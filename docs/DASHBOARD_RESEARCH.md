# Dashboard research — what's left worth building

Research notes for the E36 OBD1 dashboard. Compiled 2026-08-10.

Scope: features, not code. Everything here is implementable in vanilla JS against the
existing stdlib server, offline, no dependencies.

This document deliberately **skips anything already built** — the MIL-STD-1472 gauges,
segmented bars, engine-gated telltales, session-derived metrics, the linked cursor, the
second-session overlay, the auto-running fault-snapshot diff, the RAM explorer with
accumulated per-byte stats and its guided filter loop, `--demo` mode, and the
server-side write block. Those are done and they put this well past anything in the
consumer OBD space.

Labelling follows `PROTOCOL_NOTES.md`: **CONFIRMED** (verified against this repo's own
data or a primary source), **LIKELY**, **UNKNOWN**.

---

## 1. Four things your own data proves

These are the load-bearing findings. Everything in §2 follows from them.

### 1.1 Your captures are 42% dead air, and nothing shows it — **CONFIRMED**

`session_174425.csv`, 49 samples over 66.8 s of wall clock:

| Metric | Value |
|---|---|
| Median sample interval | 0.847 s (1.18 Hz) |
| Min / max interval | 0.799 s / **17.708 s** |
| Gaps > 5 s | two: 17.708 s and 10.338 s |
| Wall clock inside a gap | 28.0 s of 66.8 s = **42%** |

The gaps are reconnects — `LiveReader.sample()` retries up to five times, each `_open()`
costing ≥2.6 s of mandated bus idle plus ~2 s of bit-banging. That is correct behaviour
for this link. The problem is that `lineChart()` joins every point to the next
unconditionally, so a 17.7-second hole renders as a clean straight line. For
intermittent-fault work that is disqualifying: the most likely place for the fault to
have happened is inside the hole you cannot see.

### 1.2 The live view fabricates samples during a dropout — **CONFIRMED, and worse than the gap**

`poll()` runs on a fixed `setTimeout(poll, 1000)` and appends `s.live[key]`
unconditionally. `Poller.state["live"]` is only cleared when the *session* tears down —
during `LiveReader.sample()`'s internal reconnect loop, which is exactly where that
17.7 s gap came from, the state keeps its last values and `connected` stays `true`.

So the browser pushes **the same stale value seventeen more times**, and plots them
against array index rather than time. During a dropout the live chart draws seventeen
invented samples as a flat, confident line — which reads as "rock steady", the precise
opposite of the truth. Any alarm, telltale or eyeball judgement made from that view is
unsound.

### 1.3 Six unknown bytes are fetched and discarded every sample — **CONFIRMED**

`CORE_START = 0x0036`, `CORE_LENGTH = 0x0B` reads `0x36`–`0x40` inclusive. Five bytes
are decoded. **`0x39`, `0x3A`, `0x3B`, `0x3D`, `0x3E`, `0x3F` are read at full rate,
every sample, and thrown away** in `LiveReader._sample_once()` and again in
`Poller._write_row()`.

Six free unknown channels, already paid for, zero extra round trips.

### 1.4 Two scalings cannot cover their physical range — **CONFIRMED (arithmetic)**

Every current sensor is a single byte. Running each scale across `0..255`:

| Channel | @ 0x00 | @ 0xFF | Quantum | Needs | Verdict |
|---|---:|---:|---:|---|---|
| battery | 0.00 V | 17.37 V | 0.068 V | 10.5–15 V | OK |
| intake_air_temp | −33.5 °C | 132.3 °C | 0.65 °C | −20–90 °C | OK |
| coolant_temp | −32.5 °C | 133.3 °C | 0.65 °C | −20–125 °C | OK |
| **rpm** | 0 | **2550** | 10 rpm | 0–6500 rpm | **saturates** |
| load | 0.00 ms | 12.75 ms | 0.05 ms | 0–~10 ms | marginal |
| road_speed | 0 | 281 km/h | 1.1 km/h | 0–220 km/h | OK |
| **air_consumption** | 0 | **51 kg/h** | 0.2 kg/h | ~280 kg/h at WOT | **saturates** |

