---
name: e36-esp32-kline-hardware
description: "Lector K-line propio con ESP32-S3 + L9637D: FUNCIONA, leyó las fallas del DME. Firmware MicroPython y los errores que costaron la noche"
metadata: 
  node_type: memory
  type: project
  originSessionId: 36c9b727-cfdc-4a8c-a588-084fdd452c5e
  modified: 2026-09-07T21:26:03.177Z
---

**FUNCIONA, 2026-09-07.** Leyó los códigos 100 y 36 con contadores en 50 y
condiciones 0x68 y 0x72 — idénticos byte por byte a lo que dio el cable K+DCAN
el 15-ago, más las cinco cadenas de ID del DME. Continúa [[e36-kline-diagnostic-state]] y [[e36-corte-retencion-stall]].

**Por qué existe:** los 231 ms por lectura del driver FTDI de macOS limitan el
muestreo a 0,65 Hz, medido con `tools/latency.py`. Sin esa capa el techo lo pone
el handshake de KWP71 y el retardo entre bytes del DME — se esperan 10-20 Hz. A
1 Hz un corte de combustible es una muestra; a 10 Hz es una curva.

**MicroPython en vez de Arduino.** El núcleo ESP32 de Arduino son ~2 GB de
descarga; el firmware de MicroPython pesa **1,7 MB** y no tiene ciclo de
compilación. Y nuestra implementación de referencia ya es Python, así que
`kline.py`/`kwp71.py` portan casi línea por línea. Está en
`firmware/mp/kline.py`, ya cargado en la placa.
Build: `ESP32_GENERIC_S3-SPIRAM_OCT-20260824-v1.29.0.bin`.

**Las 9 conexiones** (`docs/cableado.html`, `hardware/kline-salvage.net`):
OBD2 16 → L9637D 7 (V_S) y → buck IN+ · OBD2 7 **y** 15 → L9637D 6 (K) ·
OBD2 4/5 → L9637D 5, buck −, ESP32 GND · buck OUT+ → ESP32 5Vin ·
ESP32 3V3 → L9637D 3 (V_CC) · GPIO17 → L9637D 4 (TX) · L9637D 1 (RX) → GPIO18.

**Sin conversor de nivel:** V_CC mínima del L9637D es **3 V** (tabla 5), no 4,5
como creí. Alimentado a 3,3 V su lógica queda compatible directa con el ESP32.

**El L9637D NO maneja la línea L.** LI/LO son un comparador — entrada de bus y
salida lógica, solo leen. Por eso K va a los pines 7 **y** 15 del OBD2 juntos: el
DME despierta por L.

**Pinout, hoja de datos ST Doc ID 1765 Rev 8 tabla 2**, con el texto derecho el
pin 1 queda abajo a la izquierda: abajo 1 RX, 2 LO, 3 V_CC, 4 TX · arriba 8 LI,
7 V_S, 6 K, 5 GND. **No invierte** (figura 5: TX baja y K baja detrás).

**TRAMPA que costó horas: el chip tiene pull-ups internos en TX, RX y LO** (lo
dice la primera página). Cualquier test basado en los pull internos del ESP32
para decidir si un pin está "manejado" o "flotando" **es inválido**. El único
test válido del transceptor es funcional: `TX bajo → RX debe dar 0`.

**El puerto del ESP32-S3 DevKitC-1 cambia de nombre según el modo** — en
ejecución, en descarga, y según el conector. El de la serigrafía **COM** es el
puente WCH CH9102 (`USB Single Serial`) y es el que conviene: esptool resetea
solo por DTR/RTS, sin apretar BOOT ni RST. El `USB` nativo exige el baile de
botones. Nunca cablear el nombre del puerto en un script.

**El buck: los capacitores dicen cuál lado es cuál.** 100 µF/**50 V** = entrada
(12 V); 470 µF/**16 V** = salida (5 V). Más confiable que la serigrafía. Medido:
12 V entrada, **5,22 V** salida.

## Los dos errores que costaron la noche

**KEYWORDS = 2, no 3.** El DME responde `55 00 81`: el `55` es el sincronismo y
se consume aparte, así que quedan **dos** keywords. Leyendo tres, el tercer byte
era espurio y se reconocía el equivocado — la sesión se abría y moría enseguida.

**El contacto de los cables al adaptador SOIC→DIP.** Los pads miden perfecto
cuando apoyás una punta de multímetro encima, pero un jumper metido en el agujero
de 1 mm sin soldar baila. Recablear soldando lo resolvió. **Declaré el chip
muerto dos veces y estaba sano.**

Método que sí sirvió, y es el que hay que repetir: **medir de punta a punta**
—del pin del ESP32 a la pata del chip— en vez de por tramos. Así queda incluida
la unión cable-pad, que fue justo el eslabón que nunca verifiqué.

Y **verificar la propia forma de onda**: el ESP32 leyendo por RX lo que él mismo
transmite, con marcas de tiempo. Dio bajada en t=0, pulso alto del bit 4 a los
1007 ms y anchos de 196-200 ms. Eso descartó el firmware y dejó el problema
acotado al auto.

## Cómo retomar

```
mpremote connect <puerto> exec "import kline; kline.leer_fallas()"
```
Éxito = `55 00 81` y después los códigos **100 y 36** con contadores en 50. Esos
dos ya los conocemos de memoria, así que verifican todo el stack sin ambigüedad.

**How to apply:** Ignacio prefiere avanzar rápido y decidir él los riesgos —
plantear una preocupación una vez y seguir. Pero exigir el modo del multímetro
(`V⎓`, no `V~`) **en cada pedido de medición**: una tarde entera de mediciones en
alterna dio basura (0 V donde había 12) y sobre eso construí cinco hipótesis
falsas. Y medir siempre en filas de protoboard o borneras, **nunca sobre las
patas del adaptador SOIC** — están a 1,27 mm y puentearlas con la punta es un
corto de 12 V a masa.
