# AI development sessions

Archived transcripts of the AI-assisted development of this project.
Snapshots taken 2026-09-08 (and 2026-09-12 for `c5212502`); conversations may have continued afterward.

## claude/  — Claude Code sessions (JSONL)
| file | source worktree | notes |
|------|-----------------|-------|
| `36c9b727-….jsonl` | `~/Desktop/E36_OBD` | main K-line / BLE thread |
| `520df9c4-….jsonl` | `~/Desktop/E36_OBD` | earlier session |
| `17cce4e9-….jsonl` | `conductor/workspaces/E36_OBD/nassau` | this worktree |
| `c5212502-….jsonl` | `conductor/workspaces/E36_OBD/nassau` | 2026-09-10 → 09-12: single-board PCB rev B (ESP32-S3 + L9637D + AP63203 + OBD2), printed case with M50 badge, JLCPCB/PCBWay pricing. Snapshot 2026-09-12; the session continued briefly after it. |

A third Desktop session (`9db594c5-…`, ~124 KB, 2026-08-09) existed at first
scan but was pruned from `~/.claude` before it could be archived.

### Raw material of session `c5212502` (2026-09-12)
| file | what |
|------|------|
| `claude/c5212502-tasks-2026-09-12.zip` | outputs of the background tasks and the Explore sub-agent spawned by that session (Freerouting logs, renders, DRC runs, the session-mining agent report) |
| `claude/c5212502-subagents/`, `claude/17cce4e9-subagents/` | full JSONL transcripts of the sub-agents each session spawned |
| `claude/memory-2026-09-12/` | snapshot of Claude's project memory notes (`MEMORY.md` index + one file per topic) as they stood at the end of the session |

`17cce4e9-….jsonl` was also refreshed to its 2026-09-11 state (it had grown since the first snapshot).

## codex/  — Codex CLI rollouts (JSONL)
Five rollouts whose `cwd` was the `nassau` worktree (2026-09-07).
The two large files are full sessions with inline tool output.

### E36 app conversation, September 11 checkpoint

[`codex/01a07e40-ac26-7072-b6db-2e6874e66e4d-visible-2026-09-11.jsonl`](codex/01a07e40-ac26-7072-b6db-2e6874e66e4d-visible-2026-09-11.jsonl) preserves the user messages and visible assistant replies from the ongoing iPhone/BLE/3D/Watch/widget conversation through the commit-preparation checkpoint. Export metadata records its timestamp, message count and credential redactions. It excludes internal runner instructions, private reasoning and tool payloads; attachment paths refer to the original workspace. Earlier raw snapshots remain historical archives.

For continuation, start with the [current session handoff](../docs/sessions/2026-09-11-app-scene-companions.md), which records the latest accepted design, camera controls, widget fix, tests, device installation and remaining hardware checks.

> These are raw transcripts and may contain paths or tokens surfaced by tool
> output. Kept in a private repo. Scrub before making this repository public.

## Readable enclosure session and handoff

The approved long ESP32/buck/ELM enclosure chat now has a [visible-conversation snapshot](../docs/sessions/2026-09-11-elm-backpack-transcript.md) and [continuation handoff](../docs/sessions/2026-09-11-elm-backpack.md), captured for the 2026-09-11 commit/push request. The [eight original reference images](../hardware/elm-backpack/references/README.md) are tracked alongside the enclosure. These readable records omit execution instructions, private reasoning and tool traffic.

### Enclosure raw-format records, September 11 checkpoint

The [compressed JSONL archive](codex/01a07e53-ae96-7b91-8f25-bf9802ad1c1f-raw-records-2026-09-11.jsonl.gz) retains the original record fields and timestamps for 64 public messages, 419 tool call/result records, and 45 embedded images. Its [manifest](codex/01a07e53-ae96-7b91-8f25-bf9802ad1c1f-raw-records-2026-09-11.manifest.json) records the exact snapshot cutoff, counts, exclusions, redactions and SHA-256 checksum. The checkpoint includes the request for raw transcripts; conversation after that cutoff is not included.

This is a filtered raw-format export, not a byte-identical runner backup: system/developer instructions, private reasoning, runtime state and duplicate events are excluded; outputs that read internal instruction/session files are redacted. Tool activity and images are retained, unlike the readable transcript. The archive uses Git LFS. After fetching LFS objects, decode it with:

```sh
gzip -dc sessions/codex/01a07e53-ae96-7b91-8f25-bf9802ad1c1f-raw-records-2026-09-11.jsonl.gz > enclosure-transcript.jsonl
```

The [export script](export_codex_records.py) accepts a local source JSONL path and destination `.jsonl.gz` path and writes a companion manifest.
