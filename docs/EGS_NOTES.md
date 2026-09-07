# EGS / automatic transmission diagnostics — 1994 E36 318i (M43)

Companion to `PROTOCOL_NOTES.md`. Same labelling rules: **CONFIRMED** (primary
document, or two independent sources), **LIKELY** (one decent source, or a strong
inference from a primary document), **UNKNOWN** (guess — do not act on it as fact).

Compiled 2026-08-09.

Established beforehand and **not re-derived here**: DME is Bosch Motronic M1.7.2,
KWP71, 5-baud slow init at `0x10`, 9600 8N1, keywords `55 00 81`, working. A 5-baud
sweep of `0x00–0x3F` found only `0x10`. DME has stored code 73 (sporadic) and 36
(present).

---

## 0. TL;DR

1. The car has a **GM 4L30-E = BMW A4S 310R (THM-R1)**. **LIKELY** (strong).
2. It **does** have an electronic control module (**EGS**, "Elektronische
   Getriebesteuerung", system generation **EGS 4.xx**) with real, readable,
   erasable fault memory. **CONFIRMED**.
3. The EGS is **wired directly to the 20-pin round under-hood connector**, on the
   **same RXD and TXD wires the DME uses** on a 4-cylinder E36. **CONFIRMED** from
   the BMW E36 Electrical Troubleshooting Manual. No extra connector, no OBD2 port
   needed.
4. Its protocol is **almost certainly not** 5-baud-slow-init KWP71. It is
   **LIKELY BMW DS2** (or the closely-related DS1 / EDIABAS "Concept 1"), which is
   **9600 baud, 8 data bits, EVEN parity, 1 stop bit, and has NO initialisation
   sequence at all** — you just send an addressed frame. Address **LIKELY `0x32`**.
5. Therefore **sweeping `0x40–0xFF` with a 5-baud slow init is low-value**. There is
   a documented, code-level reason a DS1/DS2 module never answers a slow init
   (§4.2). Sweep DS2-style instead — it is far faster anyway.
6. Its road-speed input is its **own sensor on the transmission** (n-ab), *not* the
   DME's vehicle-speed signal. So **DME code 73 does not directly explain a failure
   to upshift** — but see §6.4 for the one indirect path that does exist.
7. Highest-probability physical cause given a fresh valve body: **the EGS output
   speed sensor (n-ab) circuit**, then **the gear-selector (range) switch in the
   centre console**, then **the shift solenoid supply/ground common to MV1+MV2**.
   See §8.

---

## 1. Which transmission?

**A4S 310R (BMW designation) = GM Hydra-Matic 4L30-E, internal BMW/GM name
"THM-R1". LIKELY.**

Evidence:

- The BMW ETK/parts catalogue has a group *"Automatic transmission A4S270/310R"*
  and a group *"Control unit EGS, programmed"* under **E36 318i M43 Europe** and
  **E36 316i M43 Europe** — i.e. the 4-cylinder M43 E36 is catalogued with the
  A4S 270R/310R family and does get an EGS module.
  (bmwfans.info parts catalogue, `318i-M43` and `316i-M43`, Europe.)
- The BMW E36 Electrical Troubleshooting Manual section **2460.2 "Electronic
  transmission control (EGS A4S 310R)"** is headed **"316i, 318i, 318is"**. That is
  a BMW primary document naming the 4-cylinder cars with the A4S 310R.
  **CONFIRMED** for the 316i/318i family; see the caveat below on model year.
- Used-parts listings sell *"Automatic transmission 318i M43 Eh (A4S 310R)"*,
  part 24001422652 (Schmiedmann).
- BMW's own training manual *Electronic Transmission Control* states plainly:
  *"The internal code for the A4S310/270R is 4L30-E"*, and that Hydramatic
  (GM Strasbourg) *"supplies automatic transmissions to BMW for four and
  six-cylinder vehicles"*. **CONFIRMED**.

**No ZF unit is involved.** ZF 4HP22/4HP24 went in 6-cylinder E30/E34/E32-class cars
and the E36 M3; ZF 5HP18 (A5S 310Z) was a 6-cylinder unit. The 4-cylinder E36 is a
Hydramatic car. **CONFIRMED** by the same training manual's transmission tables.

Caveats worth stating plainly:

- **A4S 270R vs A4S 310R.** The number is the input-torque rating in Nm. BMW's own
  parts group is literally titled "A4S270/310R", and BMW's US training manual
  assigns A4S 310R to 92–95 cars and A4S 270R to 96–98 cars. For a **1994** car the
  310R is the expected fit — **LIKELY**, not confirmed for your specific VIN.
  **It does not matter for diagnostics**: both are the same GM 4L30-E, and the
  Baum CS1000 code-reader manual puts **A4S 310R (THM-R1) and A4S 270R (THM-R1)
  both under fault-code system "EGS 4.XX"**, with the *same* code table.
  Read the tag on the transmission case (GM tag, left-hand side) if you want
  certainty.
- **Engine designation.** You wrote M43B16. M43B16 is the 1.6 litre unit fitted to
  the **316i**; the E36 **318i** from 9/1993 got the **M43B18** (1.8). Either way
  both are M43 4-cylinders, both are catalogued with the A4S 270R/310R and an EGS,
  and both appear on the same ETM sheets — so this does not change any answer
  below. Worth resolving from the VIN/engine number at some point.
- **Control-module generation.** BMW's training manual says the A4S 310R used the
  **55-pin TCM, "GS 4.14" (early) / "GS 4.16" (facelift)**, with a *replaceable
  EPROM*. The 1998-dated ETM sheets I could read show an **88-pin** EGS connector
  (X8500, pins up to 88). So a **1994** car very likely has the **55-pin GS 4.1x**,
  and the **pin numbers in §5/§6 below differ between the two**. The *architecture*
  (which signals exist, where the diagnostic lines go) is the same. Treat all pin
  numbers as **LIKELY, cross-check against a 1994-vintage ETM before probing**.

---

## 2. Does it have a serial diagnostic interface at all?

**Yes. CONFIRMED.** Three independent lines of evidence:

1. **BMW E36 ETM, sheet 0670.5 "Diagnostic link — Block diagram".** The block
   diagram of the diagnostic connector D100 lists, as a module hanging on both TXD
   and RXD, *"Electronic transmission control (EGS A4S 310R) — 2460.2"*, alongside
   DME, ABS/ASC, airbag, IKE, ZKE, IHKA etc. Bidirectional arrows both ways.
2. **BMW E36 ETM, sheets 0670.5-01 (TXD) and 0670.5-04 (RXD)** show the EGS control
   unit **A8500** with dedicated **TXD** and **RXD** pins landing on the diagnostic
   connector (see §3).
3. **Baum Tools CS1000 code scanner, BMW manual (Oct 1997)** — a commercial
   handheld reader — has a memory cartridge **OB15-3** whose *"Transmission (EGS)
   System Code U list"* includes **`U 4 = EGS 4.xx, 1992–1995`**, and whose Section 4
   contains a full fault-code table headed *"A4S 310R (THM-R1), A4S 270R (THM-R1) —
   EGS 4.XX"* with **read and clear** functions performed *"to the vehicle
   Diagnostic Connector"*. Same manual elsewhere: the diagnostic socket is *"the 20
   pin diagnostic socket found under the hood"*.

So: this is **not** one of the early-90s units with no readable memory. It has a
numbered fault memory, it is readable and clearable serially, and 1992–1995 cars are
explicitly in scope.

Full EGS 4.XX fault-code table is reproduced in §7 — it is the single most useful
artefact found in this research.

---

## 3. Is it on the 20-pin round connector? (Q4)

**Yes — and on the same two wires as the DME. CONFIRMED** (BMW E36 ETM, sheets
0670.5-01 and 0670.5-04, dated 05/99, model year 1998).

BMW E36 diagnostic architecture is **two-wire, not a single shared K-line**:

| D100 (20-pin round) | Signal | Goes to |
|---|---|---|
| **pin 15** | **RXD** (tester → ECU) | DME `A6000` pin 87 **and** EGS `A8500` pin 87 |
| **pin 17** | **TXD** (ECU → tester) | DME `A6000` pin 88 **and** EGS `A8500` pin 88 — *on 316i / 318i / 318is* |
| **pin 20** | **TXD** | DME + EGS on 320i/323i/328i/M3/diesel; on 316i/318i/318is this is instead the "everything else" line (ABS, airbag, IKE, ZKE, IHKA, …) |
| EGS pin 60 | **PGSP** | programming line, also to D100 |

Two consequences that matter a lot:

- **On a 4-cylinder E36 the DME and the EGS sit on the same TXD wire and the same
  RXD wire.** Whatever physical connection is already talking to your DME is
  *already* physically connected to the EGS. You do not need to move a probe, add a
  connector, or find an OBD2 port. **CONFIRMED** for the 1998 sheet; **LIKELY** for
  1994, since the DME/EGS pairing on one line and everything-else on the other is
  consistent across every source found.
- **Which pin carries DME/EGS TXD differs between 4-cyl and 6-cyl E36** (pin 17 vs
  pin 20). Since your DME already answers, you are on the right pin — just note
  that generic "pin 20 is the DME line" advice is **wrong for a 4-cylinder E36**.
- Because TX and RX are **separate wires**, you should **not** see an echo of your
  own transmitted bytes (unlike a single-K-line car). If your current DME code
  discards echoes, that logic must not be assumed for the EGS either.

Also: the **EGS is powered through the DME main relay** (ETM 2460.2-01: K6300 pin 87
→ X8500 pins 54/55, 1.5 mm² RT/WS), with permanent B+ on another pin. So **ignition
must be ON and the DME relay must have pulled in** for the EGS to answer. If the DME
relay is marginal, the EGS is dead and silent even though the DME (fed elsewhere)
still talks.

---

## 4. What protocol / address? (Q3, Q5)

### 4.1 The answer

**LIKELY: BMW DS2** (or its near-identical siblings DS1 / EDIABAS "Concept 1").
Wire parameters:

- **9600 baud, 8 data bits, EVEN parity, 1 stop bit (8E1)** — note the parity
  difference from your DME's 8N1.
- **No initialisation of any kind.** No 5-baud address, no keyword exchange. The
  bus is considered "connected" from the first byte.
- Frame: `[ECU address] [total length incl. checksum] [payload …] [XOR of all
  preceding bytes]`.
- Reply: `[ECU address] [length] [status] [payload …] [XOR]`, where status
  `0xA0` = OK, `0xA1` = busy, `0xA2` = bad parameter, `0xFF` = invalid command.

**Address: LIKELY `0x32`.** Independent implementations of DS2 name
`AUTOMATIC_TRANSMISSION = 0x32` (e.g. `oleavr/bmw-coding` `ds2.py`, which uses
`MOTRONIC = 0x12`, `AUTOMATIC_TRANSMISSION = 0x32`, `IKE = 0x80`, `LCM = 0xD0`).
This is **LIKELY, not confirmed for a 1994 4-cyl E36** — those implementations were
written against later DS2 cars. Treat `0x32` as the *first* address to try, not the
only one.

**Concrete first probe** (identification request):

```
tx: 32 04 00 36        # addr=0x32, len=4, cmd=0x00 (ECU ident), xor=0x32^0x04^0x00
rx: 32 .. A0 .. ..     # anything starting 32 xx A0 is a live EGS
```

(For comparison, the same request to a DS2 DME is `12 04 00 16` — that is the
documented, widely used DS2 "ECU id" frame.)

### 4.2 Why the 5-baud sweep found nothing — and why extending it is low-value

This is the strongest single finding in this document, and it comes from source
code rather than folklore. In **`uholeschak/ediabaslib`**, `EdInterfaceObd.cs`, the
`CommParameter` "concept" switch implements every protocol EDIABAS speaks to BMW
ECUs. The relevant cases:

| EDIABAS concept | Parity | 5-baud wake address? | Key bytes? | Transmit fn |
|---|---|---|---|---|
| `0x0001` "Concept 1" | **Even** | **no** (`EcuConnected = true` immediately) | no | `TransDs2` |
| `0x0002` KWP1281 | None | **yes** (`ParWakeAddress`) | yes | `TransKwp1281` |
| `0x0003` "Concept 3" | None | **yes** (`ParWakeAddress`) | yes (`0x55` sync detected) | `TransConcept3` |
| `0x0005` **DS1** | **Even** | **no** (`EcuConnected = true`) | no | `TransDs2` |
| `0x0006` **DS2** | **Even** | **no** (`EcuConnected = true`) | no | `TransDs2` |

Your DME is a **Concept 3**-shaped ECU: 9600 8N1, 5-baud wake address, `0x55` sync
byte then key bytes — which is exactly the `55 00 81` you observed at address
`0x10`. **CONFIRMED** by the code path (`TransConcept3` sets 9600/None parity, calls
`SendWakeAddress5Baud(ParWakeAddress, 10)`, then reads and logs *"Baud rate byte:
55"*).

The DS1/DS2/Concept-1 code paths **never call `SendWakeAddress5Baud` at all**. There
is no address at which a DS2 module can be "woken" by a slow init, at any value from
`0x00` to `0xFF`, because slow init is not part of that protocol. A DS2 ECU sitting
on the line during your sweep would see a 200 ms break followed by 8N1 bytes, fail
parity, and stay silent — which is precisely what you observed.

Independent corroboration that E36 non-DME modules speak DS2 over a two-wire link:
*"Your 1994–2000 E36 will need an ADS adaptor to access the ABS and other modules,
which supports the old school RxD and TxD link fitted to those cars… In the case of
BMW, the language is DS2, the interface is 2 wire 9600 baud moving to 1 wire
9600/10400 baud"* (bimmerforums.co.uk, *BMW INPA E36 OBD OBD2 and ADS interfaces
explained*).

**Verdict on Q5:** sweeping `0x40–0xFF` with 5-baud slow init is **not worthless but
is low priority**. Two reasons to keep it as a fallback, not a first move:

- BMW's own wake addresses are all small (`0x01`, `0x10`, `0x11`, `0x12`, `0x17`,
  `0x33`). A BMW module with a slow-init address above `0x3F` would be unusual.
