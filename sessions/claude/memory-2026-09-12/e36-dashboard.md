---
name: e36-dashboard
description: "The local web instrument panel for the E36 — how it is built, what it deliberately refuses to do, and how to run it"
metadata: 
  node_type: memory
  type: project
  originSessionId: 520df9c4-5564-4e32-b377-60307bb80ef3
  modified: 2026-08-10T03:35:39.873Z
---

Local instrument panel for [[e36-obd1-kline-project]], at `~/Desktop/E36_OBD`, run with `./.venv/bin/python -m e36obd dash`. Python stdlib plus pyserial only — no framework, no CDN, works offline. Four hash-addressable tabs: `#tablero` (analog gauges), `#diagnostico` (faults, DS2/EGS probe, snapshot diff), `#capturas` (log analysis), `#scanner` (RAM explorer).

Flags: `--lan` binds 0.0.0.0 with a generated token (constant-time compare, also accepted as cookie or `X-Token`); `--demo` generates synthetic but physically plausible data so the panel can be developed and shown with no car; `--no-live` never opens the port.

**The architectural constraint:** the K-line is one serial port and only one thing may own it. Exactly ONE thread touches serial — it holds the live session and drains an action queue between samples. HTTP handlers never open the port; they enqueue and poll. That is why recording, fault reads, RAM dumps and DS2 probing coexist with live polling.

**Deliberate refusals, enforced server-side rather than hidden in the UI:** block titles `0x02` WriteRAM, `0x1A` WriteEEPROM and `0x04` ActivateActuator are rejected before reaching the bus (unit-tested with a fake ECU). Clearing fault memory IS allowed but always writes an automatic snapshot first, because the occurrence counters are the only evidence of how often a fault happens.

**Visual language:** red-orange on true black, monospace, deliberate single dark mode. Series colour `#e0521a` was chosen by running the palette validator, not by eye — BMW's actual amber (~`#ff7a1a`) fails the dark-mode lightness band at OKLCH L 0.72. Icons are Lucide (MIT) inlined so they take `currentColor`. The car blueprint is extracted from Ignacio's own `~/Desktop/Project-BMW-E36/Frame 465.pdf` via `pdftocairo`, filtered to drop dimension rules, coordinates rounded to 1 decimal (3.1 MB → 148 KB).

**Two features that beat the 1 Hz sampling wall.** *Focus mode* polls a single address as fast as the link allows — the link is not 1 Hz, it is 1 Hz *for an eleven-byte read*, and KWP71 acks every byte with its inversion so wire cost is ~2× payload. Measured 6 Hz on one byte. The server keeps a ring buffer and ships samples in batches, so a browser polling at 1 Hz still receives every sample. *Bit-level granularity* in the guided RAM search, because the M40–M52 throttle sensor is a **switch** (idle and full-load contacts, both open at part throttle), so the TPS is one or two bits in a status byte and the idle contact is **closed at idle** — you filter on "went to 0" when the throttle opens, not "went up". Both verified in isolation against synthetic targets with a free-running counter and a noise channel as decoys.

**Fifth tab, `#caja`: live transmission ratio.** The visualisation this diagnosis actually needs — engine/output ratio over time with a dashed reference line per gear (from the 4L30-E manual: 1st 2.860 / 2nd 1.620 / 3rd 1.000 / 4th 0.723, plus a Base set 2.400/1.479 selectable). A trace sitting ON a line means that gear is engaged; a trace FLOATING BETWEEN lines is a gearbox in no gear at all, which is exactly what EGS code 100 complains about. A plain rpm chart cannot show that. The y-axis is deliberately pinned to 0.65–2.95 rather than autoscaled, so all four lines stay visible and sessions are comparable.

It reads three configurable EGS RAM addresses (engine rpm, output speed, status byte) whose locations are **not yet known** — they get found once with the Scanner's guided search against the EGS target and are persisted to `egs_bindings.json`. Until then the tab explains what to look for. Verified end-to-end in `--demo`, which simulates a failed 2→3 so the between-lines signature is visible without the car.

**Do not leave a demo `egs_bindings.json` behind:** fake addresses make the panel display plausible-looking garbage as if it were real.

**How to apply:** charts are one-per-channel on purpose — rpm/°C/V/ms differ by orders of magnitude and a shared axis would be a dual-axis chart. Every axis has a `minRange` floor so sensor quantization (0.068 V, 0.65 °C per count) does not render as a dramatic spike. Needles use a first-order lag that never overshoots, because a springy needle lies about the data between 1 Hz samples.
