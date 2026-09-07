# Gauge design — building instrument-grade readouts for the E36 dashboard

A build guide, not an essay. Every snippet here was executed, rendered in Chrome and
inspected before it went into this file; the maths was checked numerically. Where a
number is quoted (overshoot in rpm, settle time in frames) it was measured, not
estimated.

Scope: vanilla JS, inline SVG, no libraries, no CDN, works offline. Everything below
drops into `e36obd/static/dashboard.html` alongside the existing `lineChart()` and
follows the same conventions — template-literal SVG strings assigned via `innerHTML`,
CSS custom properties for colour, `1 Hz` polling.

Labelling matches `PROTOCOL_NOTES.md` and `DASHBOARD_RESEARCH.md`: **CONFIRMED**
(verified here by execution/measurement, or a primary source), **LIKELY** (one decent
source or a strong inference), **UNKNOWN** (a guess — do not act on it as fact).

---

## 0. The one-paragraph version

A gauge looks serious when its geometry is derived rather than nudged, when it shows
restraint about colour, and when it never claims more than it knows. Three things do
most of the work: (1) a single angle convention that makes `transform="rotate()"` a
literal translation of the value→angle map, so no sign errors are possible;
(2) critically damped needle motion, which by construction cannot oscillate and — as
measured in §3.4 — never displays a value the sensor did not report; (3) knowing which
channels want a pointer and which want a number. Your rpm wants a dial. Your battery
voltage does not, and §4.1 explains why forcing it into one produces a gauge that is
40% warning zone.

---

## 1. The geometry core

### 1.1 Angle convention — pick one and never think about it again

**Degrees, measured clockwise from 12 o'clock.**

```
    0° = up (12:00)      90° = right (3:00)
  180° = down (6:00)    270° = left (9:00)
```

This is the right choice for one specific reason: SVG's y axis grows *downward*, so
screen-clockwise is the positive rotation direction. That makes this convention agree
with SVG's own `rotate()` **and** with arc `sweep-flag=1`. Draw a needle pointing
straight up, and `transform="rotate(θ 100 100)"` aims it at exactly θ in your
convention. No sign flips, no offset constants, nowhere for an error to hide.

Converting to the frame `Math.cos`/`Math.sin` want is a single subtraction:

```js
// screen-clockwise-from-12  ->  standard math frame
const a = (deg - 90) * Math.PI / 180;
x = cx + r * Math.cos(a);
y = cy + r * Math.sin(a);
```

Verify it once and move on — **CONFIRMED** by execution, with `cx=cy=100, r=50`:

| deg | x | y | reads as |
|----:|--:|--:|---|
| 0 | 100 | 50 | up |
| 90 | 150 | 100 | right |
| 180 | 100 | 150 | down |
| 270 | 50 | 100 | left |

**Sweep conventions.** A 270° sweep starting at 225° (7:30, lower-left) ends at
225+270 = 495° ≡ 135° (4:30, lower-right) — symmetric about vertical, with the gap
centred at the bottom. That is the classic full-size tachometer layout and it is what
you want for rpm. A 250° sweep starting at 235° also lands symmetrically (235+250 =
485 ≡ 125°) and gives more room for two- and three-digit numerals; use it for
temperature and anything with wide labels.

The real E36 cluster tachometer sweeps somewhat less than 270° — by inspection of
cluster photographs it is roughly 240–250°, needle at rest near 8 o'clock —
**UNKNOWN** as an exact figure, I could not find a BMW spec for it. It is a parameter;
set `sweep` to taste. Note also that a 270° sweep is *not* a period-correct E36
detail, it is the generic instrument convention. Both look right.

### 1.2 The three helpers

```js
const R2 = n => Math.round(n * 100) / 100;                 // keeps path data short
const clamp = (v, lo, hi) => v < lo ? lo : v > hi ? hi : v;

/* Polar -> cartesian. deg is clockwise from 12 o'clock. */
function pol(cx, cy, r, deg) {
  const a = (deg - 90) * Math.PI / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

/* Arc from a0 to a1 at radius r. Because our angles run clockwise and SVG's
   sweep-flag=1 also means clockwise, the flag is simply "is a1 after a0". */
function arcPath(cx, cy, r, a0, a1) {
  const [x0, y0] = pol(cx, cy, r, a0), [x1, y1] = pol(cx, cy, r, a1);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  const sweep = a1 >= a0 ? 1 : 0;
  return `M${R2(x0)} ${R2(y0)} A${R2(r)} ${R2(r)} 0 ${large} ${sweep} ${R2(x1)} ${R2(y1)}`;
}

/* Tick values anchored to a NICE grid (multiples of step), not to min.
   Anchoring to min gives you ticks at -30,-10,10,... which look like a mistake. */
function ticksFor(min, max, step) {
  const out = [];
  if (!(step > 0)) return out;
  for (let k = Math.ceil(min / step - 1e-9); k <= Math.floor(max / step + 1e-9); k++)
    out.push(k * step);
  return out;
}
```

The `1e-9` slop in `ticksFor` is load-bearing. Without it `ticksFor(0, 1, 0.1)` drops
the final tick to floating-point error. With it you get 11 ticks — **CONFIRMED**.

A 270° arc cannot be drawn as a single `A` command if it is a full 360° (start and end
coincide and nothing renders). Anything up to ~355° is fine; you will never approach
that on an instrument.

### 1.3 Choosing a scale — the step everyone skips

**The display range is not the sensor range.** This is the single highest-leverage
decision on a gauge face, and getting it wrong cannot be rescued by any amount of
styling.

Three rules:

1. **Show the band that carries meaning.** Your coolant sensor resolves −30 to 130 °C.
   A coolant gauge that starts at −30 spends a quarter of its sweep on temperatures
   the car will never see, compressing the 80–110 °C band where every decision
   actually lives. Start it at 20.
2. **A warning zone wider than ~25% of the sweep means the scale is wrong** — or the
   channel does not want a dial at all. §4.1 works this through for battery voltage.
3. **Pick ranges that divide evenly by `majorStep`.** `ticksFor` anchors to nice
   multiples, so a range of 40–130 with `majorStep: 10` gives ticks at both ends;
   a range of −30–130 gives you a first tick at −20 and a bare arc before it.

Verified tick counts for the ranges recommended in §9 — **CONFIRMED**:

| range | majorStep | ticks | first/last |
|---|---:|---:|---|
| 0–7000 | 1000 | 8 | 0 / 7000 |
| 40–130 | 10 | 10 | 40 / 130 |
| 10–16 | 1 | 7 | 10 / 16 |
| 0–20 | 5 | 5 | 0 / 20 |

### 1.4 `gauge()`

Returns a complete `<svg>` string. Radii are expressed in a fixed 200×200 viewBox so
every constant is legible and the whole thing scales with one `size` parameter.