- The DS2 sweep is *cheaper*: a DS2 probe is ~10 bytes and a ~100 ms timeout, so a
  full `0x00–0xFF` sweep takes well under a minute. A 5-baud sweep costs ~2.6 s per
  address in the init alone — the `0x40–0xFF` half is ~8 minutes of the car sitting
  with the ignition on.

Do the DS2 sweep first. If it comes up empty, *then* burn the 8 minutes.

### 4.3 Things that can make a DS2 probe fail even though the module is fine

- **Parity.** 8**E**1, not 8N1. Getting this wrong is silent failure.
- **Ignition on / DME relay closed** — the EGS is fed through it (§3).
- **Idle-line state and inter-byte timing.** EDIABAS carries an explicit
  `ParInterbyteTime` for DS1/DS2 and a `ParRegenTime` between telegrams. If you
  blast frames back to back you may get nothing; leave ≥50 ms between attempts.
- **DTR.** EDIABAS sets DTR for DS2 (`ParSendSetDtr = !HasAdapterEcho`) because a
  genuine BMW **ADS** interface uses DTR as the transmit-direction control. On a
  plain two-wire TX/RX hookup this is irrelevant — but it is the reason forum
  advice insists you "need an ADS interface" for E36 non-engine modules. Your DME
  already works on your hardware, and the EGS is on the same two wires, so the
  electrical layer is probably fine.
