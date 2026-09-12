# PCBWay — cotización oficial (motor de cotización de pcbway.com, 2026-09-12)

Números devueltos por el propio motor de cotización de PCBWay (`/Quote/GetDeliveryDays/` y `/order/CalcShip`,
los mismos endpoints que usa la página de cotización), con los parámetros de esta placa. Sin pedido creado.
USD.

| Concepto | Parámetros | Precio |
|---|---|---|
| **PCB, 5 unidades** | 90 × 50 mm, 2 capas, FR-4 TG150 1,6 mm, 6/6 mil, agujero mín. 0,3, verde/blanco, HASL sin plomo, vías tapadas, 1 oz, sin número de producto | **6,50** (fabricación 24 h) |
| PCB, 10 unidades | ídem | 19,68 |
| **Ensamblado, 1 placa** | lado superior, 30 partes únicas, 36 SMD, 1 de más de 10 pines (módulo), 2 THT, turnkey, sin componentes sensibles | **88,00** (5–6 días) |
| Ensamblado, 2 o 5 placas | ídem | 88,00 (tarifa plana de prototipo: el mismo precio hasta ~20) |
| Envío a Argentina, FedEx FICP | 0,58 kg | 48,87 (4–7 días) |
| Envío a Argentina, FedEx IP | 0,58 kg | 51,81 (4–7 días) |
| Envío a Argentina, DHL | 0,58 kg | 72,73 (3–5 días) |

El motor también tarifó dos servicios lentos que no aparecen en la lista para Argentina (22,76 USD a 66–130 días
y 27,67 USD a 11–33 días); no contar con ellos.

## Lo que NO está en la cotización oficial

- **Componentes**: PCBWay los cotiza a mano después de revisar el BOM (compra en LCSC / Digi-Key / Mouser y recarga
  la gestión). Estimación propia con precios LCSC: ≈ 10 USD por placa (5 son el módulo ESP32-S3), más el
  recargo de compra (20–40 %) y la ficha OBD2 (4–10 USD). Esperar **15–25 USD** de partes para una muestra.
- Impuestos de importación en Argentina.

## Total esperado para 1 muestra ensamblada

| | USD |
|---|---|
| PCB (5 pcs) | 6,50 |
| Ensamblado (1 pc) | 88,00 |
| Componentes (estimado) | 15–25 |
| Envío FedEx FICP | 48,87 |
| **Total** | **≈ 160–170** (≈ 185–195 con DHL) |

La segunda placa ensamblada sale casi gratis (mismo 88 USD; solo suma partes): conviene pedir 2.
