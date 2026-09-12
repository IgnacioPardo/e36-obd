---
name: e36-onboard-pcb
description: "Placa única rev B (2026-09-11): ESP32-S3-WROOM-1-N16R8 + L9637D + AP63203 + ficha OBD2 en 90x48, generada con gen_board.py + Freerouting; qué falta verificar antes de fabricar"
metadata: 
  node_type: memory
  type: project
  originSessionId: c5212502-a705-4dc1-81ae-b5f70cbdc161
  modified: 2026-09-11T11:09:24.432Z
---

**Ignacio pidió (2026-09-10) una sola PCB con todo SMD para mandar a fabricar**: ESP, buck
discreto, L9637D y los pines OBD2. Eso revierte la decisión previa de dejar el MCU afuera
(`hardware/LAYOUT.md`, que además tenía el TVS al revés). Está en `hardware/onboard/`,
continúa [[e36-esp32-kline-hardware]] y [[e36-kline-diagnostic-state]].

**Lo que quedó decidido y por qué:**
- Módulo **ESP32-S3-WROOM-1-N16R8** soldado (octal PSRAM: el build MicroPython es SPIRAM_OCT),
  entero sobre la placa con keep-out de antena (53–90 × 0–6,5) — Ignacio no quiso el saliente
  en la caja. Pines iguales al DevKit: 17 TX, 18 RX, 4 ADC, 38 LED, USB nativo 19/20.
- **UVLO en el EN del AP63203** (pedido: "resistors to prevent draining the battery"): R10 36k /
  R11 3,74k → ON 12,5 V, OFF 11,5 V; R12 4k7 desde VBUS para que en el banco arranque. Es piso
  de seguridad; el drenaje diario lo tiene que resolver el deep sleep por V_SENSE (firmware).
- **12 V → 3,3 V directo con AP63203** (32 V máx, salida fija), sin riel de 5 V. USB-C VBUS
  y 12 V OR-eados con dos SS34. TVS SMBJ24A con la **banda a +12 V**. R1 510 Ω en **2010**
  (0,38 W pico a 14 V, un 0805 no aguanta).
- **Ficha OBD2**: footprint construido desde el STEP del Macchina CCBDM20 (pitch 4,00,
  filas a 3,00, a 2,25 y 5,25 mm de la brida; fila 1-8 = lado ancho de la D). Un espejado
  sería benigno (+12 V caería en el pad 9, sin conectar).
- Flujo: `gen_board.py` (pcbnew, todo declarado como datos) → DSN → **Freerouting 2.4.1**
  (`-mt 1`, 30 pasadas; con `-mt 4` deja violaciones de holgura) → SES → vías de costura →
  DRC. Freerouting estrecha pistas a 0,187 mm en pines finos: NO ensancharlas después
  (rompe holguras); bajar el mínimo a 0,15 mm.

**Caja**: `hardware/onboard/case.py` (build123d), 96,8×54×26,4 prisma liso, tapa con campo =BMW= (nervios y
letras a ras en rebaje de 0,5, estilo tapa M50 — Ignacio lo pidió explícitamente); la altura la fija
la brida del conector (15,6 mm sobre la placa), la pared de 1,5 mm entra en el cuello de 2 mm del
conector. M3×16 desde abajo a postes de la tapa. Validada sin choques contra los volúmenes de la placa.

- **J4 (JST-XH 3 vías: GND, K, +12)** en paralelo con la ficha OBD2 para ir directo al conector
  redondo de 20 con una cola (19 GND, 15+17+20 K, +12 del **pin 16 = KL15 ignición** → sin drenaje,
  o 14 = KL30). Caja variante `CASE_PIGTAIL=1`. Placa ahora 90×50: la USB-C sobresale 1,6 mm y
  atraviesa la pared (abertura estadio + bisel), pedido de Ignacio ("support the usb correctly").
- Sin puente USB-UART: Ignacio dijo "si no es necesario no" → USB nativo solo.

