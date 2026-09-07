# Handoff — app iOS nativa para el panel del E36

Para quien retome esto: el hardware y el firmware **funcionan y están probados
contra el auto**. Lo único que falta es la app. Este documento es el contrato
que tiene que respetar y las trampas que ya pagamos.

---

## 1. Qué existe y anda

Un lector de K-line propio, hecho a mano, leyendo la ECU de un BMW E36 1994
(M43B16, Bosch Motronic 1.7.2).

```
DME 0x10 @ 9600  →  línea K  →  L9637D  →  ESP32-S3  →  BLE
```

Verificado el 2026-09-07 leyendo la memoria de fallas: códigos **100 y 36**,
contadores en 50, condiciones `0x68` y `0x72` — **idénticos byte por byte** a lo
que dio el cable K+DCAN el 15 de agosto. Más las cinco cadenas de ID del DME.

Muestreo medido: **341 ms por lectura, 2,93 Hz.** Contra 1550 ms / 0,65 Hz en
macOS, donde el driver FTDI impone 231 ms por lectura.

Firmware en `firmware/mp/` — MicroPython 1.29, arranca solo al energizar.

---

## 2. El contrato BLE

Esto es lo único que la app necesita saber. **No cambiarlo sin actualizar
`firmware/mp/ble.py`.**

**Dispositivo:** se anuncia con nombre `E36-OBD`.

**Servicio:** Nordic UART (NUS), el "puerto serie sobre BLE" de facto.

