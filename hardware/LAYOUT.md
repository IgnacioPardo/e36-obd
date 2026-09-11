# Front-end K-Line E36 — placa

> **Superada por `onboard/`** (2026-09-11): la placa única con el ESP32-S3-WROOM-1, el buck
> discreto y la ficha OBD2 montada está en [`onboard/README.md`](onboard/README.md). Este
> documento describe el front-end anterior, que dejaba el MCU afuera. Ojo: en aquel netlist el
> TVS D1 quedó con el ánodo a +12 V; en la placa nueva la banda va a +12 V.

**DRC limpio: 0 violaciones, 0 desconectados** (KiCad 10.0.5). Placa en
`kline-frontend.kicad_pcb`, generada por `gen_board.py` desde el netlist.
Queda 1 aviso menor: la serigrafía de J1 toca el borde.

Netlist: `kline-esp32.net`. Once componentes, once redes, todas conectadas.

## La decisión de arquitectura

**El ESP32 no va en la placa.** La placa es el front-end del lado del auto y
termina en `J2`, un conector de 7 vías. El MCU cuelga de ahí por cable.

Esto no es un rodeo para evitar medir el zócalo. Es dónde va el límite:

- La función del lado del auto — ficha, protección, transceptor — **no cambia
  nunca**. El MCU sí: podés pasar de S3 a clásico, a un Pico, o Espressif revisa
  la placa y mueve los pines. La PCB no se rehace por ninguna de esas cosas.
- El conector OBD2 está abajo del tablero, rodeado de chapa. **Pésimo lugar para
  WiFi.** Con el MCU en un cable lo ponés donde haya señal, no donde haya ficha.
- La placa queda chica. Puede llegar a entrar en la carcasa del ELM327.

Usá conector **con traba** — JST-XH o similar. Dupont suelto en un auto se sale
con la vibración.

### J2 — salida al MCU

| pin | red | dirección |
|---|---|---|
| 1 | GND | — |
| 2 | +5V | placa → MCU (alimentación) |
| 3 | **K_RX** | placa → MCU |
| 4 | **+3V3** | MCU → placa (alimenta V<sub>CC</sub> del L9637D) |
| 5 | **K_TX** | MCU → placa |
| 6 | V_SENSE | placa → MCU (ADC) |
| 7 | GND | retorno |

**Los pines 3, 4 y 5 cambiaron respecto de la primera versión.** El orden viejo
era +3V3 / K_TX / K_RX. Con el ruteo real, ese orden obligaba a que K_RX cruzara
sobre las otras dos: en U1 sale más abajo que TX y VCC, pero tenía que llegar al
pin de J2 más arriba. Reordenando, las tres quedan monótonas y salen **rectas y
paralelas** desde U1 hasta J2, sin un solo cruce.

Los 3,3 V vienen **del regulador del ESP32**. El L9637D consume 1,4 mA típicos,
así que sobra, y evita poner un LDO propio.

## Anchos de pista

Placa de **80 × 50 mm**. Con 60 × 40 el ruteo quedaba estrangulado y el DRC
tiraba 80 violaciones; ampliarla fue más barato que pelear cada holgura.

| red | ancho | por qué |
|---|---|---|
| GND, VBAT_FUSED, +5V | 0,8 mm | Camino de potencia hacia el MCU |
| K_LINE | 0,5 mm | Poca corriente, pero viene de afuera |
| K_TX, K_RX, V_SENSE, +3V3 | 0,3 mm | Señal |

Dos capas. Plano de masa entero en la inferior, sin cortarlo con pistas.

## Colocación

```
  [J1 OBD2] ─ [F1] ─┬─ [C2] [D1] ─┬─ [J3 buck] ─┐
                    │             │             │
                    └─ K_LINE ─ [R1] ─ [U1] ────┴─ [J2 → MCU]
                                       [C1]
```

**Orden desde la ficha:** OBD2 → fusible → bulk y TVS → recién ahí se ramifica.
Nada aguas arriba del fusible salvo la pista de entrada.

**U1 cerca de J1**, no de J2. La pista que conviene corta es K_LINE, que es la
que trae el ruido del auto.

**C1 a menos de 5 mm del pin 3 de U1**, con vía propia a masa. Es la regla que
más se rompe.

## Checklist antes de fabricar

- [ ] Footprint del L9637D verificado: SO-8, paso 1,27 mm
- [ ] **Pin 1 de U1 marcado en la serigrafía.** El pinout no es simétrico:
      girado 180° pone V<sub>S</sub> — los 12 V del auto — donde va RX. Se lleva
      puesto el chip y lo que esté colgado de J2
- [ ] Serigrafía con los números de pin del OBD2 al lado de J1
- [ ] Serigrafía con la tabla de J2 en la placa, para no contarla con multímetro
      dentro de un año
- [ ] Polaridad de C2 y de D1 marcadas

Ya no hay nada que medir del ESP32.


## Cambios que impuso el ruteo

**F1 pasó a fusible SMD 1206.** El portafusible de cuchilla ATO ocupaba media
placa y bloqueaba los canales. Si querés fusible reemplazable a mano, va
**en línea sobre el cable** de entrada, antes de la ficha.

**Dos saltos a la capa inferior**, cosidos con vías:

- **K_LINE** pasa por debajo de la bajada de 12 V. Es el único cruce
  inevitable: los 12 V tienen que bajar del canal superior al inferior, y la
  línea K tiene que ir de izquierda a derecha.
- **+3V3 → C1** salta por debajo de K_RX. C1 va sobre el lado derecho de U1,
  que es donde está el pin 3.

**Las vías de masa son solo cuatro**, para los pads SMD (D1, U1, R3, C1). Los
pasantes — J1, J2, J3, C2 — ya llegan al plano inferior por su propio agujero.

## Reproducirlo

```
PY=/Volumes/KiCad/KiCad/KiCad.app/Contents/Frameworks/\
   Python.framework/Versions/3.9/bin/python3
$PY hardware/gen_board.py
kicad-cli pcb drc --severity-error hardware/kline-frontend.kicad_pcb
```