```js
function gauge(cfg) {
  const c = Object.assign({
    min: 0, max: 100, value: null, majorStep: 20, minorStep: 5,
    startAngle: 225, sweep: 270, label: '', note: '', unit: '', dec: 0,
    zones: [], numFmt: v => String(v), size: 190,
  }, cfg);

  const CX = 100, CY = 100;
  //  zone band ── 92   (outboard, clear of everything)
  //  tick rail ── 86   (ticks grow INWARD from here)
  //  minor tip ── 80
  //  major tip ── 74
  //  numerals  ── 63
  const R_ZONE = 92, W_ZONE = 5.5, R_RAIL = 86, R_MAJ = 74, R_MIN = 80, R_NUM = 63;

  const span = c.max - c.min;
  const ang = v => c.startAngle + (clamp(v, c.min, c.max) - c.min) / span * c.sweep;
  const end = c.startAngle + c.sweep;
  const hot = v => c.zones.some(z => z.hot && v >= z.from - 1e-9 && v <= z.to + 1e-9);
  const inZone = c.value == null ? null
    : c.zones.find(z => c.value >= z.from - 1e-9 && c.value <= z.to + 1e-9);
  const liveCol = inZone ? inZone.color : 'var(--series-1)';

  let s = '';
  // bezel: one hairline ring. That is the entire skeuomorphism budget.
  s += `<circle cx="${CX}" cy="${CY}" r="97" fill="none"
          stroke="var(--border-lit)" stroke-width="1"/>`;

  // warning zones — dim until the needle is actually inside one
  for (const z of c.zones) {
    const live = c.value != null && c.value >= z.from && c.value <= z.to;
    s += `<path class="g-zone" d="${arcPath(CX, CY, R_ZONE, ang(z.from), ang(z.to))}"
            stroke="${z.color}" stroke-width="${W_ZONE}" opacity="${live ? 1 : .3}"/>`;
  }

  // tick rail
  s += `<path class="g-rail" d="${arcPath(CX, CY, R_RAIL, c.startAngle, end)}"/>`;

  // minor ticks, skipping any that coincide with a major
  const majors = ticksFor(c.min, c.max, c.majorStep);
  const isMajor = new Set(majors.map(v => v.toFixed(6)));
  for (const v of ticksFor(c.min, c.max, c.minorStep)) {
    if (isMajor.has(v.toFixed(6))) continue;
    const a = ang(v);
    const [x0, y0] = pol(CX, CY, R_RAIL, a), [x1, y1] = pol(CX, CY, R_MIN, a);
    s += `<line class="g-tick-min${hot(v) ? ' hot' : ''}"
            x1="${R2(x0)}" y1="${R2(y0)}" x2="${R2(x1)}" y2="${R2(y1)}"/>`;
  }

  // major ticks + numerals
  for (const v of majors) {
    const a = ang(v);
    const [x0, y0] = pol(CX, CY, R_RAIL, a), [x1, y1] = pol(CX, CY, R_MAJ, a);
    const [nx, ny] = pol(CX, CY, R_NUM, a);
    const h = hot(v) ? ' hot' : '';
    s += `<line class="g-tick-maj${h}" x1="${R2(x0)}" y1="${R2(y0)}" x2="${R2(x1)}" y2="${R2(y1)}"/>`
       + `<text class="g-num${h}" x="${R2(nx)}" y="${R2(ny)}" dy="0.34em"
            text-anchor="middle">${c.numFmt(v)}</text>`;
  }

  // a SHORT note may live inside the dial (e.g. "×1000"). A long label may not — §1.4b
  if (c.note) s += `<text class="g-label" x="${CX}" y="82" text-anchor="middle">${c.note}</text>`;

  // needle: drawn pointing UP, aimed purely by rotate()
  const a0 = c.value == null ? c.startAngle : ang(c.value);
  s += `<g class="g-needle-g" transform="rotate(${R2(a0)} ${CX} ${CY})"`
     + `${c.value == null ? ' style="display:none"' : ''}>`
     + `<path class="g-needle" d="M100 20 L102.5 100 L101.7 117 L98.3 117 L97.5 100 Z"
          style="fill:${liveCol}"/></g>`
     + `<circle class="g-hub-o" cx="${CX}" cy="${CY}" r="8.5" style="stroke:${liveCol}"/>`
     + `<circle class="g-hub-i" cx="${CX}" cy="${CY}" r="3"/>`;

  // digital co-readout, in the gap at the bottom of the sweep
  const txt = c.value == null ? '—' : c.value.toFixed(c.dec);
  s += `<text class="g-val" x="${CX}" y="138" text-anchor="middle"
          style="fill:${liveCol}">${txt}</text>`
     + `<text class="g-unit" x="${CX}" y="153" text-anchor="middle">${c.unit}</text>`;

  return `<svg viewBox="0 0 200 200" width="${c.size}" height="${c.size}"
    role="img" aria-label="${c.label} ${txt} ${c.unit}">${s}</svg>`;
}
```

**The needle.** `M100 20 L102.5 100 L101.7 117 L98.3 117 L97.5 100 Z` — a pointed tip
at radius 80, widest (±2.5) exactly at the pivot, tapering to a ±1.7 counterweight
tail 17 units behind it. The counterweight is what stops it looking like an arrow
clipped to a circle; real pointers are balanced about their pivot and the tail is the
visual evidence of that. The hub is two circles — a panel-coloured disc with a lit
ring, then a small solid centre — which covers the needle root and gives the pivot a
physical reading.

**Needle tip radius vs tick radius.** The tip lands at radius 80, exactly at the inner
end of the minor ticks. A needle that stops short of the ticks looks lost; one that
overlaps the numerals looks careless. Land it on the minor-tick line.

#### 1.4b Long labels do not go inside the dial — **CONFIRMED by rendering**

With numerals at radius 63, the numerals near the top of the sweep sit at
y ≈ 60–70 — precisely where a centred title wants to be. A first pass put
`label` at y=66 and the words `REFRIGERANTE` and `BATERÍA` collided with the numerals
`80 / 90` and `13` respectively.

The fix is not to move the text, it is to **put the channel name outside the dial**,
in the panel cell header. That is also what production dashes do, it lets the label be
as long as it needs, and it creates the horizontal alignment grid that §7 depends on.
Only a short note — `×1000`, `°C` — may sit inside, at y≈82 (18 units above the hub,
well inside the numeral ring). `gauge()` therefore takes `note`, and `label` is used
only for the accessible name.

### 1.5 The CSS

Sizes and colours live here, not in the markup, so a whole panel can be re-weighted in
one place.

```css
.g-num   { fill: var(--text-secondary); font-family: var(--mono); font-size: 12px;
           font-variant-numeric: tabular-nums; letter-spacing: .02em }
.g-num.hot { fill: var(--critical) }
.g-label { fill: var(--text-muted); font-family: var(--mono); font-size: 8.5px;
           letter-spacing: .22em; text-transform: uppercase }
.g-val   { fill: var(--text-primary); font-family: var(--mono); font-size: 26px;
           font-weight: 500; font-variant-numeric: tabular-nums; letter-spacing: .01em }
.g-unit  { fill: var(--text-muted); font-family: var(--mono); font-size: 9px;
           letter-spacing: .18em }
.g-tick-min { stroke: var(--text-muted);    stroke-width: 1 }
.g-tick-maj { stroke: var(--text-secondary); stroke-width: 2.4 }
.g-tick-maj.hot, .g-tick-min.hot { stroke: var(--critical) }
.g-rail  { stroke: var(--text-muted); stroke-width: 1; fill: none; opacity: .55 }
.g-needle{ fill: var(--series-1) }
.g-hub-o { fill: var(--surface-1); stroke: var(--series-1); stroke-width: 1.6 }
.g-hub-i { fill: var(--series-1) }
.g-zone  { fill: none; stroke-linecap: butt }

/* bloom belongs on the needle only — see §7 */
.lit .g-needle { filter: drop-shadow(0 0 4px rgba(224,82,26,.55)) }
/* stale data dims the whole instrument, not just the value */
.stale svg { opacity: .32 }
```

> **Trap — SVG presentation attributes lose to CSS.** `<text class="g-val" font-size="14">`
> renders at **26px**, not 14px, because `font-size` as an XML attribute is a
> presentation attribute and any CSS rule outranks it. This bit the first draft in
> three places. For a one-off size override use `style="font-size:14px"` (inline style
> wins) or add a modifier class. **CONFIRMED** by rendering.

The major:minor tick ratio is **2.4 : 1 in stroke weight and 12 : 6 in length**. Both
differences are needed — length alone is too weak a signal at small sizes, weight
alone reads as a rendering artefact.

---

## 2. Warning zones

A zone is an arc segment at radius 92, outboard of the tick rail with 6 units of black
between them, `stroke-linecap="butt"` so the ends are square and land exactly on their
threshold values.

```js
zones: [{ from: 6000, to: 7000, color: 'var(--critical)', hot: true }]
```

**Making it read at a glance without shouting** comes down to three decisions, and the
third is the one that matters:

1. **Put it outboard, not under the needle.** A band behind the pointer competes with
   it. Outside the ticks it is peripheral — you see it without looking at it.
