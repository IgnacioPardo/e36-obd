# BMW E36 318i (1994, M43B16) — Bosch Motronic M1.7.2 / KWP71 over K-line

Research notes. Every claim is labelled **CONFIRMED** (multiple independent sources),
**LIKELY** (one decent source), or **UNKNOWN**. Where a source is BMW-but-not-M1.7.2,
or Motronic-but-not-BMW, that is stated explicitly — do not let a nearby data point
get promoted into a fact.

Compiled 2026-08-09.

---

## 0. URGENT — read this first if you are at the car

The live test reported total silence at addresses `0x12`, `0x11`, `0x10`, `0x01`,
`0x13`, `0x33`, `0x00`, `0x02`, `0x17` across five framings. That pattern (silence
everywhere, including at the address the sources say is correct) points at **wiring,
not protocol**. Three specific things are probably wrong:

### 0.1 You are very likely on the wrong pin

**CONFIRMED.** On the BMW 20-pin round connector, **pin 15 is the L-line (RxD), not
the K-line**. The K-line is **pin 20 (TxD / "TxD1")**, with **pin 17** carrying a
second K-line (**TxD2**). Three independent sources agree pin-for-pin:

| Pin | Signal | Source agreement |
|----:|--------|------------------|
| 1  | TD — engine speed output | pinoutguide, totalcardiagnostics |
| 4  | +12V (term. R) | totalcardiagnostics |
| 7  | Service/oil interval reset | pinoutguide, totalcardiagnostics |
| 14 | +12V battery (term. 30), **always live** | pinoutguide, totalcardiagnostics |
| 15 | **L-line — RxD**, white/yellow | pinoutguide, totalcardiagnostics, deviltux |
| 16 | +12V ignition (term. 15) | pinoutguide, totalcardiagnostics |
| 17 | **K-line — TxD2**, white/violet | pinoutguide, totalcardiagnostics, deviltux |
| 18 | PGSP programming line | pinoutguide |
| 19 | **GND**, brown | pinoutguide, totalcardiagnostics, deviltux |
| 20 | **K-line — TxD (TxD1)**, white/violet | pinoutguide, totalcardiagnostics, deviltux |

So the working hypothesis in the question ("pin 15 is K-line, pin 20 is TXD1") is
**half right**: pin 20 is indeed the main bidirectional diagnostic line, but pin 15 is
**not** a K-line — it is the L-line. If the adapter has landed you on pin 15 and
nothing else, you are on a line the DME only *listens* to and never *talks* on, which
would produce exactly the silence observed.

**Verify with a multimeter before anything else** (see §8.4). With ignition on,
pin 20 (and pin 17) should idle at battery voltage through a pull-up; pin 15 likewise
idles high but is input-only at the ECU.

### 0.2 The pin 7 / pin 8 bridge — CONFIRMED as a real requirement, mechanism LIKELY

**CONFIRMED:** On BMW K-line-era cars, OBD2 socket **pins 7 and 8 are both K-lines**
(BMW uses the SAE-unassigned pin 8 as a second K-line). K+DCAN cables ship with a
switch or solder jumper between 7 and 8 precisely so that one cable can reach modules
that hang off either line; "2007 and older requires pin 7 and 8 to be bridged to work,
2007 and later requires pin 7 and 8 to be separate" (multiple cable vendors/blogs).

