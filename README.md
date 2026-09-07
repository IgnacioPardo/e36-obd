# e36obd

A native macOS client for the OBD1 diagnostic port on a 1994 BMW E36 (M43B16, Bosch Motronic M1.7.2).

That car predates OBD2. It speaks **KWP71** over a single-wire **K-line**, opened with a 5-baud slow init. A generic OBD2 scan tool cannot talk to it at all — not "it reads fewer PIDs", it will never establish a session.

The usual answer is a Windows laptop running INPA, or a VM with USB passthrough. This is neither. It is ~600 lines of Python driving an FTDI cable through Apple's built-in `AppleUSBFTDI` driver, using the UART's BREAK control to bit-bang the 5-baud wakeup. No drivers to install, no Windows, no VM.

Hardware assumed:

| Item | Detail |
|---|---|
| Cable | FTDI FT232R "INPA compatible K+DCAN" USB-to-OBD2 |
| Adapter | 16-pin OBD2 → BMW 20-pin round |
| Port | 20-pin round connector, engine bay, driver's side, under a black screw-on cap |
| Host | Apple Silicon Mac, macOS 26.3, enumerates as `/dev/cu.usbserial-A50285BI` |

**Do not install FTDI's VCP drivers.** macOS already claims the FT232R and exposes it as a `/dev/cu.*` device. Installing the vendor kext on top is a good way to break a working setup.

---

## Setup

The virtualenv already exists at `.venv` with `pyserial` installed (Python 3.14, pyserial 3.5). Nothing to build.

```bash
cd /Users/ignaciopardo/Desktop/E36_OBD
./.venv/bin/python -m e36obd doctor
```

Or activate it if you prefer:

```bash
source .venv/bin/activate
python -m e36obd doctor
```

Every example below uses the explicit `./.venv/bin/python -m e36obd` form.

### Global flags

These apply to every subcommand and go **before** it:

| Flag | Default | Meaning |
|---|---|---|
| `--port PATH` | autodetect | Serial device. Autodetect prefers FTDI VID `0x0403`, then any `/dev/cu.*usbserial*`. |
| `--baud N` | `9600` | Post-init line rate. Motronic uses 9600. |
| `--timeout SEC` | `1.0` | Per-byte read timeout. |
| `--address N` | `0x10` | ECU address for the slow init. `0x10` wakes DME #1, `0x14` DME #2. Accepts `0x10` or `16`. |
| `--keyword-bytes N` | `3` | Bytes to collect starting at the `0x55` sync. |
| `--loopback auto\|on\|off` | `auto` | Whether the cable echoes TX back onto RX. Auto-detected on the first write. |
| `-v`, `--verbose` | off | Log every byte in and out. Use this whenever something is wrong. |

Example: `./.venv/bin/python -m e36obd --address 0x11 -v codes`

---

## Verified on the car — 2026-08-09

Working end to end on a 1994 E36 M43B16 automatic. What it took, and what was
learned, so none of it has to be rediscovered:

**The L-line jumper is mandatory.** A stock K+DCAN cable drives only OBD2 pin 7
(K-line). BMW's 1.7-era DME wants the 5-baud wakeup on the **L-line**, and the
20-pin adapter brings that out on **OBD2 pin 15** — a pin the cable leaves
unconnected. Result: perfect transport, correct address, correct timing, and
total silence at every address.

The fix is a solder bridge between **OBD2 pin 7 and pin 15** inside the cable's
connector. The instant that was in, `0x10` answered with `55 00 81`. A KKL 409.1
cable does the same thing in hardware and needs no modification.

Be careful of pin 16 next door — it is +12V, and bridging it to the K-line
would put battery voltage onto the DME.

**Address is `0x10`, not `0x12`.** `0x12` is the DS2 engine-ECU address, a
different protocol entirely. `0x14` is DME #2 and is silent on this car.