- **Do not assume an echo.** Separate RXD/TXD wires (§3) means no self-echo, unlike
  single-K-line DS2 cars where the first N bytes read back are your own.

### 4.4 What is *not* the answer

- Not ISO 9141 / KWP2000 — far too early.
- Not a blink-code / flash-code readout. Nothing in the BMW literature describes a
  blink-code procedure for EGS 4.xx; the CS1000 reads numbers serially.
- Not "proprietary and undocumented" — DS2 is unpublished by BMW but is thoroughly
  reverse-engineered and openly implemented.

---

## 5. EGS wiring / pin map (from BMW ETM)

From ETM sheets 2460.2a, 2460.2-01, 2460.2-04 (**88-pin connector X8500, model year
1998** — a 1994 car is **LIKELY** the 55-pin GS 4.1x with different numbers; the
55-pin numbering is inferable from the fault-code table in §7).

Diagnostic / power:

| X8500 pin | Signal |
|---|---|
| 87 | **RXD** → D100 pin 15 |
| 88 | **TXD** → D100 pin 17 (4-cyl) |
| 60 | **PGSP** programming line → D100 |
| 54, 55 | +12 V from DME main relay K6300 pin 87 |
| 6, 28, 34 | ground |

Inputs:

| X8500 pin | Signal | Source |
|---|---|---|
| 41 | **TI** (injection time = load / fuel-consumption signal) | DME `A6000` pin 17 — same wire that drives the cluster's consumption gauge |
| 40 | **TD** (engine speed) | DME `A6000` pin 80 |
| 46 | **AC** (compressor on) | A/C compressor relay K19 circuit / DME |
| 42 + 14 | **n-ab output-shaft speed sensor**, shielded pair `W8516` via `X8516` | the transmission itself |
| 36, 8, 37, 9 | **gear selector (range) switch S3**, coded 4-line L1..L4 | centre console shifter assembly |
| 18 | **kick-down switch S8507** | under the accelerator pedal |
| 10 | **brake light switch S29** | pedal box |
| 57 | cruise-control module | (318is) |
| 25 | fault/gear display | instrument cluster |
| 85, 86 | CAN-LOW / CAN-HIGH to DME and ABS/ASC | **1998 only** — see §6.2 |