2. **Keep it thin.** 5.5 units against a 92-unit radius. It is a margin annotation, not
   a region of the dial.
3. **Render it at `opacity: .3` until the needle is inside it, then 1.0.** A redline
   that is permanently at full strength is decoration; the eye tunes it out within
   seconds and it has no headroom left for when it matters. Dim it, and the transition
   to full opacity is itself the alarm.

The `hot: true` flag additionally recolours the **ticks and numerals inside the zone**
to `--critical`. This is the cheapest legibility win on the whole face: the scale
itself tells you where the limit is, so the band is confirming information rather than
carrying it alone. Real tachometers print the redline numerals in red for the same
reason.

Finally, when the needle enters a zone the needle, hub ring and digital readout all
adopt the zone colour (`liveCol` above). One state change, three coordinated signals,
no ambiguity about which channel is complaining.

---

## 3. Needle animation

### 3.1 The problem, stated honestly

Samples arrive at 1 Hz. Snapping the needle 60 times a minute is unreadable. But any
smooth motion between samples is **displaying values that were never measured** — that
is what interpolation is, and no amount of cleverness avoids it.

So the question is not "how do I avoid inventing data" (you cannot) but "what class of
lie am I willing to tell". There are two, and they are not equally acceptable on a
diagnostic tool:

- **Lag** — the needle shows a value the sensor reported slightly in the past. Benign.
  Every mechanical gauge ever built does this.
- **Overshoot** — the needle shows a value the sensor *never reported at all*, past
  the target, because the animation carries momentum. On a tachometer this can put the
  needle into the redline during a blip that never actually reached it. **This is not
  acceptable**, and it is exactly what spring/bounce easing — the default in most
  animation libraries — produces.

Never use an easing curve with overshoot (`easeOutBack`, `spring` with damping < 1,
`cubic-bezier` with a control point outside [0,1]) on a measurement.

### 3.2 The three candidates

| solver | order | overshoot | corner at sample | notes |
|---|---|---|---|---|
| linear interpolation over the sample interval | — | none | yes, visible | needle arrives exactly as the next sample lands; constant velocity looks mechanical (this is what stepper-motor clusters do) |
| exponential smoothing `x += (t−x)(1−e^(−dt/τ))` | 1st | **provably zero** | yes, in velocity | one line, never arrives exactly, feels soft |
| **critically damped spring** | 2nd | see §3.4 | none | smooth in position *and* velocity; the boundary case that cannot oscillate |

Critical damping (ζ = 1) is the right default: it is the fastest second-order approach
that does not oscillate, and it is what a real pointer with a properly specified damper
does. Underdamped oscillates (lies). Overdamped is just slow.

### 3.3 The exact step — do not integrate this numerically

With the target constant across a frame, the error `e = x − target` obeys
`ë + 2ωė + ω²e = 0`, whose critically damped solution is closed-form:

```
  A = e₀                     B = v₀ + ω·e₀
  e(t) = (A + B·t)·e^(−ωt)
  ė(t) = (B − ω(A + B·t))·e^(−ωt)
```

Which is six lines of JS and is **exact for any dt** — no stiffness, no explosion when
a background tab hands you a 5-second frame:

```js
/* Critically damped step. smoothTime T is the ~time to converge; omega = 2/T. */
function smoothStep(x, v, target, dt, T) {
  const w = 2 / T;
  const E = Math.exp(-w * dt);
  const e0 = x - target;
  const B  = v + w * e0;
  return [target + (e0 + B * dt) * E,
          (B - w * (e0 + B * dt)) * E];
}
```

Because it is the analytic solution and not an integrator, one 0.5 s step gives
bit-identical results to five hundred 1 ms steps — **CONFIRMED** (agreement to 1e-6 in
position, 1e-5 in velocity). Unity's `Mathf.SmoothDamp` is the same formulation with a
polynomial approximation to `e^(−x)` that you do not need in JS.

### 3.4 What it actually does — measured, not asserted

All figures on a 0–7000 rpm scale, 60 fps rendering.

**Step response from rest never exceeds the target.** With `v₀ = 0`, `B = ω·e₀`, so
`e(t) = e₀(1 + ωt)e^(−ωt)`, which is `e₀` times a strictly positive decreasing
function — it cannot cross zero. **CONFIRMED** over 2000 frames.

**On a mid-flight reversal it carries past where it was, but never past its old
target.** Needle climbing toward 7000, at 3474 rpm with 14 690 rpm/s of velocity, when
the sample reverses to 2000: it peaks at 4018 (544 rpm further up) then settles. It
crosses the new target **at most once and never oscillates** — measured undershoot
below target: 0.000000000. **CONFIRMED**

**Excursion past the current sample, as a function of `smoothTime`** — worst case over
4000 random 12-sample chains at a clean 1 Hz:

| smoothTime | worst excursion beyond `[prev, cur]` |
|---:|---:|
| 0.10 s | 0.000 rpm |
| 0.15 s | 0.088 |
| 0.20 s | 2.5 |
| **0.25 s** | **18.6** (0.27% of scale — sub-pixel) |
| 0.30 s | 61.6 |
| 0.50 s | 594 (8.5% of scale — visible, and misleading) |
| 1.00 s | 2763 |

**The rule that falls out: `smoothTime ≤ ¼ of the sample interval`.** At 1 Hz that is
0.25 s, at which the needle is 99.7% of the way through a step when the next sample
arrives, so it has essentially no velocity left to overshoot with. (For reference, a
full 0→1000 step at `smoothTime = 0.25` converges to within 0.5 units in 92 frames,
1.53 s — but the part that matters is the 99.7% covered in the first second.)

| smoothTime | fraction of a step covered in 1.0 s |
|---:|---:|
| 0.15 s | 99.998% |
| 0.25 s | 99.698% |
| 0.35 s | 97.785% |
| 0.50 s | 90.842% |
| 0.80 s | 71.270% |

**The guarantee that matters.** Across 3000 random trials × 12 samples × 60 fps
(2.16 M frames), with both regular and irregular sample arrival, at every smoothTime
from 0.15 to 0.50 s, the needle **never once displayed a value outside the range of
values the sensor had actually reported** — excursion above the running maximum and
below the running minimum both exactly 0.00. **CONFIRMED**

That is the property a diagnostic tool needs, and it is stronger than "no overshoot".
It also means the safety net in §3.5 costs nothing: clamping the needle to the running
`[min, max]` of observed samples fired on **0 of 2 160 000 frames**.

> Do not clamp to `[prev, cur]` instead. That window is narrow and the needle
> legitimately sits outside it while *lagging* — clamping there would yank it forward
> and create the jump you were trying to avoid. Clamp to the observed envelope.

### 3.5 The controller

One shared `requestAnimationFrame` loop for every instrument on the page, which stops
itself when everything has settled. Verified in Chrome: 9/9 assertions pass.