**Two real bugs were fixed to get here**, both of which caused silent failure:
the stop bit was slept out for 200 ms before flushing the input buffer, which
discarded ECU replies arriving inside the spec's 60–300 ms window; and inits
were issued without the ≥2600 ms bus idle BMW requires.

**Live values only populate with the engine running.** With the ignition on and
the engine off, every sensor address reads `0x00`. This looks exactly like a
dead link and is not.

**Sampling is round-trip bound.** `--interval` barely matters — each sample
costs a full command/response cycle at 9600 baud, so the real rate is about
1 Hz. That is too slow to resolve sub-second events such as a TPS dropout, so
absence of a glitch in a log is not evidence of absence.

**Reads degrade with the engine running.** A 252-byte read is clean with the
ignition on; at idle, ignition noise corrupts the byte handshake and KWP71 has
no error recovery, so one bad byte ends the session. `live` works around this
by collapsing the core sensors into a single contiguous 11-byte read and
rebuilding the session when it breaks.

## Panel web

```bash
./.venv/bin/python -m e36obd dash            # http://127.0.0.1:8036
./.venv/bin/python -m e36obd dash --lan      # accesible desde el celular, con token
./.venv/bin/python -m e36obd dash --demo     # datos sintéticos, sin auto
./.venv/bin/python -m e36obd dash --no-live  # no toca el puerto serie
```

Todo local: stdlib de Python más pyserial. Sin framework, sin CDN, funciona sin internet.

**Cuatro pestañas**, direccionables por hash (`#tablero`, `#diagnostico`, `#capturas`,
`#scanner`) para poder compartir un link directo a una sección.

| Pestaña | Qué hace |
|---|---|
| **Tablero** | Instrumentos analógicos (régimen, refrigerante, carga), barras segmentadas para batería y aire, testigos, control de grabación y tendencia de 4 minutos |
| **Diagnóstico** | Memoria de fallas decodificada, sonda DS2 para el EGS, comparación antes/después de snapshots, registro de eventos |
| **Capturas** | Sesiones grabadas con métricas derivadas, cursor único que recorre los cinco canales a la vez, y superposición de dos sesiones para comparar |
| **Scanner** | Explorador de RAM con detección acumulada de cambios, y envío de bloques manuales |

### Un solo hilo toca el puerto

La K-line es un puerto serie y solo una cosa puede tenerlo. El servidor corre **un**
hilo que mantiene la sesión viva y, entre muestras, drena una cola de acciones. Los
handlers HTTP nunca abren el puerto: encolan y consultan. Por eso grabar, releer
fallas, volcar RAM y sondear DS2 conviven con el polling en vivo sin pelearse.

### Qué NO hace

Los bloques de escritura (`0x02` WriteRAM, `0x1A` WriteEEPROM) y de actuadores
(`0x04`) están bloqueados **en el servidor**, no solo ocultos en la UI. Verificado con
un ECU simulado: nunca llegan al bus. Borrar la memoria de fallas sí está disponible,
detrás de confirmación explícita, y **siempre guarda un snapshot automático antes** —
los contadores de ocurrencias son la única evidencia de con qué frecuencia ocurre cada
falla y no se recuperan.

### Acceso desde el celular

`--lan` liga a `0.0.0.0` y genera un token; cada request debe llevarlo. Sirve para
mirar el panel desde el teléfono con la laptop conectada en el vano motor. No hay
usuarios ni contraseñas: un secreto compartido, comparado en tiempo constante, es el
peso correcto para una herramienta en tu propia red. Cualquiera con el link puede ver
y operar el panel.

### Cómo encontrar el TPS y la velocidad

De los 252 bytes de RAM conocemos cinco. El explorador acumula, por byte, cuántas
veces cambió y entre qué valores osciló desde el último reset, y lista los candidatos
ordenados por recorrido. Con el motor en marcha: **Vigilar**, pisar el acelerador, y
mirar cuál byte recorre el rango más grande. Ese es el TPS.

## Pre-flight electrical checklist

