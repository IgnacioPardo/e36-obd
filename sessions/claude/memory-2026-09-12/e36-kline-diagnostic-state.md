---
name: e36-kline-diagnostic-state
description: "E36 diagnostics SOLVED — DME at 0x10/9600 and EGS gearbox at 0x6C/4800; working config, sensor map, wiring, and the car's real faults"
metadata: 
  node_type: memory
  type: project
  originSessionId: 520df9c4-5564-4e32-b377-60307bb80ef3
  modified: 2026-08-09T21:45:13.769Z
---

**SOLVED 2026-08-09.** The link works: fault codes decoded and live sensor logging to CSV, for [[e36-obd1-kline-project]].

**The fix:** a stock K+DCAN drives only OBD2 pin 7 (K-line), but BMW's 1.7-era DME wants the 5-baud wakeup on the **L-line**, which the 20-pin adapter brings out on **OBD2 pin 15** — a pin the cable leaves unconnected. Ignacio soldered a bridge between OBD2 pins 7 and 15 inside the cable connector and `0x10` immediately answered `55 00 81`. (A KKL 409.1 does this in hardware.) Watch pin 16 next door — it is +12V.

**Working config:** address `0x10` (NOT `0x12`, which is DS2), 5 baud 8N1 LSB-first, ≥2600 ms bus idle before each init, then 9600 8N1. Adapter pin set is 4/5/7/15/16; pin 8 is absent, so the cable's 7-8 switch does nothing either way.