```js
const CHANNELS = [];
let rafId = null, lastT = 0;

function tick(now) {
  const dt = Math.min((now - lastT) / 1000, 0.1);  // clamp: the tab was backgrounded
  lastT = now;
  let busy = false;
  for (const ch of CHANNELS) busy = ch.step(dt) || busy;
  rafId = busy ? requestAnimationFrame(tick) : null;
}
function kick() {
  if (rafId == null) { lastT = performance.now(); rafId = requestAnimationFrame(tick); }
}

/* Binds to an <svg> produced by gauge(). Smooths the NEEDLE only. */
function Needle(svg, cfg) {
  const g = svg.querySelector('.g-needle-g');
  const out = svg.querySelector('.g-val');
  const A = v => cfg.startAngle + (clamp(v, cfg.min, cfg.max) - cfg.min)
                 / (cfg.max - cfg.min) * cfg.sweep;
  const T = cfg.smoothTime ?? 0.25;
  const eps = (cfg.max - cfg.min) * 2e-4;      // settle threshold, scale-relative
  let x = null, vel = 0, target = null, lo = Infinity, hi = -Infinity;
  const aim = () => g.setAttribute('transform', `rotate(${A(x).toFixed(2)} 100 100)`);

  const api = {
    get pos() { return x; },

    /* Call once per poll. */
    sample(value) {
      if (value == null) {                     // no data is NOT zero — hide the needle
        target = null; g.style.display = 'none'; out.textContent = '—'; return;
      }
      g.style.display = '';
      out.textContent = value.toFixed(cfg.dec ?? 0);   // readout is NEVER smoothed
      target = value;
      lo = Math.min(lo, value); hi = Math.max(hi, value);
      if (x == null) { x = value; vel = 0; aim(); return; }  // first sample: jump
      kick();
    },

    step(dt) {
      if (target == null || x == null) return false;
      if (Math.abs(x - target) < eps && Math.abs(vel) < eps) {
        x = target; vel = 0; aim(); return false;          // settled -> stop the loop
      }
      const w = 2 / T, E = Math.exp(-w * dt), e0 = x - target, B = vel + w * e0;
      x = target + (e0 + B * dt) * E;
      vel = (B - w * (e0 + B * dt)) * E;
      x = clamp(x, lo, hi);   // free guarantee: never show an unmeasured value (§3.4)
      aim();
      return true;
    }
  };
  CHANNELS.push(api);
  return api;
}
```

Verified behaviour — **CONFIRMED** in Chrome against a scripted sample sequence with a
mocked clock:

- needle maximum 6097.9 ≤ highest sample 6100; minimum 800.0 ≥ lowest sample 800
- settles on the final sample to within 0.001
- transform stays well-formed: `rotate(257.79 100 100)`
- readout shows the raw sample (`"850"`), not the animated position
- rAF loop terminates when settled — 0 pending callbacks
- `sample(null)` hides the needle and shows an em dash
- survives a 30 s frame gap without producing a non-finite position

### 3.6 The rules, condensed

1. **Smooth the needle. Never smooth the number.** The pointer carries trend, the
   digits carry truth. This single split resolves the whole "don't lie about the data"
   tension: whatever the needle is doing, the number beside it is the last real sample.
2. `smoothTime ≤ ¼ × sample interval`. At 1 Hz: **0.25 s**.
3. Per-channel `smoothTime`. Fast channels short, slow channels long — a long
   smoothTime on coolant is free (it physically cannot change quickly) and it
   suppresses the 0.65 °C quantisation step. Values in §9.
4. Clamp dt (0.1 s is right) so a backgrounded tab does not teleport the needle.
5. **Null is not zero.** A dropped sample must hide the needle, not park it at minimum,
   which reads as a genuine reading of 0 rpm. Dim the whole instrument at `opacity: .32`
   and show `—`.
6. Respect `prefers-reduced-motion`: `if (matchMedia('(prefers-reduced-motion: reduce)').matches)`
   set `T` very small (0.01) rather than disabling updates.

---

## 4. Bar gauges — temperature, air, fuel, load

### 4.1 The trap: low thresholds on a bar are broken by construction

A bar lights **everything below the current value**. So colouring individual segments
red because they sit below a low limit means a perfectly healthy 13.69 V battery
renders with half its lit run in alarm red — it lights every segment from 11 V up,
including the 11–13 V ones you marked as bad.

This was a real bug in the first draft and it renders exactly as wrong as it sounds.

**The correct model:** state comes from the **value**, not from the segments.

- The lit run takes the colour of the *value's* state (ok / warn / crit).
- Only a **high** limit gets a per-segment treatment, and only on *unlit* segments —
  a faint red preview of where the ceiling is, which you can see before you reach it.
- A low limit changes the colour of the whole lit run and the readout.

```js
function barState(v, lim) {          // lim: {warnLo, critLo, warnHi, critHi}
  if (v == null) return 'none';
  if ((lim.critHi != null && v >= lim.critHi) ||
      (lim.critLo != null && v <= lim.critLo)) return 'crit';
  if ((lim.warnHi != null && v >= lim.warnHi) ||
      (lim.warnLo != null && v <= lim.warnLo)) return 'warn';
  return 'ok';
}
const STATE_COL = { ok:'var(--series-1)', warn:'var(--warning)',
                    crit:'var(--critical)', none:'var(--text-muted)' };
```

This is also where the battery-as-a-dial idea dies. Display range 10–16 V with a
"warn below 13" threshold makes the low zone **50% of the sweep**. Rendered, it is an
enormous olive band that dominates a gauge whose needle is sitting comfortably in the
healthy part of the scale. A scale on which half the face means "bad" is not
conveying information. Battery wants a bar and a number — §8.2.

### 4.2 Segmented arc bar

The E36-style segmented arc: divide the sweep into `n` equal slots, inset each segment
by half the gap on both sides, light the ones below the value.

```js
function arcBar(cfg) {
  const c = Object.assign({
    min: 0, max: 100, value: null, segments: 18, gapDeg: 1.6,
    startAngle: 235, sweep: 250, limits: {}, unit: '', dec: 0,
    size: 150, radius: 62, width: 11, endLabels: true,
  }, cfg);
  const state = barState(c.value, c.limits);
  const litCol = STATE_COL[state];
  const hiMark = c.limits.critHi ?? c.limits.warnHi ?? null;
  const CX = 100, CY = 100;
  const slot = c.sweep / c.segments;
  const t = c.value == null ? 0 : clamp((c.value - c.min) / (c.max - c.min), 0, 1);
  const litCount = Math.floor(t * c.segments + 1e-9);

  let s = '';
  for (let i = 0; i < c.segments; i++) {
    const a0 = c.startAngle + i * slot + c.gapDeg / 2;
    const a1 = c.startAngle + (i + 1) * slot - c.gapDeg / 2;
    const segLo = c.min + (i / c.segments) * (c.max - c.min);
    const overLimit = hiMark != null && segLo >= hiMark - 1e-9;
    const lit = i < litCount;
    const col = lit ? litCol : (overLimit ? 'var(--critical)' : 'var(--series-1)');
    s += `<path d="${arcPath(CX, CY, c.radius, a0, a1)}" fill="none" stroke="${col}"
            stroke-width="${c.width}" stroke-linecap="butt"
            opacity="${lit ? 1 : (overLimit ? .22 : .12)}"/>`;
  }

  const txt = c.value == null ? '—' : c.value.toFixed(c.dec);
  if (c.endLabels) {                  // without these the arc has no scale at all
    const rl = c.radius + c.width / 2 + 7;
    const [lx, ly] = pol(CX, CY, rl, c.startAngle);
    const [rx, ry] = pol(CX, CY, rl, c.startAngle + c.sweep);
    s += `<text class="g-num" x="${R2(lx)}" y="${R2(ly)}" dy="0.34em" text-anchor="middle"
            style="font-size:9px">${c.min}</text>`
       + `<text class="g-num" x="${R2(rx)}" y="${R2(ry)}" dy="0.34em" text-anchor="middle"
            style="font-size:9px">${c.max}</text>`;
  }
  s += `<text class="g-val" x="${CX}" y="106" text-anchor="middle"
          style="font-size:21px;fill:${litCol}">${txt}</text>`
     + `<text class="g-unit" x="${CX}" y="120" text-anchor="middle">${c.unit}</text>`;
  return `<svg viewBox="14 25 172 125" width="${c.size}"
    height="${R2(c.size * 125 / 172)}">${s}</svg>`;
}
```

**`Math.floor`, not `Math.round`.** A segment lights when the value has genuinely
passed its threshold. Rounding lights a segment at 50% of its band, which is a claim
of precision the segmentation does not have.

**Choose `segments` so one segment is close to the sensor resolution.** Coolant over
40–130 °C with 18 segments is 5 °C per segment against a 0.65 °C sensor step — honest.
Going to 60 segments would imply a resolution the bar cannot deliver and would look
like a progress bar.