**Read this before the cable ever touches the car.** Almost every "it doesn't work" report on these setups is one of the three problems below, and all three fail *silently* — the port opens, the command runs, and nothing answers.

### 1. OBD2 pins 7–8 must be bridged

K-line-only BMWs (E36, E38, E39, early E46) expect the diagnostic K-line on **OBD2 pin 7**, but the round-connector adapters and many cables present it on **pin 8**. K+DCAN cables are built for later CAN cars and do not bridge these by default.

- Many cables have a physical switch (often labelled for "DCAN / K-line", or an unlabelled slider on the USB end). Set it to the K-line position.
- Some cables have no switch and need pins 7 and 8 soldered together on the internal PCB. This is the single most common reason a K+DCAN cable "doesn't work on an E36".
- Verify with a multimeter in continuity mode: probe OBD2 pin 7 and pin 8 on the cable's own 16-pin connector. It should beep. If it doesn't, nothing downstream matters.

Without this bridge you will get exactly the same symptom as a dead ECU: `scan` reports "no response" on every address.

### 2. The 20-pin adapter must be fully pinned

The cable is **bus-powered from OBD2 pin 16**. It draws its +12V from the car, not from USB. Cheap 20-pin round adapters are sometimes wired K-line-and-ground only, on the assumption that the tool is self-powered. With one of those, the FTDI chip never powers up on the car side and the K-line transceiver stays dead — again, silently.

Before buying or trusting an adapter, confirm it passes through at minimum: K-line, +12V, and ground. "Fully pinned" or "all pins wired" in the listing is a claim, not a guarantee. Check it yourself.

### 3. Multimeter checks — verify, don't trust

Do these with the multimeter, at the round connector in the engine bay and at the cable's 16-pin end. **Confirm the 20-pin round pinout against a BMW source (TIS, a service manual, or a reputable E36 reference) before probing.** Pin numbering on the round connector is not intuitive and several conflicting diagrams circulate online — do not take any single number, including from this document, on faith.

| Check | Meter mode | Expected |
|---|---|---|
| Battery voltage at the round connector's +12V pin | DC volts, black lead on chassis ground | ~12.4 V engine off, ~13.8–14.4 V running |
| Round-connector K-line pin → OBD2 pin 7 | Continuity, cable+adapter **unplugged from car** | Beeps / near 0 Ω |
| Round-connector +12V pin → OBD2 pin 16 | Continuity, unplugged | Beeps / near 0 Ω |
| Round-connector ground pin → OBD2 pins 4 and 5 | Continuity, unplugged | Beeps / near 0 Ω on both |
| OBD2 pin 7 → pin 8 on the cable itself | Continuity | Beeps (see §1) |

Do continuity testing with the assembly **disconnected from the car**. Do voltage testing at the car's connector with nothing else plugged in.

If the +12V pin reads 0 V at the round connector, check the fuse feeding the diagnostic socket before assuming the adapter is bad.

### 4. Ignition position 2

The DME is only awake with the ignition in **position 2**: key turned until the dash warning lights are on, engine **not** running. Position 1 (accessory) is not enough. Nothing will answer with the key out.

For `log` you will eventually want the engine running — but establish a session with the engine off first.

---

## Usage

Run these in order. Each one only makes sense once the previous one worked.

### 1. `doctor` — desk test, no car needed

```bash
./.venv/bin/python -m e36obd doctor
```

Lists every serial port with VID:PID and flags the FTDI one, opens the chosen port, toggles BREAK (the mechanism the 5-baud init depends on), and listens for 2 seconds of unsolicited traffic.

Silence in the listen phase is **expected and fine** when you're not connected to a powered-up car. What you're confirming here is: the port exists, it opens, and BREAK control works. If BREAK fails, the slow init cannot work at all and nothing else is worth trying.

### 2. `scan` — find the ECU address

```bash
./.venv/bin/python -m e36obd scan
```

