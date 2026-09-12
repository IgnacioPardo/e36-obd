# PCBWay — pedido de 1 muestra ensamblada (borrador, 2026-09-11)

Placa: **E36 K-line reader rev B**, `hardware/onboard`. Subir `e36-kline-onboard-gerbers.zip` en el
formulario de PCB y, en el paso de ensamblado, `bom-pcbway.csv`, `pnp-pcbway.csv` y
`assembly-drawing-top.pdf`. Todo en este directorio (y en `pcbway-sample-order.zip`).

## Formulario PCB (pcbway.com/QuickOrderOnline.aspx)

| Campo | Valor |
|---|---|
| Board type | Single pieces |
| Size | 90 × 50 mm |
| Quantity | 5 (mínimo práctico; se ensambla 1) |
| Layers | 2 |
| Material | FR-4, TG 150 |
| Thickness | 1.6 mm |
| Min track / spacing | 6/6 mil (la placa usa 0,15 mm mínimos) |
| Min hole size | 0.3 mm |
| Solder mask | Green |
| Silkscreen | White |
| Surface finish | HASL lead-free (ENIG si se quiere mejor plano para el módulo) |
| Via process | Tenting vias |
| Finished copper | 1 oz |
| Remove product No. | Yes |
| Impedance control | No |

## Formulario de ensamblado

| Campo | Valor |
|---|---|
| Assembly quantity | **1** (o 2 para tener repuesto: el setup es igual) |
| Assembly side | Top only |
| Unique parts | 30 |
| SMD parts | 36 |
| THT parts | 2 (J1 conector OBD2, J4 JST XH) |
| BGA/QFN | 0 |
| Parts sourcing | Turnkey: PCBWay compra todo. Alternativa: J1 consignado (ver notas) |
| Sensitive components | Sí: módulo Wi-Fi U3 (no tocar la antena con fixtures) |
| Function test | No; solo inspección visual/AOI |
| Conformal coating | No |

## Notas para "Your instructions" (copiar y pegar)

```
Single assembled sample of a 2-layer automotive diagnostics reader. All SMD on top; two THT parts (J1, J4).
1. J1 is a J1962 OBD2 male right-angle PCB plug (Macchina CCBDM20 or equivalent): 16 pins, 4.00 mm pitch,
   two rows 3.00 mm apart, rows at 2.25 mm and 5.25 mm behind the flange, body overhangs the board edge.
   PLEASE check your connector against the footprint (holes 1.3 mm) before soldering; if it does not match,
   contact us before proceeding. Alternatively we can consign the connector.
2. U3 (ESP32-S3-WROOM-1-N16R8): must be the N16R8 variant (octal PSRAM). Keep the antenna end free of fixture contact.
3. Polarised parts: D1 (TVS) cathode band to pad 1 (+12 V rail); D2/D3 cathode to pad 1; LED1/LED2 cathode pad 1;
   U1 and U2 pin 1 as per silkscreen dot.
4. J2 (1x6 header) is DNP. Mounting holes H1-H4 stay empty.
5. Use the pick-and-place file coordinates (origin bottom-left, mm); rotations are KiCad convention, please
   confirm orientation from the assembly drawing for U1, U2, U3, D1-D3 and LEDs.
6. Lead-free process. No wash residue on the USB-C receptacle.
```

## Precio oficial (motor de cotización de PCBWay, ver `quote-official.md`)

PCB 5 pcs **6,50 USD** · ensamblado 1 placa **88,00 USD** (tarifa plana, igual para 2 o 5) · envío a Argentina
FedEx 48,87 / DHL 72,73 USD. Los componentes los cotizan a mano tras revisar el BOM: estimar 15–25 USD para una
muestra. Total esperado ≈ 160–170 USD con FedEx.

## Archivos

- `e36-kline-onboard-gerbers.zip` — gerbers + taladros (KiCad 10, extensiones Protel).
- `bom-pcbway.csv` — BOM en columnas PCBWay, con fabricante y MPN por línea y el código LCSC como pista.
- `pnp-pcbway.csv` — centroides, origen esquina inferior izquierda, mm, incluye J1/J4.
- `assembly-drawing-top.pdf/.png` — referencias y contornos (F.Fab + serigrafía).
- `board-render-top.png`, `schematic.png`, `top-layer-plot.png` — para el revisor.
- `OBD2_footprint.kicad_mod` — el footprint de J1, por si necesitan las cotas.
