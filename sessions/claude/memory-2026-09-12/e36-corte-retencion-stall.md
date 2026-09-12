---
name: e36-corte-retencion-stall
description: "E36 se apaga al soltar el acelerador — medido: el DME corta combustible y no lo reanuda (carga 0,70 ms a 930 rpm vs 2,70 sano)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 36c9b727-cfdc-4a8c-a588-084fdd452c5e
  modified: 2026-08-15T18:38:47.315Z
---

**Falla activa desde 2026-08-15**, posterior al cambio de TPS. Síntoma: al soltar
el acelerador de golpe el motor se apaga en seco ("pum"), también **en punto
muerto sin carga**, así que la caja está descartada. Continúa [[e36-kline-diagnostic-state]].

**LA MEDICIÓN QUE IMPORTA** (`logs/2026-08-15-TPS-NUEVO-corte-retencion.csv`):

| | ralentí sano | al soltar |
|---|---|---|
| régimen | 900 rpm | 930 rpm |
| **carga (0x0040)** | **2,70 ms** | **0,70 ms** |

A 930 rpm — o sea ya en régimen de ralentí — el DME entrega un cuarto del
combustible que el motor necesita, y no lo reanuda. Transición en una sola
muestra: 2,85 → 0,70. **Es el corte en retención que no se desactiva**, no falta
de aire ni problema eléctrico.

**Descartado con datos:** la batería no cae antes del apagón (13,48 V en la
muestra previa); el ralentí se sostiene bien cuando arranca (790-940 rpm, carga
2,65-2,80 durante 30 s); la mariposa **sí vuelve** a su tope (tres aperturas a
fondo, tres retornos limpios al mismo valor, luego 2 min clavada) — mi conclusión
previa de que "no volvía" era errónea, se basaba en una transición única.

**El DME no registra NADA** en ninguno de los apagones (tres el 15-ago): códigos
100 y 36 con contadores clavados en 50 y freeze frames sin moverse. Coherente:
desde su punto de vista está ejecutando una función normal, con el criterio de
salida equivocado.

**Inconsistencia sin explicar:** el canal de mariposa leyó **22 cuentas** en las
primeras lecturas del 15-ago y después se quedó en **35-36** para siempre,
incluso volviendo solo tras cada acelerada. Los dos valores del mismo sensor
nuevo. Algo se movió una vez y no volvió.

**Prueba pendiente que decide:** poner el TPS viejo y repetir la misma grabación.
Si la carga se queda en ~2,7 al soltar, es el TPS. Si igual cae a 0,7, el
sospechoso pasa a ser el **código 100** (etapa de salida del DME, presente,
freeze frame a 960 rpm = en ralentí).

**Sospecha lateral a verificar con multímetro en los bornes:** leemos 13,1-13,5 V
con el motor andando, y un alternador sano da 13,8-14,2. O está flojo, o nuestra
escala de tensión (×0,0681, sin validar) está mal.
