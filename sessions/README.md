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

## codex/  — Codex CLI rollouts (JSONL)
Five rollouts whose `cwd` was the `nassau` worktree (2026-09-07).
The two large files are full sessions with inline tool output.

> These are raw transcripts and may contain paths or tokens surfaced by tool
> output. Kept in a private repo. Scrub before making this repository public.

## Readable enclosure session and handoff

The approved long ESP32/buck/ELM enclosure chat now has a [visible-conversation snapshot](../docs/sessions/2026-09-11-elm-backpack-transcript.md) and [continuation handoff](../docs/sessions/2026-09-11-elm-backpack.md), captured for the 2026-09-11 commit/push request. The [eight original reference images](../hardware/elm-backpack/references/README.md) are tracked alongside the enclosure. These readable records omit execution instructions, private reasoning and tool traffic.
