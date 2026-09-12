#!/usr/bin/env python3
"""Export raw-format public message/tool records, without private runtime records.

Usage: python3 sessions/export_codex_records.py SOURCE.jsonl DESTINATION.jsonl.gz
Uses only the standard library. Images in tool results are preserved as recorded.
This is a disclosure-safe transcript export, not a byte-identical runner backup.
"""
import collections
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


TOOLS = {"custom_tool_call", "custom_tool_call_output", "function_call", "function_call_output"}
PRIVATE_READ = re.compile(
    r"(?:\.codex[/\\](?:sessions|memories)|\.claude[/\\]projects|"
    r"sessions[/\\](?:codex|claude)[/\\]|SKILL\.md|AGENTS\.md|"
    r"sidecar-v2-session-event-outbox|conductor-skill)", re.I)
PRIVATE_RECORD = re.compile(
    r'''["']role["']\s*:\s*["'](?:system|developer)["']|'''
    r'''["']type["']\s*:\s*["'](?:reasoning|agent_reasoning|compacted)["']|'''
    r"<\|(?:system|developer|analysis)\|>|<analysis>|<think>", re.I)
CREDENTIALS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{50,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{40,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?im)^\s*(?:cookie|set-cookie|authorization|x-api-key)\s*:\s*[^\n]+"),
    re.compile(r"(?i)(?:X-Amz-Signature|X-Amz-Security-Token|access_token|refresh_token|api_key)=[^&\s\"'<>]+"),
]


def read_records(path, limit):
    """Use a fixed byte cutoff even while the source session continues."""
    with path.open("rb") as stream:
        while stream.tell() < limit:
            line = stream.readline()
            if stream.tell() > limit:
                break
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def text_leaves(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_leaves(item)


def export(source, destination):
    limit = source.stat().st_size
    blocked_calls, private_lines, short_credentials = set(), set(), set()
    session_id = None
    cutoff = None
    for record in read_records(source, limit):
        cutoff = record.get("timestamp", cutoff)
        payload = record.get("payload", {})
        if record.get("type") == "session_meta":
            session_id = payload.get("id")
        if record.get("type") != "response_item":
            continue
        kind = payload.get("type")
        if kind in {"custom_tool_call", "function_call"}:
            command = payload.get("input", payload.get("arguments", ""))
            if PRIVATE_READ.search(command):
                blocked_calls.add(payload.get("call_id"))
        if kind == "reasoning" or payload.get("role") in {"system", "developer"}:
            for text in text_leaves(payload):
                private_lines.update(line.strip() for line in text.splitlines() if len(line.strip()) >= 80)
        if kind == "message" and payload.get("role") == "user":
            for block in payload.get("content", []):
                text = block.get("text", "").strip()
                if re.fullmatch(r"\d{4,8}", text):
                    short_credentials.add(text)

    counts = collections.Counter()
    redactions = collections.Counter()
    omitted = collections.Counter()
    images = 0
    short_pattern = re.compile(r"(?<!\d)(?:" + "|".join(map(re.escape, short_credentials)) + r")(?!\d)") if short_credentials else None

    def clean_text(text, check_private=True):
        if text.startswith("data:") and ";base64," in text[:100]:
            return text
        if check_private:
            if PRIVATE_RECORD.search(text):
                redactions["embedded_runtime_record"] += 1
                return "[Excluded: embedded private runtime records]"
            lines = [re.sub(r"^(?:L?\d+[:|]\s*)", "", line.strip()) for line in text.splitlines()]
            if any(line in private_lines for line in lines):
                redactions["private_instruction_or_reasoning_text"] += 1
                return "[Excluded: private instruction or reasoning text]"
            if "## Computer Use" in text and "declare const cua:" in text:
                # Keep the observed application state after tool documentation.
                start = text.find("\nWindow:")
                text = "[Internal tool instructions excluded]" + (text[start:] if start >= 0 else "")
                redactions["internal_tool_documentation"] += 1
        for pattern in CREDENTIALS:
            text, number = pattern.subn("[Credential redacted]", text)
            redactions["credential_patterns"] += number
        if short_pattern:
            text, number = short_pattern.subn("[Short credential redacted]", text)
            redactions["short_credential"] += number
        return text

    def clean(value, check_private=True):
        nonlocal images
        if isinstance(value, str):
            return clean_text(value, check_private)
        if isinstance(value, list):
            return [clean(item, check_private) for item in value]
        if isinstance(value, dict):
            if value.get("type") == "input_image":
                images += 1
            return {key: clean(item, check_private) for key, item in value.items()
                    if key != "internal_chat_message_metadata_passthrough"}
        return value

    metadata = dict(type="archive_metadata", sessionID=session_id,
                    exportedAtUTC=datetime.now(timezone.utc).isoformat(),
                    sourceByteCutoff=limit, sourceLastRecordAt=cutoff,
                    format="Original JSONL record envelope/payload fields for public messages and tool calls/results, gzip compressed",
                    exclusions="Private reasoning, system/developer messages, internal passthrough metadata, runtime state and duplicated event records. Reads of internal session/instruction files have their outputs redacted.",
                    credentials="Known short credential and common credential text patterns redacted; embedded images retained as recorded.",
                    byteIdenticalRunnerCopy=False)
    # Build outside the watched worktree; publishing a growing LFS file can
    # make UI diff watchers cache multiple incomplete, very large objects.
    with tempfile.TemporaryDirectory(prefix="e36-session-export-") as scratch:
        temporary = Path(scratch) / "records.jsonl.gz"
        write_archive(temporary, metadata, source, limit, blocked_calls, clean, counts, redactions, omitted)
        # Images are counted by the cleaning closure during write_archive.
        with gzip.open(temporary, "ab") as output:
            summary = dict(type="archive_summary", records=dict(counts), images=images,
                           omitted=dict(omitted), redactions={k: v for k, v in redactions.items() if v})
            output.write((json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
        shutil.move(temporary, destination)
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    manifest = dict(metadata, archive=destination.name, compressedBytes=destination.stat().st_size,
                    sha256=digest, records=dict(counts), images=images,
                    omitted=dict(omitted), redactions={k: v for k, v in redactions.items() if v})
    destination.with_suffix("").with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2), flush=True)


def write_archive(destination, metadata, source, limit, blocked_calls, clean, counts, redactions, omitted):
    with destination.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0) as output:
        def write(record):
            output.write((json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
        write(metadata)
        for record in read_records(source, limit):
            payload = record.get("payload", {})
            kind = payload.get("type")
            if record.get("type") != "response_item":
                omitted[record.get("type", "unknown")] += 1
                continue
            if kind == "message":
                if payload.get("role") not in {"user", "assistant"}:
                    omitted["internal_message"] += 1
                    continue
                if payload.get("role") == "assistant" and payload.get("phase") not in {"commentary", "final_answer"}:
                    omitted["non_public_assistant_message"] += 1
                    continue
                exported = clean(record, check_private=payload.get("role") != "user")
                counts[payload["role"]] += 1
            elif kind in TOOLS:
                if kind.endswith("_output") and payload.get("call_id") in blocked_calls:
                    replacement = dict(payload, output="[Excluded: output from reading internal session/instruction files]")
                    exported = clean(dict(record, payload=replacement))
                    redactions["internal_read_output"] += 1
                else:
                    exported = clean(record)
                counts[kind] += 1
            else:
                omitted[kind or "unknown_response"] += 1
                continue
            write(exported)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    export(*map(Path, sys.argv[1:]))