Outputs (all low-side switched by transistors in the EGS, common supply from an
**internal relay in the TCM**):

| X8500 pin | Load (via `X8521`, gearshift unit `Y8505y`) |
|---|---|
| 30 | Solenoid valve **MV1** |
| 33 | Solenoid valve **MV2** |
| 4 | Solenoid valve **MV4** |
| 32 | Solenoid valve **MV5** |
| 5 | Solenoid valve **MV3** (separate supply, X8500 pin 53) |
| 21 | **MVWK** — converter lock-up clutch (separate supply, X8500 pin 22) |
| 52 | common supply feed to MV1/2/4/5 |

Gear-selector switch logic table, straight off ETM 2460.2a (`1` = B+ present at the
corresponding EGS pin):

| Position | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| P | 1 | 1 | 0 | 1 |
| R | 1 | 0 | 0 | 0 |
| N | 1 | 1 | 1 | 0 |
| D | 0 | 0 | 0 | 1 |
| 3 | 0 | 0 | 1 | 1 |
| 2 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 0 |

---

## 6. What inputs does it use to decide when to upshift? (Q6)

### 6.1 Throttle position

**It does NOT have its own throttle sensor. CONFIRMED.**

It receives throttle/load information from the engine side over **dedicated single
wires**, not a bus (on a 1994 car):

- **`DKT` — throttle valve signal.** EGS 4.XX **fault code 55, "Throttle valve
  signal (DKT)", EGS pin 55**, possible causes *"anomalous throttle valve signal /
  break in wiring / short in wiring"*. **CONFIRMED** that this input exists on
  EGS 4.xx. Where it is generated on an M43/M1.7.2 car — DME output vs. a separate
  throttle switch — is **UNKNOWN** from the sources found; on EML-equipped
  6-cylinder cars it comes from the EML. On a cable-throttle M43 the DME is the
  only plausible source.