Plugged into the car, ignition in position 2. Tries each candidate address in turn — default set: `0x10 0x14 0x11 0x01 0x13 0x33 0x00 0x12 0x17` — and reports which ones return a `0x55` sync plus keyword bytes. Each attempt takes about 7 seconds (2.6 s of required bus idle, 2 s of bit-banging, then the listen window), so the full default sweep runs roughly a minute.

`0x10` is first because it is the confirmed BMW Motronic DME address. `0x12` is kept only as a long shot — it is the **DS2** engine-ECU address, a different protocol, and appears in no KWP71 implementation.

Pass your own list as positional arguments:

```bash
./.venv/bin/python -m e36obd scan 0x12 0x11 0x80
```

A responding address prints its keyword bytes and a ready-to-paste `--address 0xNN`. Use that address for every subsequent command.

### 3. `id` — ECU identification

```bash
./.venv/bin/python -m e36obd --address 0x10 id
```

Connects and prints the ID strings the ECU volunteers immediately after init (hardware number, software version, and similar — as ASCII plus raw hex). If the ECU volunteers nothing, it explicitly requests block title `0x00` (`REQUEST_ID`).

This is the real proof of a working link: readable text coming out of a 30-year-old ECU means framing, the ack handshake, and the sequence counter are all correct.

### 4. `codes` — stored fault codes

```bash
./.venv/bin/python -m e36obd --address 0x10 codes
```

Sends `READ_TROUBLE_CODES` (`0x07`) and prints the raw payload hex. If the total length is a multiple of 5 it also shows a speculative 5-byte-record grouping (`code`, `status`, `rest`). **That grouping is a hypothesis, not a verified BMW decode** — see "Known vs unknown" below.

If the ECU answers `NACK` / `NOT_SUPPORTED`, the tool suggests probing a different title with `raw`.

### 5. `log` — live values into CSV

```bash
# sweep the first 16 ADC channels, half-second interval, to a file
./.venv/bin/python -m e36obd --address 0x10 log --adc 0-15 --out sweep.csv

# a few specific channels, faster, for 60 seconds
./.venv/bin/python -m e36obd --address 0x10 log --adc 0,3,7 --interval 0.2 --duration 60

# raw RAM reads: ADDR:LEN, repeatable
./.venv/bin/python -m e36obd --address 0x10 log --ram 0x1000:4 --ram 0x1020:2 --out ram.csv

# include the parameter block, if this ECU implements it
./.venv/bin/python -m e36obd --address 0x10 log --param
```

| Flag | Meaning |
|---|---|
| `--adc SPEC` | ADC channels. Ranges and lists: `0-15`, `0,3,7`, `0-7,12`. |
| `--ram ADDR:LEN` | RAM read, repeatable. `LEN` defaults to 1. |
| `--param` | Include the `READ_PARAM_DATA` (`0x10`) block. |
| `--interval SEC` | Seconds between samples (default `0.5`). |
| `--duration SEC` | Stop after N seconds (default: run until Ctrl-C). |
| `--out PATH` | CSV path. Omit to write to stdout. |

Columns are `timestamp`, `elapsed_s`, then one per requested channel/read. Values are hex strings; a channel that fails a given sample yields an empty cell rather than aborting the run. At least one of `--adc`, `--ram`, `--param` is required.

More channels per sample means a slower effective sample rate — each one is a full block round-trip. A 16-channel sweep will not keep up with a 0.1 s interval.

### `raw` — probe undocumented commands

```bash
./.venv/bin/python -m e36obd --address 0x10 raw --title 0x3A
./.venv/bin/python -m e36obd --address 0x10 raw --title 0x08 04
```

Sends an arbitrary block title with optional hex payload bytes and prints every response block as hex and ASCII. This is how you go hunting when BMW used a non-standard title.

### `clear` — erase fault codes

```bash
./.venv/bin/python -m e36obd --address 0x10 clear      # prompts
./.venv/bin/python -m e36obd --address 0x10 clear -y   # no prompt
```

See the safety note below before running it.