**Commit 23c66164 en `IgnacioPardo/esp32-buck-case` (2026-09-11)** = primera versión completa (placa rev B
+ caja). Después Ignacio pidió que la caja parezca "herramienta moderna, no dongle chino": rediseño con
R6, chaflanes 45°, línea de sombra en la junta, **emblema =BMW= como pieza aparte en plata** (relieve 0,8,
se imprime relieve arriba; en la tapa iría contra la cama), guías de luz Ø3 para los LEDs, botones por
agujero de clip. **Ignacio RECHAZÓ la vuelta siguiente** (panel central en relieve con marco, banda
fresada en los respiraderos, emblema placa-negra/relieve-plata): "it looked better before" → tapa lisa con
chaflán y emblema entero en plata. Se conservaron solo los cambios invisibles: insertos M3 termofijados
(M3×12), conector en D en el modelo, renders EEVEE con luces. Con la foto del M50 como referencia ("pattern is off"): emblema 85×22 con **13 nervios finos paso 1,6, campo
negro, relieve plata, placa BMW descentrada hacia la ficha** (nervios cortos a la izquierda, largos hacia el USB); la placa BMW mide 12 de alto e interrumpe solo los
7 nervios centrales, los 3 de arriba y 3 de abajo siguen enteros (corrección de Ignacio);
SW2 (BOOT) movido a (77,5, 39) y LED2/R8 a x=86 para liberar la banda. Regla aprendida: la cavidad interior necesita radio chico (1,5) porque la placa tiene
esquinas vivas; con R3,6 la esquina de la placa se clava en la pared.

**Commit 0a5dcdac (2026-09-11)**: caja restyle + emblema M50 + USB capturada + J4/pigtail + UVLO, READMEs
(raíz y onboard) al día. La rama `IgnacioPardo/esp32-buck-case` está pusheada.

**Precio JLCPCB (2026-09-11, `hardware/onboard/pricing.py`)**: la API pública de partes de JLC
(`POST jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList`, keyword = código LCSC)
responde con curl y da precio/stock/base-expand; el endpoint de LCSC devuelve 403/404. Resultado: ≈97 USD por 5
placas ensambladas (≈19 c/u), ≈140 por 10; fijos 43 USD (11 partes extendidas × 3,07). Descubierto al cotizar:
tres códigos del BOM estaban MAL (C130489 era un electrolítico, C22936 un 1 Ω, C2296 un LED 0805) → corregidos:
L9637D = C153038 (E-L9637D013TR, stock ~1200), 3k74 = C23016, 36k = C23147, TVS = C123819, 2010 510R = C175041,
1210 10µF/50V = C53084458, LEDs 0603 básicos solo en rojo (C2286) y blanco (C2290). La ficha OBD2 de JLC
(C9900166046) está sin stock: J1 va aparte. La extensión de Chrome no estaba conectada (sin cotización en vivo).

**PCBWay (2026-09-11)**: Ignacio eligió PCBWay para 1 muestra con la ficha OBD2 soldada por la fábrica (mínimo 1,
compran de LCSC/Digi-Key/Mouser o consignado). `hardware/onboard/pcbway.py` genera `fab/pcbway/` + zip: BOM en
formato PCBWay con MPN reales, centroides con J1/J4, dibujo de armado, ORDER-NOTES.md con el formulario e
instrucciones (verificar footprint del conector antes de soldar; N16R8 obligatorio; polaridades).

**Cotización oficial PCBWay sin browser (2026-09-12)**: los precios salen de `POST pcbway.com/Quote/GetDeliveryDays/`
con el formulario serializado (campos de `QuickOrderOnline.aspx` / `quotesmt.aspx`: hidLength/hidWidth/hidNum,
txtBoardNum, txtICType=únicas, txtPadsNum=SMD, txtBGA=>10 pines, txtHolesNum=THT, pagetype 3) y el envío de
`GET /order/CalcShip` (cid Argentina = 9, sids 25 FedEx-FICP / 10 FedEx-IP / 1 DHL). Resultado: PCB 5 pcs 6,50;
ensamblado 88 plano (1–5 pcs); envío 48,87–72,73. Componentes los cotizan a mano. Total muestra ≈160–170 USD.

**Commit c003392a (2026-09-12)**: códigos LCSC verificados, pricing.py/pcbway.py, paquete PCBWay, y la
transcripción de esta sesión archivada en `sessions/claude/c5212502-….jsonl`. Todo pusheado. El README raíz
tiene cambios del hilo iOS sin commitear (no son míos: no tocarlos).

**Pendiente antes de pedir**: confirmar LCSC de L9637D, módulo, inductor, SMBJ24A, 1210
10 µF/50 V y 2010 510R; medir el conector real contra el footprint y contra el cuello de la
caja; imprimir la caja y probar el ajuste antes de fabricar en serie.

**How to apply:** al tocar la placa, editar `P`/`N` en `gen_board.py` y regenerar; nunca
editar el `.kicad_pcb` a mano. Verificar el esquema con `gen_schematic.py` (falla si no
coincide con `N`). El usuario quiere avanzar rápido: plantear un riesgo una vez y seguir.