- **`ti` / `KVA` — injection time (load).** EGS 4.XX **fault code 09, "KVA Signal
  (ti)", EGS pin 9**. In the 1998 ETM this is `A8500` pin 41 ← DME `A6000` pin 17,
  labelled **TI**, and the same wire feeds the cluster's fuel-consumption gauge.
  **CONFIRMED**.
- **`n-mot` / `TD` — engine speed.** EGS 4.XX **fault code 11, "Engine Speed Signal
  (n-mot)", EGS pin 11**; ETM shows `A8500` pin 40 ← DME `A6000` pin 80 (`TD`).
  **CONFIRMED**.
- **Kick-down** is a **direct switch to ground** under the accelerator pedal
  (S8507), not a bus message. EGS 4.XX **code 30 "Kickdown Switch", pin 30, "short
  to ground"**. BMW training manual: *"The kickdown signal is a direct ground input
  to the TCM… used on most BMW vehicles without electronic throttle control."*
  **CONFIRMED**.

### 6.2 CAN

BMW's training manual is explicit that **on earlier EGS systems these signals were
individual wires**, and CAN between DME and TCM arrived with the 1993 E32 740i.
The 1998 ETM sheet does show CAN-LOW/CAN-HIGH between EGS, DME and ABS/ASC on
316i/318i/318is, and the EGS 4.XX fault table has a CAN block (codes 150–158) shown
in parentheses. For a **1994** car, CAN between DME and EGS is **UNKNOWN, probably
absent** — if your fault memory ever returns 150-series codes, that assumption is
wrong.

### 6.3 Speed sensors

**The EGS has its own output-shaft speed sensor (n-ab) and no turbine/input speed
sensor. CONFIRMED.**

- BMW training manual, verbatim: *"4HP22/24 (EH), A4S310/270R: These transmissions
  do not use a Turbine Speed Sensor. The TD signal is used to determine input shaft
  speed. The TD signal is an output signal of the DME control unit."* And: *"All
  BMW electronic transmissions have an output shaft speed sensor… inductive type
  which will generate an AC analog signal to the TCM."*
