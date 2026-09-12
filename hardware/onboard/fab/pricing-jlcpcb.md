# Precio JLCPCB — placa rev B, ensamblado economico (SMD)

Generado por `pricing.py` el 2026-09-11. Precios de partes desde la API de partes de JLCPCB por codigo LCSC; tarifas de
ensamblado de [help/article/pcb-assembly-price](https://jlcpcb.com/help/article/pcb-assembly-price); PCB 2 capas 90 × 50 mm verde.
USD, sin envio ni impuestos. Las partes las compra JLC al momento del pedido: stock y precio cambian.

## Totales

| Placas ensambladas | Fijos (setup + stencil + 11 partes extendidas × 3.07) | SMT (142 juntas × 0.0016) | Partes (todas las placas) | PCB (5 pcs min.) | **Total** | **Por placa** |
|---|---|---|---|---|---|---|
| 2 | 43.48 | 0.45 | 20.08 | 2.00 | **66.02** | **33.01** |
| 5 | 43.48 | 1.14 | 50.21 | 2.00 | **96.82** | **19.36** |
| 10 | 43.48 | 2.27 | 89.74 | 5.00 | **140.50** | **14.05** |
| 20 | 43.48 | 4.54 | 179.49 | 9.00 | **236.51** | **11.83** |

Los fijos pesan: con 2 placas cada una sale mas del doble que con 10. La PCB se pide de a 5 (oferta de 2 USD); 10 y 20 son estimados.

## Partes (lo que JLC monta)

| Valor | Refs | LCSC | Libreria | Stock | USD c/u (5 placas) | USD c/u (10 placas) | Parte |
|---|---|---|---|---|---|---|---|
| 1A 32V | F1 | C183160 | extendido | 6161 | 0.0741 | 0.0741 | S1206-S-1.0A |
| SMBJ24A | D1 | C123819 | extendido | 57490 | 0.0604 | 0.0604 | SMBJ24A |
| SS34 | D2,D3 | C8678 | basico | 5063399 | 0.0349 | 0.0349 | SS34 |
| 510R 0.75W | R1 | C175041 | extendido | 3968 | 0.0363 | 0.0363 | CR2010F510RE04Z |
| L9637D | U1 | C153038 | extendido | 1239 | 1.7208 | 1.4052 | E-L9637D013TR |
| 100n | C1,C3,C13,C6 | C14663 | basico | 52431790 | 0.0124 | 0.0124 | CC0603KRX7R9BB104 |
| 100k | R2 | C25803 | basico | 24071143 | 0.0041 | 0.0041 | 0603WAF1003T5E |
| 22k | R3 | C31850 | basico | 4248730 | 0.0045 | 0.0045 | 0603WAF2202T5E |
| AP63203 | U2 | C780769 | extendido | 12710 | 1.2019 | 1.0735 | AP63203WU-7 |
| 10u 50V | C10,C11 | C53084458 | extendido | 6761 | 0.3580 | 0.3580 | CC1210X7R50V106MN |
| 100n 50V | C12 | C14663 | basico | 52431790 | 0.0124 | 0.0124 | CC0603KRX7R9BB104 |
| 4.7uH 3.3A | L1 | C78804 | extendido | 20903 | 0.0902 | 0.0902 | SWPA6045S4R7MT |
| 22u 10V | C14,C15 | C45783 | basico | 4925692 | 0.2456 | 0.2456 | CL21A226MAQNNNE |
| USB-C 16P | J3 | C165948 | extendido | 246772 | 0.1858 | 0.1858 | TYPE-C-31-M-12 |
| 5k1 | R5,R6 | C23186 | basico | 23622421 | 0.0019 | 0.0019 | 0603WAF5101T5E |
| ESP32-S3-WROOM-1-N16R8 | U3 | C2913202 | extendido | 37912 | 5.1394 | 4.5165 | ESP32-S3-WROOM-1-N16R8 |
| 10u | C5 | C15850 | basico | 7091690 | 0.0843 | 0.0843 | CL21A106KAYNNNE |
| 10k | R4,R9 | C25804 | basico | 27480456 | 0.0027 | 0.0027 | 0603WAF1002T5E |
| 1u | C7 | C15849 | basico | 8275197 | 0.0175 | 0.0175 | CL10A105KB8NNNC |
| RESET | SW1 | C318884 | basico | 766874 | 0.0205 | 0.0205 | TS-1187A-B-A-B |
| BOOT | SW2 | C318884 | basico | 766874 | 0.0205 | 0.0205 | TS-1187A-B-A-B |
| PWR blanco | LED1 | C2290 | basico | 1183357 | 0.0122 | 0.0122 | KT-0603W |
| 2k2 | R7 | C4190 | basico | 6484777 | 0.0022 | 0.0022 | 0603WAF2201T5E |
| STATUS rojo | LED2 | C2286 | basico | 3937449 | 0.0075 | 0.0075 | KT-0603R |
| 1k | R8 | C21190 | basico | 26339094 | 0.0033 | 0.0033 | 0603WAF1001T5E |
| 36k | R10 | C23147 | extendido | 462429 | 0.0020 | 0.0020 | 0603WAF3602T5E |
| 3k74 | R11 | C23016 | extendido | 17079 | 0.0025 | 0.0025 | 0603WAF3741T5E |
| 4k7 | R12 | C23162 | basico | 26528604 | 0.0030 | 0.0030 | 0603WAF4701T5E |

Partes extendidas (cobran 3.07 USD de carga de alimentador cada una, por pedido): C123819, C153038, C165948, C175041, C183160, C23016, C23147, C2913202, C53084458, C780769, C78804.

## No incluido

- J1: ficha OBD2: sin stock en JLC (C9900166046), comprar aparte y soldar a mano
- J4: THT: soldarla uno mismo, o pedir soldadura manual (+3.58 por pedido, +0.0164 x 3 juntas)
- Envio a Argentina: JLC Global Standard Direct Line ~10–15 USD (2–4 semanas) o DHL/FedEx ~25–40 USD (~1 semana) para un paquete de 300 g.
- Impuestos de importacion: dependen del regimen courier vigente (verificar).
- Ensamblado estandar en vez de economico: setup 25.56 + stencil 8.21 + 1.53 por cada tipo de parte (basica o extendida); no conviene a esta escala.

## Riesgos de stock

- E-L9637D013TR (C153038): 1239 unidades. Es la parte critica y con menos stock; si se agota, JLC ofrece "global sourcing" o se compra en Mouser/LCSC y se suelda a mano.
- La ficha OBD2 de JLC (C9900166046) figura sin stock: la placa se pide sin J1 y la ficha va aparte (Macchina 5 × 19.50 USD, o generica 90° de AliExpress).

## Reproducir

```
python3 hardware/onboard/pricing.py
```
La consulta por codigo es un POST a `https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList` con `{"keyword": "C2913202", ...}`; devuelve `componentPrices` (tramos), `componentLibraryType` (base/expand) y `stockCount`.