**Unlit segments stay visible** at `opacity: .12`. This is the single detail that makes
a segmented display read as a physical device rather than a filled progress bar: on a
real VFD or LED bar you can see the unlit elements. Ghost segments are the point.

### 4.3 Linear segmented bar

Better than the arc when you need several channels stacked in a column, which for four
of your five channels you do.

```js
function linearBar(cfg) {
  const c = Object.assign({
    min: 0, max: 100, value: null, segments: 24, w: 260, h: 14, gap: 2,
    limits: {}, label: '', unit: '', dec: 0, ticks: [],
  }, cfg);
  const state = barState(c.value, c.limits);
  const litCol = STATE_COL[state];
  const hiMark = c.limits.critHi ?? c.limits.warnHi ?? null;
  const H = c.h, W = c.w, top = 16;
  const sw = (W - c.gap * (c.segments - 1)) / c.segments;
  const t = c.value == null ? 0 : clamp((c.value - c.min) / (c.max - c.min), 0, 1);
  const litCount = Math.floor(t * c.segments + 1e-9);

  let s = '';
  for (let i = 0; i < c.segments; i++) {
    const x = i * (sw + c.gap);
    const segLo = c.min + (i / c.segments) * (c.max - c.min);
    const overLimit = hiMark != null && segLo >= hiMark - 1e-9;
    const lit = i < litCount;
    const col = lit ? litCol : (overLimit ? 'var(--critical)' : 'var(--series-1)');
    s += `<rect x="${R2(x)}" y="${top}" width="${R2(sw)}" height="${H}" fill="${col}"
            opacity="${lit ? 1 : (overLimit ? .2 : .12)}"/>`;
  }
  for (const tk of c.ticks) {
    const x = (tk - c.min) / (c.max - c.min) * W;
    s += `<line x1="${R2(x)}" y1="${top + H + 2}" x2="${R2(x)}" y2="${top + H + 6}"
            stroke="var(--text-muted)" stroke-width="1"/>`
       + `<text class="g-num" x="${R2(x)}" y="${top + H + 16}" text-anchor="middle"
            style="font-size:9px">${tk}</text>`;
  }
  const txt = c.value == null ? '—' : c.value.toFixed(c.dec);
  s += `<text class="g-label" x="0" y="9">${c.label}</text>`
     + `<text class="g-val" x="${W}" y="11" text-anchor="end"
          style="font-size:15px;fill:${litCol}">${txt}<tspan class="g-unit"
          dx="4">${c.unit}</tspan></text>`;
  return `<svg viewBox="-13 0 ${W + 26} ${top + H + 22}"
    width="${W + 26}" height="${top + H + 22}">${s}</svg>`;
}
```

The `-13` viewBox origin and `W + 26` width are not arbitrary: the first and last tick
labels are centred on x=0 and x=W and would otherwise be clipped in half. The first
draft rendered `40` as `|0` and `130` as `13`. **CONFIRMED** by rendering.

Label left, value right, on one baseline above the bar. That right-aligned value
column is what lets a stack of these read as an instrument panel — see §7.

---

## 5. Warning lamp row

### 5.1 Colour hierarchy

**ISO 2575 §5.1**, verbatim and identical in the 2004 and 2021 editions — **CONFIRMED**
against the standard's free preview, which includes clauses 1–5:

> — **red:** danger to persons or very serious damage to equipment, immediate or imminent;
> — **yellow or amber:** caution, outside normal operating limits, vehicle system
> malfunction, damage to vehicle likely, or other condition which may produce hazard in
> the longer term;
> — **green:** safe, normal operating condition (where blue or yellow is not required).

§5.4 adds white where none of the above applies. UN R121 §5.4.2 binds any telltale not
in its own Table 1 to exactly this clause.

The cleanest statement of the underlying logic is in **UN R13-H §5.2.21.1.1–.2**, which
distinguishes a **red** signal for failures that "preclude achievement of the prescribed
service braking performance" from a **yellow** signal for "an electrically detected
defect within the vehicle braking equipment, which is not indicated by the red warning
signal". In one line: **red = the primary function is lost. Amber = an assist layer over
an intact primary function is lost.** Apply that test to your own channels and the tier
assignment stops being a judgement call.

| colour | R121 Table 1 examples |
|---|---|
| **red** | oil pressure (10), coolant temperature (11), charging condition (12), seat belt (21), hazard (6) |
| **amber** | engine OBD / MIL (30), ABS (26), fuel level (9), rear fog (8), brake lining wear (37) |
| **green** | direction indicators (5), passing beam (2), front fog (7) |
| **blue** | main beam (3) — reserved |

> **The MIL is amber. It is never red under R121** (item 30, "Engine on-board
> diagnostics or engine malfunction", colour Yellow). Also beware the near-neighbour:
> **ISO 7000-0640** is the check-engine engine-block silhouette; **ISO 7000-1371**
> ("engine failure") is a different glyph — a rounded flask outline with an exclamation
> mark — and is *not* the check-engine light.

For a diagnostic dashboard this maps onto the `barState` tiers: `crit` → red, `warn` →
amber, `ok` → unlit. Do not invent a fifth colour. Do not use green for "ok" on a
channel with no operational meaning — an always-green lamp is noise, and it spends the
one colour that means "this is actively doing something".

Two things worth knowing before copying conventions wholesale:

- **FMVSS 101 does not mirror ECE.** Its Table 1 specifies **no colour at all** for oil
  pressure, coolant temperature, charge or fuel level, permits **words instead of
  symbols** ("Oil", "Temp", "Volts or Charge or Amp"), and gives no symbol for brake
  malfunction — only the word "Brake". This is why a US-market E36 carries *printed text
  panels* reading `CHECK ENGINE`, `ABS`, `BRAKE FLUID` and `PARK BRAKE` rather than
  pictograms. That is a regulatory route, not a BMW styling choice.
- **UN R121 §5.5.1.6:** "Unless prescribed in a specific Regulation, the colour
  requirements regarding tell-tales do not apply when tell-tales appear in a common
  space." In a shared digital display — which is what you are building — the ECE colour
  mandates formally lapse. Follow them anyway; they are good design.

### 5.2 Grouping and ordering

**No standard prescribes where telltales physically sit.** FMVSS 101 and UN R121 were
both read end to end for any provision on rows, left/right, or severity ordering, and
every location requirement is of the form "must be visible when activated" or "the
identifier must be adjacent to the thing it identifies" (R121 §5.1.2, FMVSS 101 S5.1.2).
The sole hard placement rule in either regime is for the passenger-airbag-off telltale.
The common claim that clusters put red centrally and amber peripherally is an **emergent
design heuristic, not a documented convention** — no authoritative source for it was
found. Do not cite it as a rule.

Where a documented priority scheme *does* exist is for **shared pixels**, which is
exactly your situation, and it is worth copying:

- **FMVSS 101 S5.5.5** — a privileged set (brake malfunction, airbag, low tyre pressure,
  ESC, passenger airbag off, high beam, turn signal, seat belt) **must displace any other
  symbol or message** while its condition exists.
- **S5.5.4** — when two or more are active, messages must be "repeated automatically in
  sequence" or driver-selectable.
- **S5.5.6(b)** — those, and anything required to be red, **must not be cancelable**
  while the condition persists.
- **R121 §5.5.1.3–.5** mirrors this for a narrower set.

Translated into this dashboard: a critical channel must be able to take over shared
display space, must not be dismissible while it is still critical, and when several are
critical they cycle rather than fight for the same slot.

**What the E36 itself does** — from the factory owner's manual figure (P/N 01 41 9 790
377, 07/98) cross-checked against the ECE Electrical Troubleshooting Manual connector
lists — **CONFIRMED**:

- **Top-centre pod, between speedometer and tachometer:** battery/charge (red) · main
  beam (blue) · oil pressure (red)
- **Upper flanks:** left turn arrow between fuel gauge and speedo; right turn arrow
  between tacho and coolant gauge