**Two bugs fixed along the way**, both causing silent failure: sleeping out the 200 ms stop bit before flushing (discarded ECU replies arriving in the spec's 60–300 ms window), and missing the 2600 ms bus idle.

**Verified sensor map** (M1.7.2, validated at idle — battery 13.5 V charging, IAT 19 °C, coolant rising 46→48 °C, 900 rpm): `0x0036` battery ×0.0681, `0x0037` IAT −33.5+0.65x, `0x0038` coolant −32.5+0.65x, `0x003C` rpm ×10, `0x0040` load ×0.05. **These read 0x00 until the engine actually runs** — looks like a dead link, isn't.

**Known limits:** sampling is round-trip bound at ~1 Hz regardless of `--interval`, too slow to resolve TPS dropouts. Reads are clean at ignition-on but ignition noise at idle breaks sessions, so `live` uses one contiguous 11-byte read plus reconnect-on-failure.

**The car's real faults** (predate all this): code 36 EVAP/tank-ventilation valve, short to ground, **present now**, 50 occurrences — same system as a strong fuel smell noticed while running. Code 73 VSS-or-TPS, **sporadic**, 10 occurrences — fits both a sudden idle stall and the automatic's intermittent failure to shift 2→3 and 3→4 (EGS limp). EGS fault memory has never been read; only `0x10` has ever been reached.

**Correction to an earlier hypothesis:** code 73 does NOT directly explain the failure to upshift. The EGS has its own output-shaft speed sensor (n-ab) and does not use the DME's vehicle-speed signal (the DME gets that from the cluster). Only indirect path: if 73 is failing on its TPS half, the DKT/ti signals the DME feeds the EGS go bad. Transmission is A4S 310R (GM 4L30-E); solenoid A = 1-2 and 3-4, solenoid B = 2-3. With the valve body already replaced and fluid good, top suspects are the **n-ab speed sensor at connector X8516** and the **gear-selector/range switch in the centre console**.

**Freeze-frame scalings resolved by elimination:** RPM in the fault record is ×40 (×10 gives an impossible 470 rpm for code 36), and byte 3 is coolant temperature, not volts (as volts it gives 7–9 V with the alternator charging). So code 73 was recorded at ~4560 rpm and ~32 °C — high revs on a cold engine, i.e. mid-missed-upshift. **Future captures must start from cold**; every log so far sat at 46–58 °C and never entered the window where 73 fires.

**The tachometer saturates at 2550 rpm.** `0x003C` is one byte at ×10 scale, so live rpm physically cannot exceed 2550 — even though the fault-record freeze frame (×40) reported 4560. Engine rpm is almost certainly 16-bit with its high byte at **`0x003B`**, which already arrives inside the 11-byte core block and was being discarded. To settle it: rev past 2550 once and watch whether `0x003B` moves. Six bytes in that block (`0x39 0x3A 0x3B 0x3D 0x3E 0x3F`) are free data now captured in the log.

**Two bugs found by analysing the real captures**, both of which made the tool lie: the browser appended `live` on its own 1 Hz timer while the server only cleared it on full session teardown, so during a 17.7 s reconnect it replotted one stale value seventeen times as a confident flat line; and charts interpolated straight across gaps. `session_174425.csv` is **42 % dead air**. Fixed with a per-sample `_seq`/`_t` identity that the frontend checks before appending, plotting against real time, and gap-aware paths that break the line and shade the hole.

**THE EGS WAS FOUND, 2026-08-13 — and my earlier "definitive negative" was wrong.** The transmission controller is at **address 0x6C at 4800 baud**, KWP71 like the DME but at HALF the rate. That is why every 9600 sweep returned garbage: a `0x55` sent at 4800 and sampled at 9600 reads back as `0x66`, and the observed reply was `66 33 7E E0 06 C0` twice — i.e. a 3-byte sync doubled to 6 and retried. Keywords are **`55 87 81`** (the DME gives `55 00 81`). ID strings: `4032000620 / 0043367333 / 614G511000 / 200000 / 000 / 9691241`.

**Its one stored fault: code 100 = "speed monitoring — ratio n-ab/n-mot not correct for the gear selected"**, sporadic, invalid working area, recorded at 4880 rpm, 1 occurrence (raw `64 88 7A 3C 01`). Note code **20** ("n-ab: NO signal") is NOT set — so the output-shaft sensor IS producing a signal and it is the *ratio* that is wrong, which points at the shift not actually engaging rather than a dead sensor. With the valve body already replaced, the remaining suspects are the solenoid for that shift, its supply, or something mechanical.

**Never decode one module's codes with the other's table.** DME 100 = "amplifier/output stage 1 in DME"; EGS 100 = speed monitoring. Numbers collide, meanings do not. `snapshots/egs-*.json` is deliberately excluded from the DME snapshot comparator for this reason.

**Wiring, settled by the adapter's own pin card:** OBD2 `4+5`→round `19` (gnd), OBD2 `7`→round **`17+20` commoned**, OBD2 `15`→round `15` (RXD), OBD2 `16`→round `14` (+12V **permanent**, not ignition-switched). Since the E36 ETM puts the EGS TXD on round pin **17** for 316i/318i, commoning 17+20 onto OBD2 pin 7 is exactly why both the EGS and the ABS are reachable on this cable. Nothing is missing physically.

**Also on DS2** (9600 8E1, no init): `0x56` = ABS/ASC, identify `a0 01 16 30 90 02 00 64 00 12 94 04 02`, part-number candidate 1163090, fault memory via cmd `0x04` reads `a0 b2 00 00 22 00 00 b1 00 80` (no ABS table available). A module at `0x00` answers identify only. The EGS is NOT on DS2.

**The cable dropped off USB twice in one session** (`termios.error (6) Device not configured`), killing a sweep mid-run. Sweep tools now reopen the port and retry the same address instead of aborting.

**EDIABAS SGBD files are readable: the string tables are XOR 0xF7.** Cracked by known-plaintext (`FS_LESEN` is the canonical EDIABAS fault-read job name and appears with a constant delta). BMW Standard Tools lives at `~/Downloads/Project-BMW-E36/BMW Standard Tools/ec-apps/EDIABAS/Ecu/`. The transmission's SGBD is **`gs41x.prg`** = "Getriebesteuerung 4.1x" rev 1.43 (1996), identified from `INPA/CFGDAT/E36.ENG` whose transmission menu offers gsds2 / gs41x / gs7x_k / jatco / smg.

**From that file, authoritative and now in `e36obd/egs.py`:** the full fault-code table (more specific than any third-party manual — it names *which* solenoid: 43 = MV 2-3, **48 = MV 1-2/3-4**, 54 = solenoid ground), the fault-type vocabulary, and the freeze-frame scalings, which are **NOT the DME's**: rpm ×32 (not ×40), oil temp = raw − 40, throttle ×0.392 (= 100/255 exactly), volts ×0.068. Verified three independent ways.

**Re-reading our one EGS fault with the correct scalings: engine 3904 rpm, output 1920 rpm, ratio 2.03.** The A4S 310R ratios are 2.86 / 1.62 / 1.00 / 0.72 — **2.03 matches none of them**, which is precisely what code 100 complains about. Caveat: torque-converter slip inflates engine/output, so one occurrence cannot identify which shift failed; several occurrences cluster and can.

**The SGBD has exactly 19 jobs and NONE reads commanded gear.** `STATUS_DIGITAL_LESEN` is explicitly "digitalen **Eingangs**stati" (inputs): lever position, coding switches L1-L4, brake, kickdown, A/C. So INPA cannot show commanded gear for this module either. It IS obtainable via `RAM_LESEN` (standard ReadRAM, already implemented) by finding the address — and you can hunt it **stationary**: engine idling, brake on, move the selector 1→2→3→D and the guided search finds the byte taking values 1,2,3,4.

**Better still, commanded gear may not be needed:** the ratio *immediately before* the fault identifies the gear you were in, hence the shift attempted. Ratio-over-time is the datum that matters.

**Status-job request parameters, extracted but NOT confirmed:** the six STATUS jobs are byte-identical bytecode differing in two immediates — (0x05, 0x01) motor rpm, **(0x05, 0x02) output speed**, (0x05, 0x04) load, (0x05, 0x13) oil temp, (0x05, 0x14) volts, (0x03, 0x06) digital. Whether that pair is (title, payload) is unproven. **DANGER: 0x05 is EraseTroubleCodes in standard KWP71** — blind-probing it could wipe the fault memory. Snapshot first; try (0x03, 0x06) first.

**The panel can now target either module** (`set_target` action, buttons in Scanner). One port cannot hold two baud rates, so switching rebuilds the session; with EGS selected there is no engine-sensor sampling.

**How to apply:** Ignacio declines multimeter work and pushes back on safety caveats — state a concern once, plainly, then proceed with his decision. He values speed and parallel work.

**EL DME EXPONE READ_ADC_CHANNEL (0x08), descubierto 2026-08-15.** Nunca se había
probado contra el DME — la lista de sondas apuntaba al EGS. Devuelve 2 bytes por
canal. Hay **ocho canales reales**: los índices 0x08..0x0F son espejo de
0x00..0x07, o sea que el índice se enmascara a 3 bits. **El canal 04 es la
mariposa** (recorrido 22 → 171 cuentas, ~0,43 → 3,29 V si la escala fuera 8 bits
sobre 5 V, sin validar). Esto vale más que medir en el conector: es la conversión
que hace la ECU después de todo el mazo. **Y funciona con el motor apagado**, a
diferencia del bloque central de RAM, que lee 0x00 hasta que el motor gira.
Herramientas: `tools/adc_scan.py` (barrido de los ocho, ventana sin interacción)
y `tools/throttle_watch.py` (solo el canal 04, ~2,7 Hz porque la respuesta es
corta).

**Por qué el muestreo es de ~1,55 s, medido y no supuesto (`tools/latency.py`):**
una lectura serie que bloquea cuesta **~231 ms**, y ocho bytes en una sola lectura
cuestan lo mismo que uno (28,97 ms/byte × 8 = 231,8) — o sea que **el costo es por
LECTURA, no por byte**. Es la firma de un latency timer, pero catorce veces peor
que los 16 ms de fábrica del FTDI. **Ni `IOSSDATALAT` ni quitar `flush()`/tcdrain
cambian nada** (231,7 ms en los tres casos). No se puede agrupar la solución: el
handshake de KWP71 exige reconocimiento byte por byte en las DOS direcciones, así
que son ~43 lecturas bloqueantes por muestra. Optimizando bien se llega a ~0,8 s,
no más. DS2 sí es por bloques y podría muestrear rápido.

**PELIGRO — `tools/latency.py` NO se corre con el auto conectado.** El `IOSSDATALAT`
queda pegado en el chip FTDI aun después de cerrar el descriptor, y mata el enlace:
el init sigue funcionando pero la sesión muere en el intercambio de bloques
(`timed out waiting for a byte`, distinto del `InitError` de cuando la ECU no
contesta). Se recupera **desenchufando y volviendo a enchufar el USB**.

**El SGBD del DME 1.7 NO está en la instalación de EDIABAS** (819 archivos .prg
revisados; hay dme13, DME33, ms401/410/411/420/430, no el 1.7). Por eso no se
puede saber qué actuador es la "salida 1" del código 100, como sí se pudo con los
solenoides de la caja. El truco del XOR 0xF7 sigue funcionando en toda la
instalación (176 archivos contienen "Endstufe"), lo que falta es el archivo.

**Al perseguir un apagado, el enlace se cae siempre en el momento del evento:**
huecos de 12,7 s y 13,2 s en dos grabaciones distintas, justo en la parada. Por
eso la estrategia que sirvió fue **provocar el corte sin que se apague** (soltadas
en punto muerto) en lugar de intentar filmar el apagón.