| | UUID |
|---|---|
| Servicio | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` |
| RX — la app **escribe** acá | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` |
| TX — la app **se suscribe** acá | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` |

**Comandos:** un carácter ASCII, escrito en RX.

| | |
|---|---|
| `v` | arranca sensores en vivo |
| `s` | detiene |
| `f` | lee la memoria de fallas |
| `?` | ayuda |

Cualquier carácter recibido durante el modo vivo **lo corta**. Ojo con eso: no
mandar nada mientras se quiere seguir recibiendo.

**Notificaciones:** texto, líneas terminadas en `\r\n`. Vienen **partidas en
trozos de 20 bytes** con 12 ms entre uno y otro — el MTU por defecto de BLE.
Hay que acumular en un buffer y cortar por `\n`. Sin eso, las líneas llegan
mutiladas y sin aviso.

**La línea de datos** tiene prefijo `D` y campos separados por espacio:

```
D <rpm> <carga> <refrig> <bateria> <ms>
D 892 2.76 58.5 13.48 341
```

Todo lo demás que llegue es texto legible → al registro.

---

## 3. Rangos y escalas, medidos en este auto

| campo | unidad | qué esperar |
|---|---|---|
| `rpm` | rpm | ralentí 790–940. **SATURA EN 2550** |
| `carga` | ms | ralentí 2,70–2,90. **0,70 = corte de combustible** |
| `refrig` | °C | arranca en ambiente, se estabiliza cerca de 90 |
| `bateria` | V | 13,35–13,48 andando. Debería ser 13,8–14,2 |
| `ms` | ms | ~341. Es el round trip real, sirve de indicador de salud |

**El techo de 2550 rpm es real, no un bug.** `0x003C` es UN byte con escala
×10. Dibujar un tacómetro hasta 7000 miente arriba de ese punto: hay que marcar
la zona sin dato, como hace el panel de macOS.

**Con el motor apagado todo da cero.** El DME no puebla esas posiciones de RAM
hasta que gira. Parece enlace muerto y no lo es — el panel tiene que decirlo.

**`carga` es el canal que importa para la falla que perseguimos.** A 930 rpm
midió 0,70 ms cuando el ralentí sano pide 2,70: corte de combustible en
retención que no reanuda, y el motor se para. Ver
`logs/2026-08-15-TPS-NUEVO-corte-retencion.csv`.

---

## 4. Qué construir

App SwiftUI + CoreBluetooth, pantalla del celular. **No CarPlay** (ver §6).

Mínimo viable:

1. Escanear y conectar a `E36-OBD` (filtrar por nombre o por servicio)
2. Suscribirse a TX, acumular buffer, cortar por línea
3. Parsear las líneas `D` y mostrar los cuatro valores
4. Botones: conectar, en vivo, fallas
5. Mostrar el `ms` / Hz — es el indicador de que el enlace está sano
6. Registro de texto para todo lo que no sea `D`

Deseable después: registro a archivo para analizar después de manejar, y avisar
cuando `carga` cae abajo de 1,5 ms con el régimen en zona de ralentí — que es la
firma del apagado.

Estilo: ámbar sobre negro, tipografía monoespaciada. Es el color de la
retroiluminación del tablero del auto. Referencia visual en
`e36obd/static/dashboard.html` y `docs/cableado.html`.

---

## 5. Requisitos y la trampa que rompe todo

- **Xcode**, ~10 GB
- **Cuenta de desarrollador.** La gratuita instala en el iPhone pero **la app se
  vence a los 7 días** y hay que reinstalar desde Xcode. La paga son 99 USD/año.

**LA TRAMPA:** hay que agregar **`NSBluetoothAlwaysUsageDescription`** al
Info.plist con un texto cualquiera. Sin eso, la app **crashea** al instanciar
`CBCentralManager`, sin mensaje útil. Es lo primero que hay que poner.

Solo un central por vez: si Chrome en la Mac está conectado al ESP32, el celular
no puede. Desconectar uno antes de probar el otro.

---

## 6. Lo que NO se puede, y está verificado

**Una app propia en CarPlay.** El entitlement `com.apple.developer.carplay-*`
lo otorga Apple por pedido y por categoría; diagnóstico vehicular no está en la
lista. Hasta que lo concedan, la entitlement **no aparece en el portal**, así
que no entra en ningún provisioning profile — de desarrollo tampoco. Dev mode
saltea la firma, no esto.

Y aunque saliera: en CarPlay solo se usan las plantillas de Apple. Ni una aguja.

Confirmado por dos fuentes independientes, incluida `carplayhacks.com`, cuyo
negocio es justamente saltar restricciones: *"no documented method for
developing legitimate custom CarPlay apps"*. El camino del jailbreak está
muerto en iOS 17+.

**El WiFi no sirve manejando.** El celular se va solo a la red del estéreo
(`CP-71WA`) para CarPlay inalámbrico y no puede estar en dos redes. Y el ESP32-S3
es **solo 2,4 GHz** mientras CarPlay usa 5 GHz, así que unirse a la red del
estéreo tampoco es posible. Por eso BLE.

**Web Bluetooth en iOS:** sin verificar. La PWA está lista en `docs/ble/` con
manifest e ícono, pero **exige HTTPS** y nunca la publicamos. Si funciona, la
app nativa es innecesaria. Vale probarlo antes de instalar Xcode.

---

## 7. Lo que la app no va a poder mostrar

Pedido y no disponible: **temperatura de aceite** y **posición de marcha**.

Las dos viven en el EGS (caja automática, `0x6C` @ 4800). Y el EGS **no se puede
leer con el motor andando**:

```
motor apagado   →  init OK, ReadRAM OK, ReadFaults OK, 6 bloques de ID
motor andando   →  init OK, muere en el bloque 5 de 6, siempre
```

Probados 15/30/50/80/120 ms de espera entre bytes y 10 sesiones seguidas: cero
éxitos. A 4800 cada bit dura el doble que a 9600, o sea el doble de exposición
al ruido de encendido por byte. El DME a 9600 aguanta.

*(El dueño del auto no está convencido de esta conclusión. Si alguien la vuelve
a probar y anda, mejor — pero probar con datos, no con un solo valor de espera.)*

---

## 8. Trampas que ya pagamos, para no repetirlas

**El nombre del puerto del ESP32 cambia según el modo.** En ejecución, en
descarga, y según el conector. Nunca cablearlo en un script: buscarlo cada vez.
El de la serigrafía **COM** es el puente WCH y es el que conviene — esptool
resetea solo por DTR/RTS, sin botones.

**Los pull-ups internos del L9637D invalidan los tests de "manejado vs
flotando".** Tiene pull-ups en TX, RX y LO, dicho en su primera página. El único
test válido del transceptor es funcional: `TX bajo → RX debe dar 0`.

**Medir de punta a punta, no por tramos.** Los pads del adaptador SOIC→DIP miden
perfecto cuando apoyás una punta encima; eso no prueba que el cable haga
contacto. Una noche entera se fue por ahí.

**El multímetro en `V⎓`, verificado en cada medición.** Una tarde de mediciones
en alterna dio basura — 0 V donde había 12 — y sobre eso se construyeron cinco
hipótesis falsas. Y nunca medir sobre las patas del SOIC: están a 1,27 mm y
puentearlas es un corto de 12 V a masa.

**El `KEYWORDS` del init son 2, no 3.** El DME responde `55 00 81`: el `55` es
el sincronismo y se consume aparte.

---

## 9. Estado del diagnóstico, por contexto

Lo que buscamos no es un panel: es por qué la caja no hace 2→3 ni 3→4.

**Dos ocurrencias del código 100 del EGS**, las dos con freeze frame idéntico
`7A 3C` → motor 3904 rpm, salida 1920 rpm, **relación 2,03**. Las relaciones del
A4S 310R son 2,86 / 1,62 / 1,00 / 0,72: **2,03 no es ninguna**. Pero 1,62 con
25 % de patinamiento del convertidor da 2,03 — segunda patinando cuando debería
ser tercera. Un 2→3 que no entra.

**El alternador.** Tres instrumentos independientes leyendo bajo: nuestro panel,
un ELM327 y el ESP32. 13,35–13,48 V andando cuando corresponden 13,8–14,2. Ya no
es error de escala.

**Próximo paso del diagnóstico:** manejar hasta que falle, apagar, y leer el
freeze frame nuevo. Si la tercera ocurrencia también da 2,03, queda confirmado
que siempre falla el mismo cambio.