- **Bottom strip, full width under all four dials:** fog · `CHECK ENGINE` · automatic
  transmission (yellow) · seat belt (red) · `ABS` · brake warning (red) with printed
  `BRAKE FLUID` / `PARK BRAKE` legends · airbag (red)
- Low-fuel warning is a pictogram *inside* the fuel dial, not a strip position

Two facts from the ECE wiring that will not show up in a US manual: the **seat belt
telltale is market-specific** (X17 pin 14, "USA, Canada and Gulf countries"), and the
ECE cluster harness has **no MIL pin at all** — the petrol check-engine lamp is a
US/OBD-II feature, and the ECE car gets a *catalytic converter overtemperature* lamp
(X16 pin 26) in its place.

Whatever order you choose: **one row, a fixed slot per lamp that stays occupied (dark)
when unlit, and never reflow it.** A lamp that moves when its neighbour lights is a lamp
whose position you cannot learn, and position is how telltales are actually read.

### 5.3 Implementation

24×24 viewBox, stroke-based, colour by state, dark but present when off.

```js
const LAMPS = {
  coolant: `<path d="M9.5 3.6a2.1 2.1 0 0 1 4.2 0v7.9a3.6 3.6 0 1 1-4.2 0z"/>
    <path d="M11.6 8.4v5.6" stroke-width="1.3"/>
    <path d="M2 17.4c1.2 0 1.2 1.5 2.4 1.5s1.2-1.5 2.4-1.5M15.4 17.4c1.2 0 1.2 1.5 2.4 1.5s1.2-1.5 2.4-1.5"/>
    <path d="M2 21c1.2 0 1.2 1.5 2.4 1.5S5.6 21 6.8 21M15.4 21c1.2 0 1.2 1.5 2.4 1.5S19 21 20.2 21"/>`,
  battery: `<rect x="2.5" y="7" width="19" height="12" rx="1.2"/>
    <path d="M7 7V4.8h3.2V7M13.8 7V4.8H17V7"/>
    <path d="M6.2 13h3.6M15 13h3.6M16.8 11.2v3.6"/>`,
  oil: `<path d="M2.6 16.6v-4.4a1 1 0 0 1 1-1h4.1l2.6-2h7.4a3 3 0 0 1 3 3v4.4z"/>
    <path d="M7.4 11.2 3.4 6.9h4.6l1.4 1.6"/>
    <path d="M12.4 20.3a1.7 1.7 0 0 1-3.4 0c0-1 1.7-2.9 1.7-2.9s1.7 1.9 1.7 2.9z"/>`,
  mil: `<path d="M2.6 15.4v-4.6h1.8V8.9h2.3v1.9h1.7V7.4h4.9l2.4 3.4h1.9V8.9h3.8v6.5h-1.9v2.3h-4.6l-2.2-2.3h-1.7v2.3H8.7v-2.3H6.4v2.3H4.4v-2.3z"/>
    <path d="M10.1 10.3v1.7M12.9 10.3v1.7"/>`,
  brake: `<circle cx="12" cy="12" r="5.4"/>
    <path d="M12 8.6v4.2M12 15.2v.9" stroke-width="1.5"/>
    <path d="M4.6 7.2a8.4 8.4 0 0 0 0 9.6M19.4 7.2a8.4 8.4 0 0 1 0 9.6"/>`,
  abs: `<circle cx="12" cy="12" r="7.4"/>
    <path d="M3.2 7.4a9.6 9.6 0 0 0 0 9.2M20.8 7.4a9.6 9.6 0 0 1 0 9.2"/>
    <text x="12" y="15.2" text-anchor="middle" font-size="6.2" font-weight="700"
      fill="currentColor" stroke="none">ABS</text>`,
  link: `<path d="M3.5 18.5V9.2M8 18.5V5.5M12.5 18.5v-6.2M17 18.5V7.4M21 18.5v-11"/>`,
};

function lamp(name, state) {          // 'off' | 'warn' | 'crit'
  const col = state === 'crit' ? 'var(--critical)'
            : state === 'warn' ? 'var(--warning)' : 'var(--text-muted)';
  const on = state !== 'off';
  return `<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="${col}"
    stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"
    style="opacity:${on ? 1 : .22};${on ? `filter:drop-shadow(0 0 5px ${col})` : ''}"
    role="img" aria-label="${name} ${state}">${LAMPS[name]}</svg>`;
}
```

Glyph notes: the coolant lamp is a thermometer over **two rows of two waves** (the
waves are what distinguishes coolant temperature from ambient/ice warnings); the
battery is a box with two terminal nubs and explicit `+` / `−`; the oil lamp is a can
with the spout pointing **up-left** and a falling drip; `mil` is the ISO engine-block
silhouette. `link` is not a standard telltale — it is a signal-bars glyph for K-line
health, which for this tool is more useful than half the real ones.

The `drop-shadow` on lit lamps is the one place bloom is unambiguously correct: a real
telltale is a bulb behind a translucent panel and it genuinely blooms. See §7.

**Bulb check.** Real clusters illuminate every telltale for a few seconds at ignition-on
so you can see a failed bulb. Worth mimicking on connect — light the whole row for
~1.5 s, then drop to real state. It also proves your own rendering works, which is the
same reason the car does it.

---

## 6. Typography for instruments

You are already on monospace throughout, which is most of the battle. The rest:

**Tabular figures, always.** `font-variant-numeric: tabular-nums` on every readout.
Monospace mostly gives you this, but the property also fixes proportional fallback
fonts and costs nothing. Without it, a value flicking between `1.00` and `13.69`
changes width and the whole readout jitters — the single most amateur-looking thing a
live dashboard can do.

**Reserve the width, do not let it grow.** Tabular figures fix per-glyph width but not
digit count. `9.8` → `13.7` still shifts a centred readout. Either right-align the
value (as `linearBar` does) or pad to a fixed field width.