rpm wraps above 2550. Airflow covers about a fifth of the engine's range. Both are
near-certainly **16-bit** — and rpm's high byte is almost certainly `0x003B`, which you
are already reading and discarding (§1.3), sitting one byte before `0x3C` exactly where
r3vlimited's "RPM descriptor 0x3B" note puts it (`PROTOCOL_NOTES.md` §7). **LIKELY**,
and trivially testable: rev past 2600 and watch `0x3B` go non-zero as `0x3C` wraps.

Related display bug: the rpm dial is drawn `max:7000, redline:6000` on a channel that
physically stops at 2550. Two-thirds of that face is unreachable and the needle wraps to
the bottom at 2600 rpm rather than pegging.

---

## 2. What to build, ranked

Ten items. The first four are cheap and fix correctness; the rest are capability.

### 1. Sample identity — server stamps a monotonic counter and timestamp; client appends only when it advances

*Why:* §1.2. The live view currently invents one duplicate sample per second through
every dropout and draws it as a steady line. Nothing else in the tool can be trusted
until this is fixed, and every other integrity feature falls out of it.
*Complexity:* **trivial.** One counter in `Poller._session()`, one comparison in
`poll()`, plot against the timestamp instead of the array index.

### 2. Gap-aware charts and a link-health readout

*Why:* §1.1. Emit a new `M` in the path whenever `Δt > 2.5 ×` the median interval and
shade the gap; grey out any value older than ~2.5 sample periods and stop it feeding
alarms. Surface achieved Hz **both ways** — `rows / duration` (0.73 Hz on that session)
and the median inter-sample rate outside gaps (1.18 Hz). The divergence between those
two numbers *is* your link-quality metric, and `LiveReader.reconnects` is already being
counted and never published.
*Complexity:* **trivial.**

### 3. Log the whole 11-byte core block as raw hex in every CSV row

*Why:* §1.3. Six unknown bytes are already on the wire every sample. Logging them costs
nothing and retroactively doubles the size of every future discovery dataset — including
the `0x3B` test in §1.4.
*Complexity:* **trivial.** Two lines.

### 4. Scale/range audit as a standing check

*Why:* §1.4. For every channel, compute the range its scaling implies and flag any that
cannot cover its plausible physical envelope, plus any gauge face wider than its
channel's representable range. You have no manufacturer definition file, so this is the
only thing standing between you and a plausible-looking wrong number. It already catches
two live bugs and the 7000 rpm dial.
*Complexity:* **trivial.** A table of plausible envelopes and a loop.

### 5. Continuous ring buffer with triggered capture

*Why:* §3.3. Always recording into a circular buffer; a trigger freezes a window
**before and after** the event, drops a timeline marker, and keeps recording. This is
the standard professional scan-tool feature and the only realistic way to keep the
context around an event you cannot sample. The canonical mistake to avoid is documented
in TunerStudio's own composite logger: *"if you do not click the box to capture a log to
a file, you can't save it after recording"* — you watch the fault happen and the data is
gone because you did not declare in advance that you wanted it.
*Complexity:* **moderate.** A deque in `Poller`, a trigger evaluator, a save path.

### 6. Focus mode — trade channels for sample rate, with an earliest-deadline scheduler