**LIKELY (not confirmed):** that your 16→20 adapter routes round pin 20 → OBD2 pin 8
and round pin 17 → OBD2 pin 7 (or the reverse). I could not find an authoritative
pin-by-pin wiring table for the 16→20 adapters — the published references all show it
as an image only, and cheap adapters are known to be miswired ("If you buy some cheap
BMW 20 pin – OBD2 adapters from china they are probably not pinned out correctly").

**Action:** bridge OBD2 pins 7 and 8, or better, ohm out the adapter and find which
OBD2 pin your round pin 20 actually lands on. This is cheap and is the single highest-
probability fix.

### 0.3 The address is 0x10, not 0x12

**CONFIRMED for BMW DMEs on KW71** (see §1). `0x12` is the BMW **DS2** ECU address for
the DME — a *different protocol* — and is almost certainly where that value came from.
It has no documented meaning as a KWP71 5-baud wake address.

### 0.4 Also worth 60 seconds: try DS2 with no init at all

**Speculative, but free to test.** EDIABAS/EdiabasLib's "Concept 1", "DS1" and "DS2"
transports use **no 5-baud init whatsoever** — they set the baud rate, set **EVEN
parity**, mark the ECU connected immediately, and just transmit a telegram
(`EdInterfaceObd.cs`, cases `0x0001`, `0x0005`, `0x0006`; `ParAllowBitBang = false`,
`EcuConnected = true`). If the M43 DME turns out to be a DS2 talker rather than a KW71
talker, a 5-baud init will never produce a byte no matter what address you use.

Cheap test: 9600 baud, **8E1**, no init, send the DS2 identify telegram
`12 04 00 16` (addr 0x12, len 4, cmd 0x00, XOR checksum) and watch for any response.
Confidence that M1.7.2 is DS2: **LOW** — the literature consistently puts Bosch
Motronic DMEs on KW71 and BMW/Siemens units on DS2 — but it costs one minute and
rules out a whole branch.

---

## 1. The 5-baud slow-init address byte

**Answer: `0x10`. Not `0x12`.**

**CONFIRMED** (two fully independent sources, both BMW, both Bosch Motronic):

1. **km5tz.com — BMW E31 850i reverse engineering.** The author instrumented a real
   INPA session against a real BMW DME (Bosch Motronic 1.7, part number decoded from
   the ID strings as `0 261 200 353`) and wrote:
   > "The awakening or addressing process for the DME's takes place at the blistering
   > speed of 5bps (8N1) on the RxD line (or L-Line). A single byte **'0x10'** will
   > awaken DME #1 and **'0x14'** will awaken DME #2 (850i has 2 x DME's)."

   (Mirrored, with the same wording, at `deviltux.thedev.id/notes/kw71-protocol-description/`.)

2. **colinbourassa/libiceblock**, `src/test_utils/kwp71read.cpp`, in a comment that
   names the exact ECU it was tested against:
   ```c
   // This is appropriate for Bosch Motronic 1.2 p/n 0 261 200 156 (E32 BMW 750iL)
   const uint8_t ecuAddr = 0x10;
   KWP71 kwp(4800, LineType::KLine, true);
   ```

**Is `0x12` reported anywhere?** **No.** I found no source anywhere that gives `0x12`
as a KWP71 5-baud wake address, for BMW or anyone else. `0x12` **is** well attested as
the **DS2** protocol ECU address for the Motronic/engine ECU (`oleavr/bmw-coding`
`ds2.py`, ms4x.net's DS2 writeup, and multiple forum sources: "MOTRONIC (Engine ECU) =
0x12, AUTOMATIC_TRANSMISSION = 0x32, IKE = 0x80, LCM = 0xD0"). DS2 is a completely
different, non-5-baud protocol. Conflating the two is the likeliest origin of the
`0x12` in the reference implementation.

**Other BMW KW71 addresses:** `0x14` = second DME (V12 cars only). **LIKELY.**
Addresses for EML and EGS: **UNKNOWN** — every source says KW71 covers DME, EML and
EGS but none publishes the EML/EGS wake bytes.

**Does BMW differ from other Motronic 1.7 users?**

- **Alfa Romeo / Fiat:** `0x10` for Motronic. **CONFIRMED** — `kaihara/kwp71scan`
  (Alfa 155, tested on real hardware) does `bitbang(0x10); // send Motronic address`,
  and the pcmhacking TunerPro MotronicPlugin config is documented as "baud 9600, Ecu
  address 0x10". Fiat/Alfa address conventions also list 0x15 Viscomatic, 0x20 ABS,
  0x80 Airbag — i.e. 0x10 is "the engine" across that family.
- **Volvo (Motronic 4.3/4.4):** `0x10`. **LIKELY** — the Dilemma "Volvo Motronic 4.3"
  document states you send "a 0x10 byte to the port at 5 baud" (note: Volvo's *wakeup*
  mode then replies at an odd 12700 baud; normal-mode KWP71 differs — see §3).
- **Ferrari (Motronic 2.7 / 5.2):** **UNKNOWN** address. libiceblock notes the F355
  Motronic 5.2 "responds to a block 0x3A request with fault code data", i.e. Ferrari
  deviates in *block titles*, not necessarily address.
- **VW/Audi:** effectively **not comparable** — VAG moved to KWP1281 with addresses
  `0x01` (engine), `0x02` (gearbox), `0x17` (cluster). Different protocol family.

**Bottom line: `0x10` is the same across BMW, Alfa/Fiat and Volvo Motronic. There is no
evidence BMW is special here.**

## 2. Init framing — data bits and parity

**Answer: 8 data bits, no parity, 1 stop bit (8N1). CONFIRMED.**

Three independent sources, none derived from each other:

- **libiceblock** `KWP71.h`: `initDataBits() { return 8; }`,
  `initParity() { return 0; }` (0 = none; 1 = odd, 2 = even per
  `BlockExchangeProtocol.h`).
- **km5tz / E31 BMW capture**: "at the blistering speed of 5bps (**8N1**)".
- **kwp71scan** `bitbang()`: start bit low, then exactly 8 data bits LSB-first at
  200 ms/bit, then stop bit high — no parity bit emitted.
- **EdiabasLib** `SendWakeAddress5Baud()` does the same: break for the start bit, then
  `for (int i = 0; i < 8; i++)` bits at ~200 ms, then stop bit. No parity.

Also note all three implementations use **200 ms per bit** (5 baud exactly), send data
**LSB first**, and hold the stop bit for 200 ms (kwp71scan holds a further 190 ms).
EdiabasLib sleeps 180 ms then spins to the exact 200 ms boundary — the tail-spin
matters, `Thread.Sleep`-only timing drifts.

Post-init serial framing is also **8N1** — see §3.

**On the 7-bit-with-parity variants:** those exist in the ISO9141 world (some Fiat and
Marelli units), but no KWP71 source assigns them to Motronic. Trying 7O1/7E1 was
harmless but is not where the answer lies.

## 3. Keyword bytes after the 0x55 sync

**Answer for BMW Bosch Motronic: `55 00 81`, acknowledged with `0x7E`. CONFIRMED for
M1.7 on a BMW; LIKELY for M1.7.2.**

From the km5tz E31 capture (and its deviltux mirror):
> "After sending a wake up command (INPA will try 3 x times before giving up) the DME
> responds by sending **0x55, 0x00, 0x81** on the TxD line to which diagnostics
> responds with **0x7E** (acknowledge)."

`0x7E` is `~0x81`, which matches libiceblock's generic rule exactly:
`isoKeywordNumBytes() = 3`, `isoKeywordIndexToEcho() = 2`,
`isoKeywordEchoIsInverted() = true`. colinbourassa's protocol page independently gives
the KWP-71 defaults as "Keyword bytes: 3 (`55 00 81`)".

So the reference implementation's expectation of three bytes starting with `0x55` is
**correct**, and `55 00 81` specifically is the value a BMW Motronic returns.

**Caveats:**
- The BMW datum above is from a **Motronic 1.7** (M70 V12, 850i), not a **1.7.2**.
  The 1.7.2 is the same protocol generation; **LIKELY** identical, not confirmed.
- Non-BMW Motronics return different keywords — e.g. Volvo M4.3 returns
  `55 AB 02` and is acked with `0xFD`. So do not treat `55 00 81` as universal; treat
  it as "what BMW's units return".
- **Post-init baud rate is ECU-dependent and this is a real trap:**
  - BMW Motronic **1.7 / 1.7.x → 9600** 8N1. **CONFIRMED** (km5tz E31 capture:
    "further communications takes place on the single wire TxD line at **9600bd 8N1**";
    KWP71Diag ships "predefined config to M1.7-M1.7.3 with standard baudrate **9600**").
  - BMW Motronic **1.2 → 4800** (libiceblock's `kwp71read.cpp` constructs
    `KWP71 kwp(4800, ...)` for the E32 750iL).
  - Alfa 155 → 4800 (`kwp71scan` calls `Serial.begin(4800)`).
  So **9600 is right for your car**, but if you ever see a garbled `0x55` rather than
  silence, drop to 4800 before concluding anything.
- `kwp71scan` reads **five** bytes after the 0x55 on Alfa units and echoes `kw2`
  inverted — a reminder that keyword count is not universal either.

## 4. Block titles — standard KWP71 or BMW-specific?

**Answer: BMW uses the STANDARD KWP71 block titles. CONFIRMED for BMW Motronic 1.7,
LIKELY for 1.7.2.**

This is directly readable out of the km5tz INPA capture, where every title lines up
with libiceblock's `KWP71BlockType` enum:

| Title | libiceblock name | Seen in the BMW capture as |
|------:|------------------|----------------------------|
| `0x01` | ReadRAM | `06 D2 **01** 02 00 37 03` — read 2 bytes @ 0x0037 |
| `0x07` | ReadTroubleCodes | `03 D4 **07** 03` — "Inpa req error count" |
| `0x08` | ReadADCChannel | `04 9C **08** 05 03` — read ADC channel 5 |
| `0x09` | Empty / NOP | `03 D0 **09** 03` — keepalive, used constantly |
| `0xF6` | InfoString | `0D 01 **F6** 32 35 33 30 …` — ASCII ID strings |
| `0xFB` | ADCValue | reply to the 0x08 request |
| `0xFC` | BinaryData | reply carrying fault-code data |
| `0xFE` | RAMContent | `05 D3 **FE** 00 00 03` — reply to ReadRAM |

Note the **ReadRAM payload layout is `[count][addr_hi][addr_lo]`**, exactly as
libiceblock (`KWP71::readRAM`) and your `kwp71.py` already build it. Good.

`0x05` EraseTroubleCodes and `0x10` ReadParamData were **not** observed in the capture
— **UNKNOWN** whether M1.7.2 implements them. The E31 author's UI does have a "Read and
Clear DME errors" screen, so `0x05` is **LIKELY** present.

Framing details confirmed by the same capture, all matching your implementation:
- first byte = length = "total message length minus the first byte"
- second byte = a sequence counter incrementing by one **per message**, wrapping at
  0xFF, shared across both directions
- last byte always `0x03`
- no checksum; **every byte except the final `0x03` is echoed back inverted** by the
  receiver
- both sides must alternate; idle side sends `0x09` NOP or the ECU sleeps
- **INPA sends 2 NOP message pairs between each data request**, and the author reports
  that removing them broke the value updates: "I tried removing these to speed things up
  but the values did not update correctly so it appears this protocol must be followed."
  Worth mimicking.

**Known deviation elsewhere:** Ferrari F355 Motronic 5.2 answers fault-code requests on
block `0x3A` instead of `0x07` (libiceblock header comment). No such deviation is
reported for BMW.

## 5. Fault-code format from ReadTroubleCodes

**Answer: a count block first, then one 5-byte record per code. LIKELY (single strong
source, plus a corroborating hint).**

From the km5tz E31 DME capture and the author's DME-emulator source:

```
Inpa sends    03 D4 07 03          request (title 0x07, no payload)
DME ack       FC 2B F8
DME sends     04 D5 FC 00 03       count block: title 0xFC, payload = [count]
Inpa ack      FB 2A 03 FF
```

and then, for each stored code, one further block of title `0xFC` with a **5-byte
payload**:

```
tc1 = [0x08, 0xd5, 0xfc, 0x64, 0x01, 0x80, 0x80, 0x03, 0x03]
#            len   seq  title  |----------- payload -----------|  trailer
# Byte[3] = TC number
# Byte[4] = additional info (bitfield, below)
# Byte[5] = engine RPM at time of fault   (x40 scaling)
# Byte[6] = battery volts at time of fault (0.0681 * x = volts)
# Byte[7] = error frequency
```

The author also annotates a second example showing byte[6] doing double duty in his
notes as temperature (`0x80` = 48 °C, `0x40` = 0 °C, `0xA0` = 72 °C, `0x60` = 24 °C)
and as load signal — i.e. **the freeze-frame bytes' meaning is not fully pinned down.**
Treat bytes 5–7 as **UNKNOWN-ish**; byte 3 (the code number) is solid.

**Byte[4] — fault condition bitfield (can have several bits set):**

| Bit  | Meaning |
|-----:|---------|
| `0x00` | open circuit / error not present / static error |
| `0x01` | short to B+ |
| `0x02` | short to ground |
| `0x04` | not allowed |
| `0x08` | invalid working area |
| `0x10` | exhaust-gas-relevant fault |
| `0x20` | fault stored after re-bouncing delay |
| `0x40` | error present (vs. historic) |
| `0x80` | sporadic error |

**Corroboration:** libiceblock's `KWP71::readFaultCodes` comment says "The FIAT-9141
spec document indicates that the fault code data is arranged in **one 5-byte group for
each code**. This format might hold for other KWP71-supporting ECUs as well." Two
unrelated families landing on 5 bytes/code is reassuring but still not proof for
M1.7.2.

### 5.1 Fault code number → description, DME M1.7 / M1.7.1 / **M1.7.2** / M3.1 / M3.3

**CONFIRMED** (endtuning.com's BMW code database, cross-checked against the M43-specific
list circulating on E36 sites; codes are **decimal**):

| # | Description |
|--:|-------------|
| 1 | Fuel pump relay (EKP) or RPM signal |
| 2 | Idle-speed controller |
| 3 | Injectors (4cyl: 1,3) |
| 4 | Injectors (DME 3.3.1 cyl 4,6) |
| 5 | Injectors (DME 3.3.1 cyl 3,5) |
| 6 | Injectors — general |
| 7 | VANOS relay, or injector cyl 6 (**DME 1.7.2**) |
| 8 | "CHECK ENGINE" light failure (US models) |
| 12 | Throttle position sensor (TPS); lambda sensor on M3.3.1 |
| 13 | Lambda probe |
| 15 | Knock sensor 1 (1.7 / 3.1) or **ignition fault (1.7.2)** |
| 16 | Ignition system, or cam/crank position sensor |
| 17 | Camshaft position sensor |
| 18 | **DISA changeover valve (1.7.2)** |
| 19 | Electric fan output stage |
| 20 | Cruise control |
| 26 | Voltage supply |
| 29 | Idle-speed controller / idle actuator |
| 32 | Injectors (4cyl: 2,4) |
| 36 | EVAP / tank-ventilation canister valve |
| 37 | Oxygen-sensor heater relay |
| 38 | Lambda heater relay |
| 41 | Air mass flow sensor (AFM/MAF) |
| 42 | Speed signal, or knock sensor 2 (1.7.x / 3.3.1) |
| 46 | Electric fan |
| 48 | A/C compressor shut-off |
| 54 | Control-unit voltage supply B+ |
| 55 | Ignition (final stage) |
| 63 | Torque-converter lockup clutch |
| 64 | EGS→DME connection / ignition timing intervention |
| 70 | Oxygen sensor (1.7.x / 3.1) |
| 73 | Vehicle speed signal (VSS), or TPS |
| 76 | Idle CO potentiometer / CO adjust |
| 77 | Intake air temperature sensor |
| 78 | Engine coolant temperature sensor |
| 82 | MSR engine drag torque, or **A/C compressor (1.7.2)** |
| 83 | ASC (EML) |
| 100 | Amplifier/output stage 1 in DME |
| 101 | Amplifier/output stage 2 in DME |
| 200 | DME control unit |
| 201 | Lambda regulation |
| 202 | Control unit |
| 255 | Control unit — internal error |

(The full endtuning table is longer; the above keeps the entries plausible on a 4-cyl
M43. The km5tz author's independently-derived `tclook[]` table agrees on 1, 2, 3, 8,
32, 36, 37, 41, 48, 54, 64, 70, 73, 76, 77, 78, 100, 200, 201 — good cross-validation.)

**Caution:** these are the numbers the *diagnostic protocol* returns. They are **not**
the 1xxx "stomp test" blink codes you see quoted for E36s (1444 etc.), and not OBD-II
P-codes. Do not mix the tables.

## 6. ADC channels — numbering, meanings, scaling

**Mostly UNKNOWN for BMW M1.7.2.** Here is what exists and how far it can be trusted.

### 6.1 What is confirmed about the mechanism

`ReadADCChannel` (`0x08`) takes a **1-byte payload = channel number**
(libiceblock `checkValidityOfBlockAndPayload`: `payload.size() == 1`) and the ECU
replies with title `0xFB` (ADCValue). In the BMW capture:

```
Inpa sends     04 9C 08 05 03        request ADC channel 0x05
DME ack        FB 63 F7 FA
DME sends      (05) 9D FB 00 05 03   reply: title 0xFB, payload 00 05
```

so the ADC value is a **2-byte big-endian** quantity. **CONFIRMED.**

### 6.2 The one BMW ADC channel with a published meaning

**Channel `0x05` = oxygen (lambda) sensor voltage. LIKELY** — single source. The km5tz
emulator line for the "exhaust values" page is
`exm2 = [0x05,0xd3,**0xfb**,0x00,0x40,0x03]  # Lambda sensor (volts) = .00484 * Byte4`
and channel 5 is the only `0x08` request on that page. Note `0.00484 × 1023 ≈ 4.95 V`,
i.e. this is a **10-bit ADC on a ~5 V reference**; the "Byte4" scaling only works while
the high byte is zero. A safer general form is
`volts = ((hi << 8) | lo) * 5.0 / 1023`.

**All other BMW M1.7.2 ADC channel assignments: UNKNOWN.** I could not find a published
channel map.

### 6.3 Circumstantial evidence on channel ordering (do NOT treat as fact)

- The **r3vlimited "Motronic 1.7 DIY Reverse Engineering"** thread, working from the
  8051 firmware rather than the diagnostic protocol, lists the ECU's physical analog
  inputs as: **AN0 = AFM, AN1 = VBATT, AN2 = IAT, AN3 = CTS, AN4 = TPS, AN5 = COPOT,
  AN6, AN7**. These are *hardware ADC pins*. Whether the diagnostic `0x08` channel
  index equals the hardware AN index is **UNKNOWN** — and note it directly contradicts
  §6.2's "channel 5 = lambda" (AN5 = CO potentiometer), so at least one of the two
  mappings does not transfer.
- The **TunerPro MotronicPlugin** definitions (Alfa/Fiat M2.10.3, **not BMW**) use:
  `0x08 0x01` = battery voltage (`X / 14.68` volts, or `0.0681·X + 0.0019`),
  `0x08 0x02` = intake air temperature, `0x08 0x03` = coolant temperature, with these
  polynomials:
  - IAT °C = `-2.01389e-5·x³ + 0.008784722·x² - 1.676875·x + 156.74375`
  - CTS °C = `-1.4482e-5·x³ + 0.006319247·x² - 1.35140625·x + 144.4095455`
  These are **confirmed for Alfa Romeo Motronic**, reproduced identically in
  `kaihara/kwp71scan` from live-car testing. They are **not** validated on BMW and the
  BMW NTC curve may well differ.

**Practical guidance:** rather than guessing ADC channels, use the **RAM reads in §7** —
those are BMW-specific, already scaled, and were captured from a real BMW DME.

## 7. RAM memory-map addresses for live values

**LIKELY for BMW Motronic 1.7 (E31 850i, M70). Transfer to M1.7.2 is UNKNOWN and
should be treated as a starting point for probing, not as truth.**

Captured from a real INPA↔DME session (km5tz). Requests are
`ReadRAM (0x01)` with payload `[count][addr_hi][addr_lo]`; replies come back as title
`0xFE` with the data. Byte 3 of the reply block is the first data byte.

**INPA's "Analog values" page polls these seven, in a repeating loop:**

| Address | Value | Scaling (author's, from emulator calibration) |
|--------:|-------|-----------------------------------------------|
| `0x0036` | Battery volts | `0.0681 × B3` |
| `0x003C` | Engine RPM | `10 × B3` |
| `0x008B` | Road speed (km/h) | `1.102 × B3` |
| `0x0037` | Intake air temperature (°C) | `-33.5 + 0.65 × B3` |
| `0x0038` | Coolant temperature (°C) | `-32.5 + 0.65 × B3` |
| `0x0055` | Ignition angle | `0.75 × (96 - B3)` |
| `0x0040` | Load (ms injection) | `0.05 × B3` |

**INPA's "Exhaust values" page polls five addresses** — `0x009D`, `0x0211`, `0x0207`,
`0x0201`, `0x0262` — plus ADC channel `0x05`:

| Address | Value | Scaling |
|--------:|-------|---------|
| `0x009D` | Air consumption (kg/h) | `0.2 × B3` |
| `0x0211` | Lambda integrator | `B3 - 128` |
| `0x0207` | Adaptation, additive | `B3 - 128` |
| `0x0201` | Adaptation, multiplicative | `B3 - 128` |
| `0x0262` | Adaptation, TEV | `B3 - 128` |
| ADC ch `0x05` | Lambda sensor volts | `0.00484 × B4` (see §6.2) |

(The author's own notes flag the last four as "not sure what Byte4 is" — the
address→meaning pairing for the 0x02xx block is his best inference.)

**Digital values: one read covers them all** — `ReadRAM` **10 bytes @ `0x0020`**:
```
Inpa req    06 28 01 0A 00 20 03
DME sends   0D 29 FE 06 DC FD 00 00 84 00 00 00 04 03
# byte 12: bit 0x20 = lambda control active
# byte 11: bit 0x10 = idle speed status
```
Only two bits are decoded; the rest is **UNKNOWN**.

**Why this may not transfer to M1.7.2:** the E31 unit is an M70 V12 running Motronic
**1.7** with part number `0 261 200 353`. Your M43B16 runs **1.7.2** with a different
part number and a different variable layout. The *protocol* transfers; the *addresses*
plausibly shift. Expect to have to re-find them — but `0x0036`–`0x0040` and `0x008B`
are a sensible first sweep, and a full `ReadRAM` dump from `0x0000` (libiceblock's
example reads 252 bytes from `0x0000`) with the engine idling vs. revving is the
standard way to relocate them.

**Independently:** the r3vlimited E30 thread mentions "RPM descriptor `0x3B`, Load
descriptor `0x40`" — `0x40` for load matches km5tz exactly, and `0x3B` is adjacent to
km5tz's `0x3C` for RPM. Two unrelated reverse-engineers landing within one byte of each
other is a genuinely good sign that this region is stable across the M1.7 family.

## 8. The BMW 20-pin round connector pinout

**CONFIRMED** — see the table in §0.1. Summary of the four pins that matter:

- **K-line: pin 20** (TxD / TxD1), white/violet. This is the bidirectional diagnostic
  line. **Pin 17** is a second K-line (TxD2), same wire colour.
- **L-line: pin 15** (RxD), white/yellow. Unidirectional, tester → car only.
- **+12V battery (always live): pin 14** (term. 30), red. Pin 16 is switched +12V
  (term. 15, ignition); pin 4 is +12V term. R.
- **Ground: pin 19**, brown.
- **TD (engine rotation speed output): pin 1**, black — this is a *tach output*, not a
  data line. Do not connect a UART to it.

### 8.1 Which K-line is the DME on?

**UNKNOWN.** Sources say the two K-lines split the modules — "There are two K lines
(TxD and TxD2), with DME and EGS on one, and everything else on the other" — but they
do not consistently say *which*. Try pin 20 first (it is the one universally labelled
"TxD"/K-line in the pinout tables), then pin 17.

### 8.2 The L-line and the ADS adapter

BMW's own tooling reaches OBD1 modules through an **ADS** ("Aktiven Diagnose Stecker")
adapter, described by users as "one RS232-to-K-line transceiver, plus a switch to route
K-line data to the L-line based on the DTR line of the RS232 port". That is a direct
statement that BMW's factory interface **can and does drive the L-line separately**,
under software control, for exactly the wake-up phase.

Corroborating: "for EU E36 and ///M E36/Z3 cars, older modules with low computing power
need the L line for Rx data"; "if Pin 15 is installed on the 20-pin OBD1 diagnostic
plug, only a fully ADS compatible interface will be able to connect to all modules".

### 8.3 Note that K+DCAN cables usually do NOT drive the L-line

A K+DCAN cable presents OBD2 pin 7 (+ pin 8) K-line and typically leaves OBD2 pin 15
(L-line) unconnected. Cheap **VAG-COM KKL 409.1** cables, by contrast, generally *do*
drive both K and L from the same TXD signal — which is very likely why KWP71Diag's
documentation says it works "with simple VAG COM KKL 409.1 adapter, but only with FTDI
chip". If you end up needing the L-line, a KKL 409.1 may get you there with no
soldering.

### 8.4 Verify with a multimeter — do this, the sources disagree often enough

1. Ignition **on**, engine off. Black probe on **pin 19**; confirm ~0 V and continuity
   to chassis.
2. **Pin 14** should read battery voltage with the key **out**. **Pin 16** should read
   ~0 V key-out and battery voltage key-on. If these two are swapped, your connector
   orientation/numbering is mirrored — stop and re-read the connector.
3. **Pin 20** and **pin 17** should sit at battery voltage (pulled up) with the key on,
   and should *not* be hard-shorted to ground.
4. Ohm out the 16→20 adapter with the car disconnected: buzz round-pin-20 against OBD2
   pins 7 and 8 and record which one it lands on. Do the same for round pin 17 and
   round pin 15.
5. **Pin numbering on the round connector is not obvious.** Confirm it against a
   photo/diagram before trusting any probe reading — mis-indexing this connector is a
   classic multi-hour mistake.

## 9. Does M1.7.2 need the L-line for slow init?

**This is the crux, and the honest answer is: the sources conflict. LIKELY that the
L-line is required on BMW; CONFIRMED that it is not required on other Motronics.**

**Evidence that BMW clocks the address on the L-line:**

- km5tz (real BMW DME, real INPA capture, the best BMW-specific source in this document):
  "the awakening or addressing process for the DME's takes place at the blistering speed
  of 5bps (8N1) **on the RxD line (or L-Line)**. … Since further communications takes
  place on the single wire TxD line … (**RXD is no longer used**)."
- r3vlimited E30 diagnostics thread: "the **L-Line only used for wake-up and initiating
  communication**, followed by handshaking with the K-Line to request data."
- The ADS adapter's design (§8.2) exists precisely to switch the transmit signal onto
  the L-line — you would not build that hardware if the K-line sufficed.

**Evidence that the K-line alone can work:**

- **libiceblock explicitly runs the BMW case on the K-line**: its BMW Motronic 1.2
  (E32 750iL) example constructs `KWP71 kwp(4800, **LineType::KLine**, true)` — the
  library supports `LineType::LLine` and the author chose K for the BMW ECU he tested.
- `kaihara/kwp71scan` bit-bangs the address on `K_TX` only and works on Alfa Motronics.
- colinbourassa's protocol page: "L-line: unidirectional, used for addressing; K-line:
  bidirectional, used for data exchange (**though the K-line can also handle addressing
  if the L-line isn't implemented**)."
- ISO 9141 itself specifies the address is sent on **K and L simultaneously**, which is
  why so many cables tie them together and why the distinction is usually invisible.

**Reconciliation (my read, flagged as inference):** the K-line-works evidence comes from
a Motronic **1.2** and from **Alfa** units; the L-line-required evidence comes from BMW
**1.7-generation** DMEs specifically. Those are not in conflict if BMW's 1.7-era units
only wired their 5-baud receiver to the L-line input. **You should assume you need to
drive pin 15 (L-line) with the 5-baud address while listening on pin 20 (K-line),
and be prepared to also drive pin 20 in parallel.**

Note that **driving both lines simultaneously is the safe default** and is what real
tools do: EdiabasLib's `SendWakeAddress5Baud(value, setDtr, **bothLines**, delay)` takes
an explicit "both lines" flag and passes `true` for its 5-baud (KWP1281) concept.

**Direct consequence for your implementation:** a UART-BREAK bit-bang reaches **only**
the line your transceiver's TX drives. If that is pin 20 and the DME listens on pin 15,
you will get exactly the silence you are seeing, forever, at every address and every
framing. This is consistent with your observed symptoms.

## 10. What EDIABAS/INPA actually does — and its limits as a reference

**CONFIRMED:** `uholeschak/ediabaslib` implements these transports in
`EdiabasLib/EdiabasLib/EdInterfaceObd.cs`: `0x0000` Raw/EDIC, `0x0001` Concept 1,
`0x0002` Concept 2 (ISO 9141 / KWP1281), `0x0003` Concept 3, `0x0005` DS1, `0x0006`
DS2, `0x0110` D-CAN. **There is no KWP71/KW71 concept.** `EdInterfaceAds.cs` is a
73-line stub that only parses the interface name — the ADS path is not implemented.

So: **EdiabasLib cannot tell you how INPA wakes an OBD1 Motronic**, because it does not
do it. That work happens inside BMW's proprietary `ADS32.dll` plus the ECU's SGBD
(`.prg`) file, neither of which is in the repo. **The contents of the M1.7.2 SGBD are
UNKNOWN to me.**

What *is* transferable from EdiabasLib:
- `SendWakeAddress5Baud()` (§2) is a clean, known-good reference for 5-baud timing,
  including the both-lines flag and the sleep-then-spin timing discipline.
- Concept 1 / DS1 / DS2 use **no init at all** and **even parity** (§0.4).
- `Kwp1281InitDelay = 2600` ms — the bus-idle time before an init attempt. kwp71scan
  uses the same `delay(2600)` with the comment "k line should be free of traffic for at
  least two seconds". libiceblock uses `timeBeforeReconnectMs() = 260`. If you are
  retrying init in a tight loop, **2.6 s of idle before each attempt** is the safer
  number.

---

## What to try first

In order. Stop at the first one that produces any byte at all.

**1. Fix the wiring before touching the protocol.** Bridge OBD2 pins **7 and 8** (most
K+DCAN cables have a switch for this; otherwise a jumper). Then confirm with a
multimeter which OBD2 pin your adapter connects **round pin 20** to. You want your
FTDI's K-line on **round pin 20**, ground on **round pin 19**. This alone is the most
likely explanation for total silence.

**2. Then, the single most likely init parameter set:**

| Parameter | Value |
|-----------|-------|
| Wake address | **`0x10`** |
| Init bit rate | 5 baud — 200 ms per bit |
| Init framing | **8 data bits, no parity, 1 stop bit**, LSB first |
| Line to clock the address on | **L-line (round pin 15)**, ideally **K and L together** |
| Bus idle before init | **≥ 2600 ms** |
| Post-init baud | **9600**, 8N1 |
| Expected keyword reply | **`55 00 81`** on the K-line (round pin 20) |
| Your acknowledgement | **`0x7E`** (= `~0x81`), after a short delay |
| Then | ECU volunteers `0xF6` ASCII ID blocks; ACK each with a `0x09` NOP until it sends `0x09` |

**3. If still silent, drive the L-line.** If your cable has no L-line output, wire the
FTDI TX through a second transceiver (or a simple open-collector transistor with the
car's pull-up) onto **round pin 15**, keep RX on **round pin 20**, and repeat step 2.
Per §9 this is the most likely remaining blocker on a BMW 1.7-generation DME.

**4. If you see garbage instead of silence,** you are on the right wire with the wrong
baud — try **4800** as well as 9600 before changing anything else.

**5. Only then start varying the address** (`0x14`, then a sweep) — and drop `0x12`
entirely unless you are deliberately testing the DS2 hypothesis in §0.4, where it is the
*correct* address for a completely different protocol.

---

## Source list

- colinbourassa, *Automotive diagnostic protocols* — https://colinbourassa.github.io/car_stuff/diagnostic_protocols/
- colinbourassa/libiceblock — https://github.com/colinbourassa/libiceblock
  (`src/KWP71.h`, `src/KWP71.cpp`, `src/BlockExchangeProtocol.h`, `src/test_utils/kwp71read.cpp`)
- km5tz, *BMW 850i page 11* — http://www.km5tz.com/BMW%20850iP11.htm  ← the single most valuable BMW-specific source
- halis duraki (deviltux), *KW71 Protocol Description* — https://deviltux.thedev.id/notes/kw71-protocol-description/
- halis duraki, *Keyword Protocols* — https://deviltux.thedev.id/notes/keyword-protocols/
- kaihara/kwp71scan — https://github.com/kaihara/kwp71scan (`scan/scan.ino`)
- uholeschak/ediabaslib — https://github.com/uholeschak/ediabaslib (`EdiabasLib/EdiabasLib/EdInterfaceObd.cs`)
- R3VLimited, *Motronic 1.7 DIY Reverse Engineering* — https://www.r3vlimited.com/board/forum/e30-technical-forums/engine-drivetrain/alternative-tuning-w-a-r-megasquirt-etc/375887-documentary-motronic-1-7-diy-reverse-engineering
- R3VLimited, *Need BMW e30 diagnostic protocol information* — https://www.r3vlimited.com/board/forum/e30-technical-forums/car-audio-electronics/380262-need-bmw-e30-diagnostic-protocol-information
- pcmhacking.net, *MotronicPlugin — TunerPro KWP71 plug-in* — https://pcmhacking.net/forums/viewtopic.php?t=3089 (Cloudflare-protected; consulted via search snippets only)
- EndTuning, *BMW Codes* — https://www.endtuning.com/bmwcodes.html
- PinoutGuide, *BMW 20-pin round connector* — https://pinoutguide.com/CarElectronics/car_diag_pinout.shtml
- Total Car Diagnostics, *About BMW-20 Diagnostic Socket (OBD-1)* — http://www.totalcardiagnostics.com/support/Knowledgebase/Article/View/88/22/
- BimmerForums UK, *BMW INPA E36 OBD/OBD2 and ADS interfaces explained* — https://www.bimmerforums.co.uk/threads/bmw-inpa-e36-obd-obd2-and-ads-interfaces-explained.85191/
- Dilemma, *Volvo Motronic 4.3 / 4.4* — https://www.villacarlota.net/volvo/motronicsuite/
- oleavr/bmw-coding `ds2.py` — https://github.com/oleavr/bmw-coding/blob/master/ds2.py (DS2 address list)