- ETM 2460.2-01 shows the sensor as item 12 of the gearshift unit `Y8505y`, wired
  through connector `X8516` on a **shielded pair `W8516`** ("shield up to 10 mm in
  front of EGS speed sensor connector") to EGS pins 42 and 14.
- EGS 4.XX **fault code 20: "Transmission rotation speed signal (n-ab) — Stall
  speed signal", EGS pins 14, 20, "No signal / anomalous engine speed signal"**.
- EGS 4.XX **fault code 100: "Speed monitoring — speed ratio n-ab/n-mot not correct
  for gear selected"** — i.e. the module actively cross-checks n-ab against n-mot
  and will act on a mismatch.

So the EGS computes road speed **itself**, from its own sensor at the transmission.
It does **not** consume the vehicle-speed signal that the DME uses.

### 6.4 Can DME code 73 plausibly cause a failure to upshift?

**Not directly. LIKELY no.** Reasoning:

- Code 73 on M1.7/M1.7.1/M1.7.2/M3.1/M3.3 is *"Vehicle Speed Signal (VSS) or TPS"*
  (endtuning BMW code list, which states the DME range it applies to).
- The DME's vehicle-speed input on this platform comes **from the instrument
  cluster** — ETM 1210.19-09 shows DME `A6000` pin 73 wired to instrument cluster
  `A2w` pin 2 ("speedometer output"). That is a completely different signal chain
  from the EGS's own n-ab sensor at the transmission.
- Therefore a bad VSS/cluster speed signal starves the *DME* (cruise, some fuelling
  and EVAP logic) but leaves the EGS's road-speed knowledge intact.

**The one indirect path that does exist — worth taking seriously:** if code 73 is
firing on the **TPS half** rather than the VSS half, then the DME's idea of throttle
position is bad, and the DME is the source of both the **`DKT` throttle signal** and
the **`ti` load signal** that the EGS uses for its shift map. A corrupted or
implausible DKT/ti would produce exactly "shift points wander, sometimes never
reaches the upshift threshold" — and would show up as **EGS code 55 (DKT) and/or
code 09 (KVA/ti)** in the transmission's own fault memory. That is a concrete,
falsifiable hypothesis and it is the main reason getting into the EGS is worth the
effort.

Note code 36 (EVAP valve short to ground, present) is unrelated to shifting.

---

## 7. EGS 4.XX fault-code table — A4S 310R / A4S 270R (THM-R1)

Reproduced from the **Baum Tools CS1000 BMW manual, Section 4** (Oct 1997), system
code `U 4`, applicable **1992–1995**. Pin numbers are for the **EGS control unit
connector**. This is the table to read your codes against once you are connected.

| Code | Fault | EGS pin | Documented causes |
|---|---|---|---|
| 01 | Solenoid, parking/neutral lock | | break / short in wiring, defective valve winding |
| 02 | Program switch (E=pin 2, M=pin 31, S=pin 34) | 2/31/34 | break / short / defective switch |
| 04 | Engine intervention | 4 | break / short in wiring |
| 09 | **KVA signal (ti)** | 9 | break / short in wiring |
| 11 | **Engine speed signal (n-mot)** | 11 | break / short in wiring |
| 20 | **Transmission rotation speed signal (n-ab) / stall speed** | 14, 20 | **no signal**, anomalous engine speed signal |
| 22 | Transmission fluid temperature sensor | 17, 22 | fluid temp too high (>165 °C) |
| 23 | **Shift lever position** | 26 | break / short in wiring, short in sensor |
| 28 | Battery voltage + (terminal 30) | 28 | break in wiring, battery contacts |
| 30 | Kick-down switch | 30 | short to ground |
| 35 | Stop light switch | 35 | break in wiring |
| 37 | Battery voltage + | 37 | voltage out of range |
| 38 | Solenoid valve — converter lock-up clutch | 38 | break / short, defective winding |
| 39 | Stop light switch | 39 | break in wiring |
| 40 | Pressure regulator | 40, 41 | break / short, defective winding |
| 43 | **Solenoid valve 2** | 43 | break / short, defective winding |
| 45 | **Solenoid valve — band** | 45 | break / short, defective winding |
| 48 | **Solenoid valve 1** | 48 | break / short, defective winding |
| 54 | **Ground — solenoid valves** | 54 | break / short, defective winding |
| 55 | **Throttle valve signal (DKT)** | 55 | anomalous throttle valve signal, break / short |
| 100 | **Speed monitoring** | | ratio n-ab / n-mot not correct for gear selected |
| 101 | Downshift lock | | speed too high for intended downshift |
| 102 | Engine over-rev lock in 1st and 2nd | | engine speed 300 rpm above output speed |
| 103 | EPROM error | | damaged EPROM / reinitialise power / replace unit |
| 104 | DKT engine temperature signal | 35 | (diesel/MUX variants) |
| 105 | DKT throttle valve signal | 35 | break / short, anomalous signal |
| 106 | MUX injection rate | | DDE sending faulty injection-rate signal |
| 107 | False code set | | |
| 110 | **EGS control unit not programmed** | | have EGS control unit programmed |
| (150–158) | CAN faults: timeout 1/2, bus monitor, status, throttle valve, load, engine intervention, engine temperature, engine speed | | later CAN-equipped cars only |
| 200–205 | Kickdown not working; sport/manual program not selectable; program cannot be converted (pin 6); no engine deceleration detected (pin 24); brake light / brake light test switch | | |
| 206 | False code set | 25 | |
| 300 | **Diagnostic circuit fault** | | |
| 301 | **EGS voltage supply** | | no voltage to EGS control unit, check wiring harness |

Note the presence of **code 300 "diagnostic circuit fault"** and **code 301 "EGS
voltage supply"** — both of which are exactly the kind of thing that would be
sitting in memory if the module has been electrically unhappy.

---

## 8. Common causes of intermittent 2→3 / 3→4 failure, valve body already replaced (Q7)

### 8.1 Which solenoid does which shift

**CONFIRMED** across multiple transmission-parts vendors and rebuild references
(Global Transmission Parts, CT Powertrain, Cobra, Phoenix, Transmission Parts
Distributors — all listing the same 4L30E / A4S270R / A4S310R part):

- **Shift solenoid "A" = 1-2 and 3-4 shift**, normally open.
- **Shift solenoid "B" = 2-3 shift**, normally closed.

Standard 4L30E energisation pattern (**LIKELY** — generic GM 4L30E, not verified
against BMW's EGS 4.xx strategy specifically):

| Gear | Sol A | Sol B |
|---|---|---|
| 1 | ON | ON |
| 2 | OFF | ON |
| 3 | OFF | OFF |
| 4 | ON | OFF |

This matters for interpreting your symptom:

- **If the car is stuck in 2nd** (no 2-3, and therefore trivially no 3-4), that is a
  **single** failure: solenoid **B stuck ON / stuck closed / not being commanded
  off**, or the B shift valve hanging. One documented description of the failure
  mode: *"If the shift B solenoid fluid port remains closed due to a mechanical
  problem inside the solenoid or the B shift valve is stuck, the transmission will
  not shift into 3rd gear, but there could be an electrical problem as well."*
- **If it genuinely does 2-3 sometimes but never 3-4**, that is solenoid **A**.
- **If both shifts fail independently**, look for something *common* to both:
  the shift-solenoid **common supply** (fed by the **relay inside the TCM** — BMW
  training manual: *"All magnetic valves (except THM R-1 to 12/95) are supplied
  power from an internal relay located in the TCM"*), the **solenoid ground, EGS
  pin 54**, the transmission **case connector / internal harness**, or an input the
  EGS uses to authorise *any* upshift.

Note the "except THM R-1 to 12/95" carve-out: **your car predates 12/95**, so its
solenoid supply is *not* from the TCM internal relay — it is external. Worth
tracing.

### 8.2 Ranked candidate causes, given a fresh valve body and good fluid

**1. EGS output-shaft speed sensor (n-ab) circuit — HIGHEST.**
Inductive AC sensor on a shielded twisted pair, connector `X8516` at the
transmission, in the heat and oil. Without a credible rising road-speed signal the
EGS has no upshift trigger, and its plausibility check (code 100, "ratio n-ab/n-mot
not correct for gear selected") will actively inhibit or abort shifts. Intermittent
by nature: a marginal connector or a chafed shield gives you good behaviour when
cold and nonsense when hot. Sets **code 20** and/or **code 100**. A valve body swap
cannot touch it. Cheap to test: resistance across the sensor (inductive, expect a
few hundred ohms to ~1.5 k), AC millivolts rising with road speed, and wiggle-test
the connector.

**2. Gear-selector (range) switch — HIGH.**
BMW training manual, verbatim: *"The E36 with the A4S270/310R the range switch is
located in the centre console on the selector lever assembly"* — i.e. **not** on the
transmission, so a valve body job never went near it. Same manual: *"Malfunctions
in the range switch or wiring can cause various shifting complaints"*, and *"If the
reading on Status Requests does not match the actual selector lever position, there
will be various transmission malfunctions."* A worn/dirty console switch that
intermittently reports "3" or "2" instead of "D" produces **exactly** "sometimes
won't go past 2nd or 3rd", with no mechanical fault and no fluid symptom. Sets
**code 23 (shift lever position, pin 26)**. Test statically with a multimeter
against the L1..L4 logic table in §5.

**3. Solenoid A / B themselves, or their wiring to the case connector — MEDIUM-HIGH.**
Solenoids are individually replaceable without dropping the valve body (*"pull out
the roll pin and remove the solenoid"*), so a valve body replacement does **not**
guarantee new solenoids — depending on what "valve body replaced" actually included,
the original solenoids may have been carried over. Sets **code 43 (MV2)**,
**code 48 (MV1)**, **code 45 (band)**, **code 38 (TCC)**, or **code 54 (solenoid
ground)**. Test: resistance at the case connector, and back-probe for the EGS's
low-side switching while driving.

**4. Throttle/load signal from the DME (DKT / ti) — MEDIUM, and the one your DME
code 73 could actually explain.** See §6.4. Sets **code 55** and/or **code 09**.

**5. Kick-down switch stuck / shorted to ground — MEDIUM-LOW.**
Direct ground input, pin 30, documented failure mode "short to ground", codes 30 /
200. A permanently-asserted kickdown holds gears far longer than normal and reads
as "won't upshift". Trivial to test at the pedal.

**6. Power supply / grounds — LOW but free to check.**
Codes 28, 37, 301 all exist precisely because this platform suffers from it. The
EGS is fed via the DME main relay. Low or noisy supply produces intermittent
everything. Also generically documented for BMW autos: *"a weak battery (low
voltage) is a common reason a BMW gets stuck in gear."*

**7. Genuine failsafe / emergency program — probably NOT what you have.**
BMW training manual: in failsafe *"the transmission will be shifted into a higher
gear… 3rd or 4th (on a 4-speed)"*, all solenoids de-energised, line pressure
maximum, TCC off. Failsafe locks you in a **high** gear, not a low one. If your car
is stuck in 2nd, that is **not** classic failsafe — it is a live control decision or
a shift-element failure. If it sometimes limps into 3rd/4th and lights the fault
symbol, then failsafe *is* being entered and a code will have been logged.

---

## 9. What to do next

**Step 1 — do not sweep `0x40–0xFF` with 5-baud yet.** The evidence (§4.2) says a
DS1/DS2 module cannot answer a slow init at any address, and the EGS is almost
certainly DS2-family. Park that sweep as a fallback.

**Step 2 — reconfigure the port and do a DS2 sweep on the connection you already
have working.** Same two wires, same connector, ignition on:

- 9600 baud, **8 data bits, EVEN parity, 1 stop bit**.
- For `addr` in `0x00 … 0xFF`: send `[addr] [0x04] [0x00] [addr^0x04]`, wait ~200 ms,
  accept anything that comes back starting with `addr`. Leave ≥50 ms between
  addresses. The whole sweep is under a minute.
- Try **`0x32` first** (LIKELY EGS), and `0x12` as a positive control — if a DS2
  DME answers on `0x12` you have proven the DS2 layer works on your hardware.
- Expect **no echo** of your own bytes (separate RXD/TXD wires) — but log raw bytes
  rather than assuming.

**Step 3 — if the DS2 sweep is empty**, in this order:
1. Confirm the DME relay is pulling in and there is +12 V at the EGS supply pins —
   an unpowered EGS is silent regardless of protocol.
2. Repeat the DS2 sweep with **8N1** (cheap, rules out a parity assumption).
3. Only then spend the ~8 minutes on the 5-baud sweep of `0x40–0xFF`.

**Step 4 — once connected, read the fault memory against §7.** The codes that would
change the diagnosis most: **20** (n-ab speed sensor), **23** (shift lever
position), **43 / 48 / 45 / 54** (solenoids and their ground), **55 / 09** (DKT and
ti from the engine side), **100** (speed-ratio plausibility), **301** (supply).

**Step 5 — physical work, in parallel, without waiting for the bus.**
Highest-probability single physical cause given the valve body has already been
replaced and the fluid is good:

> **The EGS output-shaft speed sensor (n-ab) circuit at the transmission —
> connector `X8516` and its shielded pair.** It is the one input without which the
> module cannot decide to upshift at all, it is intermittent-by-nature, and a valve
> body replacement does not go near it.

Second: **the gear-selector/range switch in the centre console** — verify the L1..L4
pattern in §5 against the actual lever position, wiggling the lever. Third:
**resistance and low-side switching of shift solenoids A (MV1, pin 48) and B (MV2,
pin 43)** at the case connector, plus the solenoid ground on pin 54.

---

## 10. Sources

Primary documents:

- **BMW E36 Electrical Troubleshooting Manual** (05/99, MY1998) — sheets 0670.5-00
  "Diagnostic link block diagram", 0670.5-01 "TXD, pins 17 and 20", 0670.5-04 "RXD,
  pin 15", 2460.2a/2460.2-01/2460.2-04 "Electronic transmission control (EGS A4S
  310R), 316i, 318i, 318is", 1210.19-08/-09 "DME M1.7.3, 4-cylinder M43".
  <https://elektronikabmw.pl/wp-content/uploads/2020/08/1998_BMW_E36_316i_318i_318is_320i_323i_328i_m3_318tds_325td_325tds_schematy_elektryczne_instrukcja.pdf>
- **BMW Training — *Electronic Transmission Control*** (transmission/TCM tables,
  turbine & output speed sensors, range switch, program switch, emergency program,
  solenoid control). <https://www.ge39.com/files/electran1+2.pdf>
- **Baum Tools CS1000 BMW manual**, Oct 1997 — EGS system "U" list and the EGS 4.XX
  fault-code table for A4S 310R / A4S 270R (THM-R1).
  <http://www.motodok.com/Documentation/Files/BMW/cs1000-bmw.pdf>
- **`uholeschak/ediabaslib`, `EdiabasLib/EdiabasLib/EdInterfaceObd.cs`** — EDIABAS
  concept table: Concept 1 / DS1 / DS2 use even parity and no 5-baud init; Concept 2
  / Concept 3 use a 5-baud wake address and key bytes.
  <https://github.com/uholeschak/ediabaslib/blob/master/EdiabasLib/EdiabasLib/EdInterfaceObd.cs>

Secondary:

- <http://bmwfans.info/parts-catalog/E36-Sedan/Europe/316i-M43/L-A/mar1994/browse/automatic_transmission/control_unit_egs_programmed> — EGS control unit catalogued for E36 316i/318i M43 Europe
- <https://www.schmiedmann.com/en/product/2035923-used?product=A36456> — "Automatic transmission 318i M43 Eh (A4S 310R)"
- <https://en.wikipedia.org/wiki/GM_4L30-E_transmission>
- <https://github.com/oleavr/bmw-coding/blob/master/ds2.py> — DS2 framing and `AUTOMATIC_TRANSMISSION = 0x32`
- <https://github.com/handmade0octopus/ds2> — DS2 frame layout, `12 04 00 16` ident request
- <https://www.bimmerforums.co.uk/threads/bmw-inpa-e36-obd-obd2-and-ads-interfaces-explained.85191/> — E36 pre-96 two-wire DS2 / ADS
- <https://www.zroadster.net/forum/viewtopic.php?t=38095> — which modules INPA reads on OBD1 E36 (includes EGS)
- <https://deviltux.thedev.id/notes/ads-interface/> — ADS interface electrical layer
- <https://www.endtuning.com/bmwcodes.html> — M1.7/M1.7.2 code 73 = "Vehicle Speed Signal (VSS) or TPS", code 36 = EVAP canister valve
- <https://globaltransmissionparts.com/4l30e-shift-solenoid/>, <https://www.ctpowertrain.com/2-pc-4l30e-shift-solenoid-kit-a-1-2-3-4-b-2-3-bmw-cadillac-honda-isuzu/> — solenoid A = 1-2 & 3-4, solenoid B = 2-3
- <https://www.planetisuzoo.com/threads/4l30e-shift-solenoids.78447/> — solenoid B stuck / B shift valve stuck = no 3rd