**Unit placement and weight.** The unit is not part of the number. Smaller (roughly
35–40% of the value's size), muted colour, letter-spaced, and set *after* the value
with a small gap. `26px` value / `9px` unit works on the dial; `15px` / `9px` on a bar.
Never let the unit share the value's colour or weight — the number is the datum, the
unit is a label about it.

**Letter-spacing carries the "instrument" signal.** This is the highest-yield
typographic move available and it costs one line:

| role | size | letter-spacing | case |
|---|---:|---:|---|
| channel label | 8.5–9.5 px | **.20–.22em** | UPPER |
| unit | 9 px | .18em | lower/as-written |
| scale numeral | 12 px | .02em | — |
| big value | 21–27 px | .01em | — |

Wide tracking on small uppercase labels reads as engraved panel legend. Tight tracking
on large numerals reads as a display element. The contrast between the two is what
separates an instrument from a web page — a web page sets everything at the same
tracking.

**Numerals stay upright.** Do not rotate scale numerals to follow the radius. Rotated
numerals are a watch-face convention, not an instrument one; on a 270° sweep they end
up upside-down at the bottom, and every automotive and aviation gauge keeps them
upright.

**Vertical centring on ticks.** `text-anchor="middle" dy="0.34em"` rather than
`dominant-baseline: central`. Both work in current browsers, but `dy` in em units is
bulletproof and scales with font-size. 0.34em centres cap-height (which is what the eye
aligns on for digits), not the em box.

**Do not use a fake LCD font.** You cannot ship one offline without embedding it, and
a 7-segment *shape* drawn in SVG (§8.1) is both more controllable and more honest than
a font that renders letters you never intended.

---

## 7. The serious quality bar

What actually separates a Bosch/VDO/AiM-looking panel from a hobby dashboard, in rough
order of impact:

**1. Restraint with colour.** A professional dash is 90% one colour on black, with a
second colour reserved for alarm. Yours already commits to this — one amber-orange
family. The failure mode is assigning a distinct hue per channel; the instant you have
five hues you have a toy. Colour means *state*, never *identity*. Identity is carried
by position and label.

**2. Derived geometry.** Every radius on the dial in §1.4 comes from a named constant
and every tick from a loop. Nothing is nudged. Nudged layouts have tells: ticks that
do not quite meet the rail, a needle whose tip stops 3px short, numerals at slightly
different radii. These read as sloppiness even when the viewer cannot name what is
wrong.

**3. A real alignment grid.** Cells of equal height, labels on one baseline, values
right-aligned to a shared column. This is why §1.4b moved channel names out of the
dials into cell headers — it produces a horizontal rule across the panel at a constant
y, which is most of what makes a multi-instrument layout look engineered. Wrap each
instrument in an identical cell with a header row and a `1px` `--border` underline.

**4. Density, deliberately chosen.** Serious dashes are dense — they fit a lot in
because the operator is scanning, not browsing. But density comes from tight, even
gutters and small labels, not from cramming. Pick one gutter (9–14px) and use it
everywhere, including inside cells.

**5. Bezel and inset treatment: almost none.** This is where hobby dashboards go
wrong most visibly. No brushed-metal gradients, no chrome rings, no inner glow, no
drop shadows under cells. The entire skeuomorphic budget on the gauge in §1.4 is **one
1px ring at radius 97** in `--border-lit`, plus the panel-coloured hub disc. That ring
does real work — it closes the composition and separates the instrument from the cell —
and anything beyond it starts to look like a 2008 iOS app. Depth on a modern dash comes
from *value* (panel `#0d0906` against page `#000000`) and hairline borders, not from
bevels.

**6. Glow, precisely targeted.** Bloom is correct where a real light source exists and
wrong everywhere else:

| where | verdict |
|---|---|
| lit warning lamp | **yes** — it is a bulb behind plastic |
| needle | **yes, subtle** — `drop-shadow(0 0 4px rgba(224,82,26,.55))`, backlit pointer |
| large digital value | yes, very subtle, as your existing `--glow` does |
| scale numerals, tick marks | **no** — blurs the thing whose job is precision |
| cell borders, panel edges | **no** — instantly reads as a gaming peripheral |
| everything at once | **no** — if it all glows, nothing does |

The tell for cheap glow is uniform application. Real backlighting has a source; if your
glow does not model one, drop it.

**7. Never let the layout move.** Fixed cell sizes, fixed lamp slots, fixed value field
widths. Something that reflows on data change cannot be read peripherally, and reading
peripherally is the entire purpose.

**8. Show what you do not know.** The single most credibility-building feature: dim to
`opacity: .32` and show `—` when data is stale. Hobby dashboards show the last value
forever; instruments tell you the channel is dead. This is also the point made in
`DASHBOARD_RESEARCH.md` §1.1 about your logs' dead air.

---

## 8. Digital readouts

### 8.1 7-segment in SVG

Seven hexagonal polygons per digit with mitred ends, driven by a bitmask. No font, no
external asset, crisp at any size.

Bit order `a…g` = bits 0…6, with segments laid out:

```
     aaaa
    f    b
    f    b
     gggg
    e    c
    e    c
     dddd
```

```js
const SEG_MAP = {
  '0':0b0111111,'1':0b0000110,'2':0b1011011,'3':0b1001111,'4':0b1100110,
  '5':0b1101101,'6':0b1111101,'7':0b0000111,'8':0b1111111,'9':0b1101111,
  '-':0b1000000,' ':0
};

function segDigit(mask, ox, W, H, T) {
  const ht = T / 2, g = ht * 0.55;                  // g = gap between segment ends
  const xl = ox + ht, xr = ox + W - ht, yt = ht, ym = H / 2, yb = H - ht;
  const hz = (yc, x0, x1) =>
    `${R2(x0)},${R2(yc)} ${R2(x0+ht)},${R2(yc-ht)} ${R2(x1-ht)},${R2(yc-ht)} `
  + `${R2(x1)},${R2(yc)} ${R2(x1-ht)},${R2(yc+ht)} ${R2(x0+ht)},${R2(yc+ht)}`;
  const vt = (xc, y0, y1) =>
    `${R2(xc)},${R2(y0)} ${R2(xc+ht)},${R2(y0+ht)} ${R2(xc+ht)},${R2(y1-ht)} `
  + `${R2(xc)},${R2(y1)} ${R2(xc-ht)},${R2(y1-ht)} ${R2(xc-ht)},${R2(y0+ht)}`;
  const segs = [
    hz(yt, xl + g, xr - g),   // a
    vt(xr, yt + g, ym - g),   // b
    vt(xr, ym + g, yb - g),   // c
    hz(yb, xl + g, xr - g),   // d
    vt(xl, ym + g, yb - g),   // e
    vt(xl, yt + g, ym - g),   // f
    hz(ym, xl + g, xr - g),   // g
  ];
  return segs.map((p, i) =>
    `<polygon points="${p}" opacity="${(mask >> i) & 1 ? 1 : 0.09}"/>`).join('');
}

function sevenSeg(text, opt = {}) {
  const o = Object.assign({ W:11, H:19, T:2.6, adv:3.4, dotW:4,
                            color:'var(--series-1)', h:30 }, opt);
  let x = 0, out = '';
  for (const ch of String(text)) {
    if (ch === '.') {                       // DP tucks against the previous digit
      out += `<rect x="${R2(x - o.adv + 0.6)}" y="${R2(o.H - o.T)}"
                width="${o.T}" height="${o.T}"/>`;
      x += o.dotW; continue;
    }
    out += segDigit(SEG_MAP[ch] ?? 0, x, o.W, o.H, o.T);
    x += o.W + o.adv;
  }
  const w = Math.max(String(text).endsWith('.') ? x : x - o.adv, 1);
  return `<svg viewBox="0 0 ${R2(w)} ${o.H}" height="${o.h}"
    width="${R2(o.h * w / o.H)}" fill="${o.color}">${out}</svg>`;
}
```

**The 0.09-opacity unlit segments are the whole trick.** They make it a display with
elements rather than glowing shapes on black. A consequence worth knowing: a blank
`' '` renders as a ghost `8`, which is exactly right for a fixed-width field — it holds
the position visibly, like a real LCD. `sevenSeg(' 940')` renders a ghost leading digit;
that is a feature, not a bug.

The mitred hexagons matter too — plain rectangles read as a progress bar, the 45° ends
read as a segment display.

Verified: `sevenSeg('13.69')` produces 28 polygons (4 digits × 7) plus 1 decimal-point
rect, viewBox `0 0 58.2 19`. **CONFIRMED**

### 8.2 Which channels want a pointer and which want a number

The human-factors distinction is between **quantitative reading** (what is the exact
value?) and **check reading / qualitative reading** (is it normal? which way is it
moving? how fast?). A moving pointer against a fixed scale wins decisively at the
second — position and rate are perceived pre-attentively, without reading — and loses
at the first. A digital readout is the reverse: exact, and useless for trend, because
you cannot see rate of change in a number that updates once a second.

Applied to your five channels:

| channel | primary form | why |
|---|---|---|
| **rpm** | **analogue dial** | Pure rate-of-change channel. The exact figure almost never matters; how fast it is rising, and whether it is near redline, is the entire content. This is the textbook case for a pointer. |
| **coolant temp** | **bar + number** | Check-reading channel. You care about "normal / warming / too hot" and the crossing of 110. Slow-moving, so a pointer's trend advantage is worthless. Keep the number for the warm-up-rate work in `DASHBOARD_RESEARCH.md` §5.3. |
| **intake air temp** | **bar + number**, or plain number | Slowest channel, least dramatic, and 0.65 °C quantisation means the pointer would step visibly. Lowest priority on the panel. |
| **battery volts** | **number, with a thin bar** | Precision channel: 13.69 vs 13.7 is the difference between a reading and a rounding. A dial cannot show 0.01 V and its warning zone would swallow 40% of the face (§4.1). Two decimals, always. |
| **injection load (ms)** | **bar + number** | Genuinely both — it is the best engine-load proxy so you want to see it move, but you also want to read it (idle ≈ 2.8 ms). A linear bar beside the tach gives rate; the number gives the value. |

The general rule: **give a channel a pointer when its derivative is the information.**
rpm and load have informative derivatives. Coolant, IAT and battery do not, on a 1 Hz
link.

Every analogue gauge here also carries its digital co-readout under the hub, so you
never have to choose — which is exactly what modern race dashes do, and why §3.6 rule 1
(smooth the needle, never the number) matters.

---

## 9. Channel specifications

Drop-in configs. Display ranges follow §1.3 and are deliberately narrower than the
sensor ranges.

```js
const GAUGES = {
  rpm: {
    min: 0, max: 7000, majorStep: 1000, minorStep: 250,
    startAngle: 225, sweep: 270,           // full 270°, the primary instrument
    numFmt: v => v / 1000, note: '×1000', unit: 'rpm', dec: 0,
    zones: [{ from: 6000, to: 7000, color: 'var(--critical)', hot: true }],
    smoothTime: 0.18,                      // fast channel
  },
  coolant_temp: {
    min: 20, max: 130, majorStep: 20, minorStep: 5,
    startAngle: 235, sweep: 250,
    unit: '°C', dec: 1,
    limits: { warnHi: 110, critHi: 120 },
    segments: 22,                          // 5 °C per segment vs 0.65 °C sensor step
    smoothTime: 0.8,                       // slow channel; also kills quantisation step
  },
  intake_air_temp: {
    min: -20, max: 80, majorStep: 20, minorStep: 5,
    unit: '°C', dec: 1,
    limits: { warnHi: 70 },
    segments: 20,
    smoothTime: 1.0,
  },
  battery: {
    min: 11, max: 15.5,                    // NOT 8–16; see §4.1
    unit: 'V', dec: 2,
    limits: { critLo: 12, warnLo: 13, critHi: 15 },
    segments: 24,
    smoothTime: 0.5,
  },
  load: {
    min: 0, max: 16, majorStep: 4, minorStep: 1,
    unit: 'ms', dec: 2,
    segments: 24,
    smoothTime: 0.25,
  },
};
```

> **Battery limits are only valid with the engine running.** 12.4 V is a healthy
> resting battery and a failing alternator. Gate the alarm on rpm:
> ```js
> const running = live.rpm > 400;
> const battLimits = running ? {critLo:12, warnLo:13, critHi:15} : {};
> ```
> Without this gate the panel screams every time you switch the ignition on, and an
> alarm that is wrong at startup is an alarm nobody reads. This is the same
> cry-wolf problem as `DASHBOARD_RESEARCH.md` §6.

**Recommended layout.** Tachometer large on the left as the primary instrument;
coolant as a second dial or arc bar beside it; battery, load and IAT as a stacked
column of linear bars on the right; telltale row across the bottom. That is one
pointer for the channel that needs one, one check-reading dial, and three compact
quantitative readouts — and it fits the existing `.tiles` grid width.

---

## 10. Wiring it into `dashboard.html`

The existing `poll()` already fetches `/api/state` at 1 Hz and calls `renderLive()`.
Two changes:

**Build the instruments once**, not on every poll. The current `renderLive()` rebuilds
`#tiles` with `innerHTML` each second; doing that to a gauge destroys the SVG node the
animator holds a reference to, and the needle would reset every second.

```js
let INSTRUMENTS = null;

function buildPanel() {
  const box = $('#panel');
  box.innerHTML = SENSORS.map(s => `
    <div class="cell" data-key="${s.key}">
      <div class="cell-h">${s.label}</div>
      ${s.key === 'rpm' ? gauge({...GAUGES.rpm, value: null, label: s.label})
                        : linearBar({...GAUGES[s.key], value: null, label: ''})}
    </div>`).join('');
  INSTRUMENTS = {
    rpm: Needle(box.querySelector('[data-key="rpm"] svg'), GAUGES.rpm),
  };
}

function updatePanel(live, connected) {
  const stale = !connected || !live;
  for (const s of SENSORS) {
    const cell = $(`#panel [data-key="${s.key}"]`);
    cell.classList.toggle('stale', stale);
    const v = stale ? null : live[s.key];
    if (INSTRUMENTS[s.key]) INSTRUMENTS[s.key].sample(v);      // animated
    else cell.lastElementChild.outerHTML =                     // bars: cheap redraw
      linearBar({...GAUGES[s.key], value: v, label: ''});
  }
}
```

Add `<div id="panel" class="tiles"></div>` to the markup, call `buildPanel()` once in
`init()`, and call `updatePanel(s.live, s.connected)` from `poll()` next to the
existing `renderLive(s.live)`. `buildPanel()` must also run on `resize` **only if** you
size instruments in pixels — the SVGs here scale from their viewBox, so they do not
need it, unlike `lineChart()`.

Bars can be rebuilt wholesale each second — they are discrete and have no animation
state, so there is nothing to lose. Only the needle needs a persistent binding.

**Stale detection.** `connected` alone is not enough; the link can be up while the DME
returns nothing (which per `sensors.py` is exactly what happens with ignition on and
the engine not running — all those addresses read `0x00`). Track the timestamp of the
last differing sample and treat >2.5 s as stale.

---

## 11. Build checklist

- [ ] One angle convention, documented at the top of the file (§1.1)
- [ ] Every radius a named constant; every tick from a loop (§1.4)
- [ ] Display ranges chosen, not copied from sensor ranges (§1.3, §9)
- [ ] No warning zone wider than ~25% of a sweep (§4.1)
- [ ] Channel labels outside the dial, in cell headers (§1.4b)
- [ ] `smoothTime ≤ 0.25 s` on every channel at 1 Hz (§3.4)
- [ ] Needle smoothed; digital readout never smoothed (§3.6)
- [ ] Needle clamped to the observed sample envelope (§3.5)
- [ ] `null` hides the needle and dims the instrument — never parks it at zero (§3.6)
- [ ] `font-variant-numeric: tabular-nums` on every readout (§6)
- [ ] No `font-size` presentation attributes on elements with a CSS class (§1.5)
- [ ] Glow on needle and lamps only (§7)
- [ ] Exactly one bezel ring; no gradients, bevels or shadows (§7)
- [ ] Battery limits gated on `rpm > 400` (§9)
- [ ] Fixed lamp slots; the row never reflows (§5.2)

---

## 12. Sources and verification

**Verified here.** All geometry, tick counts, arc flags, easing behaviour, overshoot
measurements and rendered output were produced by executing the code in this document
— Node 24 for the numerical work, Chrome headless for rendering and DOM behaviour. The
figures in §1.1, §1.3, §3.3, §3.4, §3.5 and §8.1 are measurements, not estimates.

**Standards and conventions** (colour hierarchy, telltale grouping, upright numerals) —
ISO 2575 *Road vehicles — Symbols for controls, indicators and tell-tales* and
UNECE Regulation No. 121. Described from widely-documented convention; the standards
text itself was not consulted, hence **LIKELY** rather than **CONFIRMED**.

**Human-factors basis for §8.2** — the quantitative-reading vs check-reading
distinction is standard display-design material (Sanders & McCormick, *Human Factors in
Engineering and Design*; Wickens, *Engineering Psychology and Human Performance*), which
consistently finds moving-pointer displays superior for rate and deviation judgements
and digital displays superior for precise value reading.

**Critically damped smoothing** — the closed-form solution in §3.3 is the standard
critically-damped-spring formulation popularised by Thomas Lowe, "Critically Damped
Ease-In/Ease-Out Smoothing", *Game Programming Gems 4*, and used by Unity's
`Mathf.SmoothDamp`. The version here uses `Math.exp` directly instead of that article's
polynomial approximation.

**Related documents in this repo** — `DASHBOARD_RESEARCH.md` (§1.1 stale data, §5.3
warm-up rate, §6 alarm design), `PROTOCOL_NOTES.md`, `e36obd/sensors.py` (scalings and
quantisation steps quoted in §9).

**Not verified.** The exact E36 tachometer sweep angle (§1.1) — treat 270° as a design
choice, not a reproduction.