---

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `No serial port found` | Cable not enumerated, or macOS hasn't claimed it | `ls /dev/cu.*`; try another USB port or cable; check for a non-FTDI clone chip with `system_profiler SPUSBDataType`. Pass `--port` explicitly if the device name differs. |
| `doctor` opens the port but BREAK control fails | The `/dev/tty.*` device was selected instead of `/dev/cu.*`, or a third-party FTDI kext is interfering | Always use `/dev/cu.*` — `/dev/tty.*` blocks on carrier detect, which never asserts on a K-line cable. Uninstall any vendor FTDI driver and reboot. |
| `scan` finds no responding address | Almost always electrical, not software | Work the pre-flight list in order: pins 7–8 bridged? adapter passing +12V and ground? +12V present at the round connector? ignition in position 2? Only after all four, widen the address list. |
| Init succeeds (keywords printed) but blocks fail their ack handshake — `bad ack for byte N` | Timing or line quality: marginal K-line pull-up, long/thin adapter wiring, or the ECU is using a non-standard framing detail | Re-run with `-v` to see the exact byte where it diverges. Try a shorter/better adapter. If the failure is always at byte 0 of the first block, suspect loopback misdetection — force it with `--loopback on` or `--loopback off`. |
| `no valid init response (wanted 3 bytes from 0x55, got ...)` — partial keywords | Wrong `--keyword-bytes` for this ECU, or noise before sync | Try `--keyword-bytes 2` or `4`. Run with `-v` to see the pre-sync noise the tool is discarding. |
| Session establishes, then dies mid-`log` | KWP71 drops the link if blocks stop flowing; also a classic loose-connection signature | Lower `--interval` so keepalive traffic is more frequent; reduce the number of channels per sample. Then check the physical connection — vibration at the round connector and a marginal ground are both common. |
| Intermittent disconnects, worse with the engine running | Ignition noise coupling onto a single-wire bus, or the cable browning out on a sagging supply | Route the cable away from plug leads and the coil. Verify supply voltage at pin 16 while running. Confirm the engine-bay connector's ground is clean. |
| `ECU rejected command 0x.. with NOT_SUPPORTED` | BMW used a different block title for that function | Probe with `raw --title 0xNN`. This is expected on some commands — see below. |

---

## Known vs unknown

Being straight about this, because it determines how much you should trust the output.

### Solid