*Why:* §3.2. Your link is not "1 Hz". It is ~1 Hz *for an eleven-byte read*. A
single-byte `read_ram` is a much shorter transaction, and the rate scales accordingly —
this is the one lever that genuinely buys temporal resolution, and it is the difference
between never seeing a 200 ms event and seeing it about half the time. Implement it as
per-channel desired intervals with a next-due timestamp, always servicing the most
overdue channel (AndrOBD's model), plus a one-click "hunt this address and nothing else"
mode. Show achieved Hz per channel rather than pretending to a nominal rate.
*Complexity:* **moderate.**

### 7. Bit-level view and stimulus correlation in the scanner

*Why:* The scanner converges on a **byte**. The M40/M42/M43/M50/M52 throttle sensor
(BMW p/n 13631726591) is a **switch** — an idle contact and a full-load contact, both
open at part throttle — so TPS is **one or two bits inside a status byte**, not a byte
that tracks the pedal. Byte-level increased/decreased will see it only as a small
numeric wobble among noisier neighbours. `PROTOCOL_NOTES.md` §7 records INPA polling a
10-byte "digital values" block at `0x0020` with two bits decoded (`0x20` lambda control
active, `0x10` idle speed status) — that block is where to look first, and "idle speed
status" is plausibly the idle contact itself.

Two mechanics, both small:
- **Per-bit change counters and bit-level predicates**, so a toggling bit is visible.
- **A stimulus track**: hold a key while the pedal is off idle, release on lift, repeat
  ten times. Then rank all 252 bytes *and* all 2,016 bits by agreement with that track.
  cabana's "Find Similar Bits" is ~30 lines — count disagreements against a reference
  bit, keep anything below 50%, sort ascending — and it has an *Equal: Yes/No* toggle,
  which matters because an idle contact is closed at idle and therefore **inverted**
  relative to "throttle open".

Use Spearman as well as Pearson for the byte-level version (NTC curves are strongly
non-linear and rank correlation finds monotonic relationships Pearson misses), and
search ±3 samples of lag — at 0.85 s per sample, a one-sample misalignment drops a true
correlation from 0.95 to 0.3.
*Complexity:* **moderate.**

### 8. A change-count scan mode

*Why:* Every relative predicate compares two adjacent samples, so it is at the mercy of
*when* those samples landed — and your intervals range 0.799 s to 17.7 s. A **count of
how many times each byte changed**, filterable, is an aggregate over the whole window
and is immune to that jitter. BizHawk's RAM Search has it for exactly this reason
(frame-stepped work at low rates), with the canonical trick of making the count
countable: blip the pedal **exactly four times** over a sixty-sample capture, then filter
`changes ≈ 8`. rpm changes nearly every sample and is excluded from one side; coolant
changes every ~20 samples and is excluded from the other. One filter, both confounders
gone. Pair it with a reset button so it is a scoped experiment, not a lifetime total.
*Complexity:* **trivial** given the accumulated stats you already keep.

### 9. Derived channels that aren't there yet

*Why:* Warm-up rate and idle stability are built. Four more carry real diagnostic weight:

- **Injector duty cycle.** `duty% = PW_ms × rpm / 1200` for one injection per 720°, or
  `/600` for batch fire once per crank revolution (**UNKNOWN** which applies to the M43 —
  make it a labelled constant). At your idle, 2.7 ms and 900 rpm, that is 2.0% or 4.1%.
  Pulse width alone does not tell you whether the fuel system is near its limit; duty
  cycle does, and a PW that has crept up 15% at the same rpm and airflow since last
  month is a lean-running engine compensating.
- **Fuel adaptation.** `EXTRA_SENSORS` already defines `lambda_integrator` at `0x0211`,
  and `PROTOCOL_NOTES.md` §7 lists `0x0207` additive, `0x0201` multiplicative and
  `0x0262` TEV adaptation, all `B3 − 128`. The dashboard reads none of them —
  `web.py` imports only `CORE_SENSORS`. These are *the* classic Motronic diagnostic:
  additive off at idle with multiplicative near zero means unmetered air, i.e. a vacuum
  leak; multiplicative off across the range means fuel pressure, injectors or the air
  mass meter. At 0.2 Hz through the scheduler in item 6 they are nearly free.
- **Gear ratio clustering.** Once road speed is located, histogram `rpm / road_speed`
  and let the clusters emerge rather than hardcoding A4S 310R ratios. Four sharp peaks
  confirms both channels are real; a smear means torque-converter slip (expected below
  ~40 km/h on your automatic) or that one channel is wrong. This is also the **validation
  test** for whichever byte you decide is road speed — a candidate that produces clean
  ratio clusters is right, one that does not, is not. Then log ratio-cluster transitions
  as shift events: "it never left cluster 3 above 90 km/h" is a diagnosis.
- **Link health as real channels.** Achieved rate, reconnect count, gap count and
  seconds, longest gap — logged into the CSV and charted like anything else. `README.md`
  already records that reads degrade with the engine running because of ignition noise,
  so a run whose reconnect rate spikes at a particular rpm is telling you about the
  ignition system, not just the cable. Speeduino ships a gauge for exactly this
  (`loopGauge`, ECU main loop rate, danger below 750 loops/s) — the acquisition path is
  a sensor like any other.

One rule governs all of them: **never compute a rate from consecutive samples.** With a
0.65 °C coolant quantum at 1.18 Hz the sample-to-sample derivative is always exactly 0
or ±0.77 °C/s — pure quantisation, no information. Use a least-squares slope over a
window (30–60 s for temperature, 5–10 s for rpm) and state the window length in the UI.
*Complexity:* **moderate.**

### 10. Alarm rules with deadband, debounce, gating and latching

*Why:* The telltales are gated on the engine running, which is the right first move, but
the thresholds are still inline literals evaluated on the latest single sample. One
corrupted byte on a noisy K-line flips a lamp and the next sample flips it back, with no
record that it happened. Four mechanisms, all from ISA-18.2 / EEMUA 191, all cheap:

- **Deadband.** EEMUA 191's recommended defaults by measurement type: temperature 1%,
  pressure 2%, level 2%, flow 5%. Applying deadband plus on/off delay is documented as
  cutting alarm load 45–90%.
- **N-of-M debounce**, not a wall-clock delay — at 1.18 Hz with gaps, sample counts are
  the honest unit. 2-of-3 is a reasonable default. TunerStudio ships this as a named
  primitive, `isTrueFor(cond, seconds)`; that it exists as a first-class function rather
  than being left to each user is the tell.
- **Gating.** No alarm while the link is down or the value is stale (§1.2), none during
  cranking, none on lambda before closed loop.
- **Latching.** A 200 ms excursion is at most one sample and possibly zero, so a breach
  must stay visible with its peak value and timestamp until acknowledged. A transient
  that has already recovered is exactly what you are hunting; an indicator that cleared
  itself while you were looking at the road has destroyed the only evidence.

Two structural refinements worth taking from the EFI world: **four levels per channel**
(`LowCritical` / `LowWarning` / `HighWarning` / `HighCritical`, as every TunerStudio
gauge and every Speeduino `.ini` gauge declaration carries) because battery voltage and
coolant are both dangerous at *both* ends; and **the lamp renders the reason** — rusEFI
displays `Fuel cut: <reason>` by indexing a string list rather than lighting a generic
lamp, and you already have the code-to-description table in `faults.py`.
*Complexity:* **moderate.** A rule table plus one evaluator, replacing the literals.

**Just outside, both cheap:** *peak-hold with decay* on the dials (TunerStudio's
`ShowHistory` + a 15 s `HistoryDelay` — you cannot watch a gauge while driving, and it
is the one thing a dial does better than a number); and *filter chips named after the
physical reason* — engine not running, warming up, overrun, not in closed loop, **stale
sample**, **adjacent to a reconnect** — applied to every chart and statistic. Speeduino's
VE-analysis filters are named this way (`accelFilter`, `aseFilter`, `overrunFilter`,
`minCltFilter`), and the last two on my list exist in no other tool because no other tool
has your link.

---

## 3. Hunting a 200 ms fault that fires once every twenty minutes

This is the crux, so here is the whole argument rather than a feature list.

### 3.1 Accept the arithmetic first

At a 0.847 s median interval, a 200 ms event is visible in roughly **200/847 ≈ 24%** of
occurrences — and that assumes the value is even latched in RAM for the full duration
rather than being filtered by the DME before it reaches the location you are reading.
Once every twenty minutes means about three chances an hour, so **a one-hour drive gives
you roughly a 56% chance of catching it once.**

That number should be *in the UI*. `README.md` already says the right thing in prose —
"absence of a glitch in a log is not evidence of absence" — but the dashboard should
compute it: given N samples over T minutes and an assumed event duration, state the
detection probability next to any negative result. It converts "I didn't see it" into a
quantity, which is the difference between a null result and a wasted afternoon.

One genuinely counterintuitive consolation: **your jitter helps.** Intervals ranging
0.799–0.911 s mean you are not phase-locked. A perfectly uniform 1 Hz sampler can beat
against a quasi-periodic event and miss it systematically forever; a jittered sampler
cannot. Do not "fix" the timing.

### 3.2 Buy resolution by giving up breadth — the only real lever

The link is round-trip bound, but the round trip is not constant: it scales with payload.
At 9600 8N1 each byte is ~1.04 ms, and KWP71 acknowledges **every byte with its
inversion**, so wire cost is about double the payload — plus, per the captured INPA
session in `PROTOCOL_NOTES.md` §4, two NOP block pairs between data requests, which the
capture's author found were load-bearing.

An eleven-byte core read is therefore materially more expensive than a one-byte read.
Dropping to a single address should get you into the **several-Hz** range, which moves a
200 ms event from "24% chance" to "reliably caught".

So the design move is not to speed up the link — it is to **spend the whole budget on
one address when hunting**, and to make that a first-class mode rather than a config
edit. Everything else drops to 0.1–0.2 Hz through the deadline scheduler. This is the
same instinct as the scan-tool trade convention (trim the PID list for a faster refresh)
and TunerStudio's Data Log Profiles (named channel subsets, switchable per task), and it
is worth measuring rather than assuming: instrument the actual transaction time for a
1-byte vs 11-byte read and put both numbers in the UI.

### 3.3 Make the ECU be the fast logger — the highest-yield move

You cannot sample at kHz. **The DME already does.** It samples its own inputs
continuously and latches, per fault: an occurrence counter, a condition bitfield with
`0x40` "error present now" and `0x80` "sporadic", and freeze-frame values. That is a
hardware event recorder wired to every sensor you care about, and it is sitting on the
other end of the cable.

The snapshot diff already runs on the occurrence counters. Three upgrades turn it from a
before/after comparison into an event detector:

1. **Poll during the run**, every 20–30 s. One round trip, ~0.03 Hz, essentially free.
2. **Diff every poll**, not just start against end — on a new code, a counter increment,
   or the `0x40` present-now bit toggling, raise an event, drop a timeline marker, and
   **fire the ring-buffer trigger** (item 5).
3. **Chart the counters as step series** alongside the sensor channels.

The payoff is exact: **you get a timestamp for an event you could never have sampled.**
Your code 73 is stored sporadic — vehicle speed signal, or TPS, which is precisely the
pair you cannot locate. When it re-occurs the DME will tell you within thirty seconds,
and the ring buffer hands you the surrounding context. That combination confirms a
candidate byte *and* diagnoses the fault in the same run.

Watch the `0x40` bit specifically. A transition from historic to present-now and back is
the fault happening, timestamped at the ECU's detection rate rather than yours.

### 3.4 Look for the residue, not the event

A 200 ms dropout leaves traces that persist orders of magnitude longer than the event.
Integrators are low-pass filters that remember impulses — which is exactly what you need
when you cannot sample the impulse.

- **Fuel adaptation** (`0x0211`, `0x0207`, `0x0201`) steps and *stays* stepped. A
  fuelling-relevant glitch is visible for minutes afterwards in a value you can sample at
  0.2 Hz.
- **Idle actuator position** moves and recovers slowly.
- **The transmission failing to upshift is itself the residue** of a VSS dropout, and it
  persists for seconds — far longer than the electrical event that caused it.
- **The EGS is an independent witness.** Per `EGS_NOTES.md` it has its own fault memory
  and its own output-speed sensor (n-ab), on a different protocol. Two modules logging
  the same drive from different sensors is a corroboration channel nothing else gives
  you. Poll both, and diff both.

Design consequence: give slow integrator channels their own strip chart with a long time
base, and mark steps in them as events. A step in adaptation with no corresponding
change in rpm or load is a fast event you did not see.

### 3.5 Distinguish a bad sensor from a bad cable — free, and nobody does it

When a sample is implausible — rpm jumping 2500 in one interval, a value pinned at
`0x00` or `0xFF` — check whether **the other channels glitched in the same sample**. All
five moving wildly at once is a corrupted read; one moving alone is a real sensor event.

This costs a few lines, it runs on data you already have, and it is the difference
between chasing a wiring fault in the harness and chasing a marginal K-line connection.
Nothing in the consumer tool space does this because nothing else reads five channels
from one contiguous block in a single transaction — you get it because of `CORE_LENGTH`.

### 3.6 Stop waiting and provoke it — wiggle-test mode

The technician's actual answer. Single address, maximum rate (§3.2), everything else
off, plus **an audible tone whose pitch tracks the value** so you can be under the bonnet
with both hands on a connector instead of watching a screen. `AudioContext` with an
oscillator is a dozen lines and needs no network. Add a hold-to-mark key so the moment
you wiggled a specific connector lands on the timeline.

Combined with §3.3 this is the strongest pairing available: provoke, and let the ECU's
own fault counter adjudicate whether you succeeded.

### 3.7 Trigger sources, in order of usefulness here

1. **Fault-counter increment or `0x40` transition** (§3.3) — the ECU caught what you could not.
2. **Manual**, on the spacebar — "it just did the thing". TunerStudio uses spacebar for
   log marks; Snap-on supports wiring the trigger to a steering-wheel switch so a
   technician can fire it mid-road-test without looking.
3. **Comms loss.** A reconnect is itself an event worth having the run-up to, and given
   §1.1 it fires often. The run-up may show a rising error rate that precedes the drop.
4. **Plausibility violation** (§3.5).
5. **Threshold or rate**, with the §2.10 debounce rules.

On fire: freeze the window, write it with the trigger reason, drop a marker, beep once,
**and keep recording**. A trigger must never stop the capture.

### 3.8 Make long captures navigable

A forty-minute drive at 1.18 Hz is ~2,800 samples and is unreadable without navigation.
A **full-width overview strip** showing where events, alarms, gaps and triggers occurred
across the whole run, clickable to jump, is what makes the difference between taking long
captures and quietly giving up on them. MegaLogViewer's implementation is exactly this —
*"red lines in status bar to indicate MARK positions"*, at whole-log scale rather than
only on the zoomed chart.

And do not smooth by default. A moving average is a transient remover; if you offer it,
draw the raw series underneath. At these densities, draw the sample points too — twelve
points and a line through them is honest, a smooth curve through twelve points is not.

---

## 4. UX mistakes to avoid

Filtered to ones you are actually exposed to.

1. **Connecting across gaps** (§1.1) and **treating a repeated poll as a new sample**
   (§1.2). The two failure modes that make a dashboard confidently wrong.
2. **Not distinguishing zero from no-data from stale.** Three different states, routinely
   rendered identically — and it bites unusually hard here, because `README.md` records
   that every sensor address reads `0x00` with the engine off. That is a real reading of
   zero that means "not populated".
3. **Autoscaling Y axes by default.** `lineChart()` takes lo/hi from the data and pads
   15%, so an idle rpm trace varying by two quantisation counts fills the chart and looks
   alarming. The `minRange` floor helps but is a floor, not a range — any real excursion
   still rescales everything. Default to the physical range each sensor already declares,
   offer autoscale as a toggle, and always label the axis so a rescale is visible.
4. **Precision theatre.** The CSV writes `900.000` rpm, `57.850` °C, `2.700` ms against
   quanta of 10 rpm, 0.65 °C and 0.05 ms. Three decimals on a value that moves in steps
   of ten makes quantisation noise look like signal — the idle trace wobbling 880–920 is
   **±2 counts**, not a hunting idle. Display at the precision of the quantum and show
   the raw byte alongside.
5. **A gauge face wider than its channel's range** (§1.4). A needle at the two-thirds
   mark is a lie you can read at a glance, which is worse than no dial.
6. **Modal dialogs while driving.** Alerts belong in a persistent strip and an event log.
   TunerStudio's split is the right one — a modal "Global Warning" that must be dismissed
   is for *engine about to be destroyed*, and a corner "Passive Message" for everything
   else.
7. **Smoothing that hides the fault** (§3.8).
8. **Losing state on reload.** Chart history, watch lists, alarm setpoints, selected
   session, scanner candidate set. `localStorage` is enough, and losing a scanner run
   mid-hunt is genuinely costly.
9. **Slow startup.** From rusEFI's in-car dash guidance: *"a dash that takes thirty
   seconds to appear is a dash that is blank every time you start the car."* Yours is a
   local server and one HTML file, but that file is already ~173 kB and every feature
   here adds to it. Keep first paint independent of the ECU connection.
10. **Rendering cost.** TunerStudio has an entire Options → Performance page devoted to
    disabling gauge animation and enabling a "lite mode" — animated gauges are expensive
    enough on real hardware to need an escape hatch. `animate()` runs continuously on
    `requestAnimationFrame`; if you add 252 live hex cells, per-byte sparklines and a
    correlation table, budget for it and offer a way to stop animating.
11. **Generic labels.** The dominant complaint about MegaLogViewer, in its users' words,
    is that you cannot find anything — and one reply names the structural cause: *"it
    will work with so many ECUs all with different names for the same thing, it gets
    really confusing."* Supporting thirty ECU families forces every label to be abstract.
    **You support exactly one car.** Name things concretely — "termostato abierto",
    "código 73", "0x003C" — and never generalise a label to cover a case you do not have.
    It is the cheapest quality your tool can have and the one commercial products
    structurally cannot copy.
12. **Hiding uncertainty.** Half your scalings are inferred from a *different ECU
    variant*. Worth a concrete warning: RomRaider ships BMW logger definitions with real
    TPS and vehicle-speed addresses, and they will surface if you search — but they are
    for **Siemens MS41/MS42/MS43 on DS2** (the M52 six-cylinders), not Bosch M1.7.2 on
    KWP71. Those files put engine data around `0xDA2A`–`0xFAFC`; everything confirmed on
    your car lives in `0x0036`–`0x0262`. A plausible address from a nearby ECU is the
    most expensive kind of wrong because it produces a number rather than an error. Every
    value derived from an unverified scaling should carry a visible confidence marker —
    the repo's own CONFIRMED / LIKELY / UNKNOWN convention, in the UI.

---

## 5. Sources

**Tools studied**

- MegaLogViewer / MegaLogViewer HD — <https://www.efianalytics.com/MegaLogViewer/>, <https://www.efianalytics.com/MegaLogViewerHD/>; change log <http://www.efianalytics.com/MegaLogViewer/changeLog.html>
- TunerStudio MS — <https://www.tunerstudio.com/>; math parser (incl. `isTrueFor`) <https://www.tunerstudio.com/index.php/support/manuals/88-math-parser-functions>; Data Log Profiles <https://www.tunerstudio.com/index.php/products/tuner-studio/tsarticles/94-data-log-profiles>; Action Management <https://www.tunerstudio.com/index.php/products/tuner-studio/tsarticles/125-action-management>
- Gauge property names (`ShowHistory`, `HistoryDelay`, `NeedleSmoothing`, `PegLimits`, `InvalidState`, four-level limits) read from real TunerStudio `.dash` XML, e.g. <https://github.com/bryhasagithub/arduino-afr-gauge>
- Speeduino `speeduino.ini` — gauge declaration format, indicator lamp set, `loopGauge`, `[VeAnalyze]` filter names — <https://raw.githubusercontent.com/noisymime/speeduino/master/reference/speeduino.ini>
- rusEFI — <https://github.com/rusefi/rusefi>; Digital Dash <https://github.com/rusefi/rusefi/wiki/Digital-Dash>
- cabana (maintained fork) — byte-pattern classifier, bit muting, Find Similar Bits, Find Signal — <https://github.com/deanlee/openpilot-cabana>
- SavvyCAN — Sniffer notching, Flow View playback, Range State, File Comparison — <https://www.savvycan.com/docs/>
- Cheat Engine scan types and percentage scans — <https://wiki.cheatengine.org/index.php?title=Help_File:Scan_types>, <https://wiki.cheatengine.org/index.php?title=Help_File:Percentage_scans_and_compare_to_saved_results>
- BizHawk RAM Search, "Number of Changes" — <https://tasvideos.org/EmulatorResources/RamSearch>
- scanmem / GameConqueror — <https://github.com/scanmem/scanmem>
- RomRaider logger definition schema and BMW DS2 support — <https://www.romraider.com/RomRaider/LoggerXMLReferenceGuide>
- AndrOBD per-item update scheduling — <https://github.com/fr3ts0n/AndrOBD/wiki/Data-item-update-time>
- MoTeC i2 Pro — <https://www.motec.com.au/i2/i2overview/>
- Ircama/ELM327-emulator — <https://github.com/Ircama/ELM327-emulator>

**Practice and standards**

- Snap-on, *PID Trigger Functions* — <https://www.snapon.com/Diagnostics/US/KB/PID-Trigger-Functions.htm>
- Snap-on, *Working with Data (PIDs)* — <https://www.snapon.com/DiagnosticsManuals/TritonD8%20NA/Content/ApolloD9/Working_with_Data__PIDs_.htm>
- *Using your scan tool effectively* — <https://www.vehicleservicepros.com/service-repair/diagnostics-and-drivability/article/21060154/using-your-scan-tool-effectively>
- DIYAutoTune, *Using the Tooth Logger and Composite Logger* (the "must pre-declare capture" failure) — <https://www.diyautotune.com/support/tech/using-the-tooth-logger-and-composite-logger/>
- exida, *Why should I use an Alarm Deadband?* (EEMUA 191 deadband table) — <https://www.exida.com/Blog/why-should-i-use-an-alarm-deadband>
- *Improving alarm management with ISA-18.2* — <https://www.processonline.com.au/content/software-it/article/improving-alarm-management-with-isa-18-2-part-1-37009763>

**Vehicle-specific**

- BMW throttle position **switch** (idle + full-load contacts), M40/M42/M43/M44/M50/M52, p/n 13631726591 — <https://www.bimmerworld.com/Engine/Engine-Sensors/Throttle-Position-Switch-E36-93-99-E34-E32-E38-E39-Z3-BMW-13631726591.html>
- Motronic throttle-switch operation — <https://forums.mye28.com/viewtopic.php?t=91137>
- Everything already catalogued in `PROTOCOL_NOTES.md` §10 and `EGS_NOTES.md`

**In-repo evidence**

`session_174425.csv` (sample timing, quantisation) · `e36obd/sensors.py` (core block
extent, scalings) · `e36obd/live.py` (reconnect behaviour, discarded bytes) ·
`e36obd/web.py` (poller architecture, published state) · `e36obd/faults.py`,
`e36obd/snapshot.py` (fault record layout, counter differencing) ·
`e36obd/static/dashboard.html` (chart path construction, poll loop)