- **KWP71 framing.** `[length][seq][title][payload...][0x03]`, with every byte but the last acknowledged by its bitwise inversion, in both directions. Taken from [colinbourassa/libiceblock](https://github.com/colinbourassa/libiceblock), which documents this from tested hardware. The length byte counts seq + title + payload + trailer but not itself.
- **The macOS slow init.** libiceblock bit-bangs the 5-baud wakeup via libftdi bitbang mode, which is unusable here because `AppleUSBFTDI` owns the interface. This implementation clocks the address bits out with the UART's BREAK control instead — BREAK asserted holds TX low (logic 0), cleared returns to idle high (logic 1), which is exactly start bit / 8 data bits LSB-first / stop bit. The port never leaves 9600 baud. Bit deadlines are absolute so jitter can't accumulate over the ~2-second sequence.
- **Loopback handling.** The cable echoes TX onto RX. That's auto-detected on the first write rather than assumed, and a byte that comes back *not* matching what was sent is treated as real ECU data and pushed back for the next read.

### Not confirmed

1. **The correct slow-init address for M1.7.2.** `0x12` is the usual Bosch Motronic address and is the default, but it is not confirmed for this specific DME. That uncertainty is the entire reason `scan` exists. Once you find the address that answers, note it down.

2. **Block titles may be non-standard.** The `BlockType` table is the generic KWP71 set. Manufacturers deviate. A `NOT_SUPPORTED` response does not mean the ECU lacks the feature — it may mean BMW put it on a different title. `raw --title 0xNN` is the tool for finding out.

3. **Fault-code format is not decoded.** `codes` prints raw hex, plus a *speculative* 5-byte-record grouping when the length divides evenly. Neither the record layout nor the code-number-to-description mapping has been verified for this ECU. There is no fault-code table in this project. A code number without a table tells you a fault exists, not what it is.

4. **ADC channel meanings and the RAM map are unknown.** There is no list of which channel is coolant temp, which is TPS, or where anything lives in RAM. `log` is therefore a **discovery tool**, not a dashboard. It gives you timestamped raw values to correlate against things you do to the car — see the next section.

Scaling is also unknown. A raw ADC byte is not degrees Celsius; the conversion is ECU-specific and has to be derived.

---

## Discovering what the values mean

The method is empirical: log everything while doing something with a known physical effect, then look for the column that moved the way the physical thing moved.

**Coolant temperature.** Start cold. Log a full sweep for the whole warm-up:

```bash
./.venv/bin/python -m e36obd --address 0x10 log --adc 0-15 --interval 1.0 --out warmup.csv
```

Start the engine and let it come up to temperature. Coolant temp is the channel that rises **monotonically** over ~10 minutes and then flattens when the thermostat opens. Almost nothing else in the car does that. Note that NTC sensors are usually inverted — the raw value may fall monotonically as temperature rises, which is just as identifiable.

**Throttle position.** Engine off, ignition on. Log a short sweep while sweeping the pedal slowly from closed to full and back:

```bash
./.venv/bin/python -m e36obd --address 0x10 log --adc 0-15 --interval 0.3 --duration 60 --out throttle.csv
```

TPS is the channel that tracks the pedal, returns to the same value at rest, and hits its ceiling at wide-open. Do a few full sweeps so you can tell a real correlation from a coincidence.

**Battery voltage.** This one you can calibrate absolutely, which makes it the best channel to solve first. Measure battery voltage with the multimeter, find the channel closest to a fixed multiple of it, then load the system — headlights on, then engine running with the alternator charging — and confirm the raw value tracks the meter. Two points (say 12.4 V and 14.2 V) give you a linear scale for that channel, and often hint at the ADC reference the others share.

**Intake air temp / air mass.** Distinguish from coolant temp by the fact that IAT responds within seconds to a heat gun or a cold soak, whereas coolant temp has minutes of thermal lag. Air mass jumps with a throttle blip and settles back.

General approach:

- Change **one** thing at a time. A log taken while the engine warms *and* you rev it is uninterpretable.
- Prefer monotonic or repeatable-cycle stimuli. Anything that goes up and comes back down to the same value is easy to spot in a spreadsheet.
- Load the CSV into anything that plots — a column that visibly correlates is worth more than staring at hex.
- Once you're down to a handful of interesting channels, re-log just those at a much shorter `--interval` for better time resolution.
- Write down what you confirm. Nothing here persists a mapping for you.

---

## Safety

- **Do not probe pins at random with the ignition on.** Shorting a DME input to +12V or to ground can destroy it. Not every line into the DME is fuse-protected. An M1.7.2 is expensive and increasingly hard to find.
- Do continuity testing with the harness **disconnected from the car**. Do voltage testing deliberately, one pin at a time, with a known-good ground reference.
- Confirm the round-connector pinout against a BMW source before touching a probe to it. Assume any pinout diagram — including the framing in this README — is wrong until you've verified it.
- **`clear` destroys evidence.** An intermittent fault that is currently stored is diagnostic information you may not be able to reproduce on demand. Read and record the codes with `codes`, and save the raw hex, *before* you erase anything. Once cleared, it's gone.
- `raw` sends arbitrary block titles to a live engine controller. The `WRITE_RAM` (`0x02`), `WRITE_EEPROM` (`0x1A`), and `ACTIVATE_ACTUATOR` (`0x04`) titles exist in the block table and are not read-only operations. Know what a title does before sending it.
- Do all first-contact work with the engine off. Once you move to logging with the engine running, keep the cable clear of the belts, the fan, and the exhaust manifold.
