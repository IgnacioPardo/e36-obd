# Validación de la app E36

La demo y las pruebas automáticas no validan la radio del iPhone ni el enlace contra el auto.

## Comprobaciones automáticas

Desde la raíz del repositorio:

```sh
swift test --package-path ios/Core
python3 -B -m unittest discover -s firmware/tests -v
xcodebuild -project ios/E36OBD.xcodeproj -scheme E36OBD \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro,OS=18.6' \
  -derivedDataPath ios/DerivedData CODE_SIGN_IDENTITY=- test
```

Elegir un dispositivo que aparezca en `xcrun simctl list devices available` y que Xcode muestre como elegible. Si Xcode indica que falta la plataforma de su SDK, instalarla desde **Settings → Components**, o con `xcodebuild -downloadPlatform iOS`.

Para ejecutar los targets de pruebas directamente sobre un simulador ya instalado:

```sh
python3 ios/tools/test_simulator.py --device UUID_DEL_SIMULADOR
```

El script conserva el resultado `.xcresult` y las capturas bajo `ios/TestResults/`. En Xcode 26.2, si `actool` exige el runtime 26.2 que todavía no está instalado, agregar `--without-icon`: permite comprobar el código completo y las pruebas en iOS 18.6, omitiendo exclusivamente el catálogo del ícono. Ese resultado **no valida la compilación del catálogo**. La compilación normal conserva el ícono y requiere completar los componentes de Xcode.

El script firma los productos del simulador de forma ad hoc (`CODE_SIGN_IDENTITY=-`) para que Xcode incluya los entitlements simulados del App Group. No necesita una identidad de desarrollo para el simulador. Desactivar toda la firma omite esos entitlements y hace fallar la prueba de almacenamiento compartido del widget.

Las pruebas del núcleo cubren límites de fragmentos y UTF-8, desbordamiento, formatos BLE, RAM vacía, secuenciación de comandos, restauración, alertas, transacciones, recuperación, CSV y conservación de picos/huecos en gráficos. Las pruebas de interfaz guardan capturas de las dos orientaciones y recorren grabación, fallas, avisos, reconexión, recuperación tras cierre, texto grande e historial. Los tests de firmware usan el código real con módulos de hardware sustituidos y comprueban respaldo, verificación y recuperación del actualizador con un transporte USB simulado.

La revisión del tablero incorpora comprobaciones de coordenadas: cada esfera principal debe mantener x, y, ancho y alto (tolerancia 0,5 pt) al aparecer uno o varios avisos, apagar el motor simulado, saturar la lectura, reconectar y cerrar paneles. Los controles principales deben conservar áreas de al menos 44 × 44 pt. Las capturas se revisan también visualmente: estas aserciones no detectan por sí solas jerarquía, contraste o texto incorrecto.

### Resultado local — 7 de septiembre de 2026

- **19 pruebas Swift del núcleo**, **8 pruebas Python de firmware/actualizador** y **5 pruebas XCTest** (3 unitarias y 2 recorridos de interfaz): todas aprobadas, sin pruebas omitidas.
- Xcode 26.2, simulador iPhone 16 Pro con iOS 18.6; compilación mediante `test_simulator.py --without-icon`. El código de la app y la descripción Bluetooth incluida en el producto se verificaron. El catálogo del ícono sigue pendiente del runtime 26.2 requerido por `actool`.
- Capturas revisadas en ambas orientaciones y con el máximo tamaño de texto; se corrigieron la actualización del OBC, el área táctil de las sesiones y el solapamiento del selector de demo. Se abrió la hoja de exportación con sus dos CSV.
- Un CSV de demostración conservó 32 muestras originales, 17 eventos, tres inicios de alerta y los estados `populated`/`unpopulated`.
- El iPhone 17 Pro detectado usa iOS 27.0 beta (24A5430a), con Developer Mode desactivado; no hay identidades de firma válidas en este Mac. No se instaló en ese dispositivo y su compatibilidad con Xcode 26.2 no se da por validada.
- No se detectó un ESP32 en un puerto USB. **No se modificó firmware en hardware**. Quedan pendientes todas las comprobaciones físicas de la lista siguiente, incluida la captura de 30 minutos.

### Revisión de diseño — 7 de septiembre, 23:20 ART

- Se recompiló la interfaz revisada y se repitieron las **5 pruebas XCTest**, todas aprobadas. Esta revisión conserva el núcleo de adquisición y persistencia de la validación anterior.
- Se comprobaron coordenadas estables durante avisos individuales y simultáneos, motor apagado, saturación, reconexión y cierre de paneles, además de las áreas táctiles mínimas y el contador de sesiones con texto accesible.
- Revisión visual de las capturas finales: vertical, horizontal, fallas, ajustes, temperaturas, historial y recuperación con tamaño de texto máximo. Se corrigieron la separación entre escalas y valores, el tamaño del control principal horizontal, el borde del fondo de los paneles y la etiqueta de cantidad de sesiones.
- Resultado: `ios/TestResults/20260908T021856419293Z/Tests.xcresult`. Capturas exportadas en `.context/qa/redesign-final/`. Se utilizó `--without-icon`; continúa pendiente la validación del catálogo con el runtime correspondiente.

### Ajuste al cuadro de referencia — 7 de septiembre, 23:43 ART

- Se aprobaron nuevamente las **5 pruebas XCTest** con las escalas del cuadro E36, agujas planas, centros negros, indicadores auxiliares en abanico y displays segmentados.
- Las comprobaciones de posición incluyen también la batería en horizontal. Se verifica que admisión y estado de grabación queden dentro de la altura de la barra inferior y que el tacómetro quede por encima.
- Resultado: `ios/TestResults/20260908T024152140241Z/Tests.xcresult`; capturas revisadas en `.context/qa/bmw-reference/`. La compilación utiliza el mismo `--without-icon` documentado arriba. El pequeño cambio posterior al pictograma de batería se comprueba visualmente en el simulador.

### Widget — 8 de septiembre, 00:08 ART

- **25 pruebas del núcleo** (19 existentes y 6 del widget) y **7 pruebas XCTest** (5 unitarias y 2 de interfaz), todas aprobadas. Se comprobaron la extensión embebida, el App Group real del simulador, la separación ESP32/demo, los datos ausentes o corruptos y los límites de publicación.
- Resultado: `ios/TestResults/20260908T025912280891Z/Tests.xcresult`. Compilación con firma ad hoc y `--without-icon` en iPhone 16 Pro, iOS 18.6. La firma permite comprobar el contenedor compartido; no constituye firma para un iPhone físico.
- Se encontró **Instrumento E36** en la galería del sistema, se agregó a la pantalla de inicio y se cambió su configuración. El origen ESP32 sin lecturas muestra un guion; Demostración conserva su rótulo DEMO. El menú ofrece los cinco sensores.
- Se contrastaron las lecturas del widget con las de la app y su archivo compartido: refrigerante a 112,5 °C con aviso y RPM saturadas como `2550+`. Se accionó la flecha sin abrir la app y se comprobó que la antigüedad de la muestra continúa visible. Capturas en `.context/qa/widgets/`.
- Esta comprobación verifica WidgetKit en la pantalla de inicio. **No valida CarPlay físico**, su contraste al retirar el fondo ni las actualizaciones con BLE real. El runtime iOS 26.2 seguía descargándose; la compilación del catálogo del ícono también sigue pendiente. Ver [WIDGETS.md](WIDGETS.md) para instalación y comprobaciones en el vehículo.

### Actualización física del ESP32 — 8 de septiembre, 11:09 ART

- Detectado por USB en `/dev/cu.usbmodem5C4C0875701`: ESP32-S3 con Octal-SPIRAM, MicroPython 1.29.0 del 24 de agosto. Los archivos `ble.py` y `main.py` del dispositivo coincidían con las versiones previas del repositorio.
- Se repitieron las **8 pruebas de firmware y del actualizador**, todas aprobadas. Se reemplazó únicamente `ble.py` para agregar admisión al final del mensaje `D`; no se reflasheó MicroPython ni se modificó K-line.
- Respaldo anterior: `.context/firmware-backups/20260908T140820825057Z/ble.py`. La lectura posterior del dispositivo coincide byte por byte con `firmware/mp/ble.py`; SHA-256 instalado: `0b71e5f027fb0cbfd0f4f568807d8b6941025c7db4405d792751606ec7f6a1f3`.
- Tras reiniciar, la consola confirmó `anunciando como E36-OBD` y el arranque del bucle BLE sin excepciones. Registro: `.context/esp-boot.log`; comprobación de respaldo y hashes: `verification.json` junto al respaldo. Se cerró la consola sin interrumpir el panel.
- Este resultado verifica la instalación y el arranque en hardware. No verifica una conexión BLE desde el iPhone, muestras reales del DME ni continuidad con CarPlay; esas pruebas siguen pendientes.

Para volver exactamente al BLE anterior:

```sh
python3 ios/tools/update_ble.py --restore .context/firmware-backups/20260908T140820825057Z/ble.py
```

### Instalación en el iPhone — 8 de septiembre, 11:27 ART

- **E36 OBD 1.0 (1) instalado y abierto en el iPhone 17 Pro**, conectado por USB, con iOS 27.0 beta (24A5430a). Developer Mode y los servicios de desarrollo quedaron habilitados. `devicectl` confirmó la instalación, el lanzamiento y que el proceso de la app seguía ejecutándose.
- La compilación completa para dispositivo con Xcode 26.2 (17C52) terminó correctamente. Incluye el catálogo del ícono, la descripción Bluetooth y `E36OBDWidgets.appex`; ya no se omite `Assets.xcassets`. Se verificaron las firmas de ambos bundles y su App Group en los perfiles instalados.
- Se utilizó el **Personal Team** del usuario. El App Group se registró desde Signing & Capabilities y se incluyó en ambos perfiles. El perfil de la app vence el **15 de septiembre de 2026 a las 11:23 ART**; renovar compilando y reinstalando conserva los datos. La configuración local del equipo está en `ios/Local.xcconfig`, ignorado por git.
- Producto: `.context/iphone-build/Build/Products/Debug-iphoneos/E36OBD.app`. Evidencia: `.context/iphone-final-build.log`, `.context/iphone-install-result.json`, `.context/iphone-launch-verified.json` y `.context/iphone-sideload-verification.json`.
- Esta prueba confirma instalación y arranque con la beta del teléfono. No confirma todavía recepción BLE del ESP32, consultas al DME, widgets en CarPlay físico ni captura prolongada con pantalla bloqueada.

### Diagnóstico de BLE y captura — 8 de septiembre, 11:44 ART

- El registro SQLite del iPhone confirmó descubrimiento de `E36-OBD` a −52 dBm, Bluetooth autorizado, conexión NUS y suscripción TX. La conexión inicial funcionó al omitir la opción de demora con valor cero.
- Se guardó una muestra real a las 11:38:59: **990 rpm, 3,30 ms de carga, 21,4 °C de refrigerante, 13,62 V, 19,1 °C de admisión y 440 ms de consulta**. El firmware confirmó `detenido (1 muestras)` al detener esa captura. Esto confirma recepción y almacenamiento del formato ampliado; no confirma continuidad.
- En otro intento, el firmware notificó `se corto: sin respuesta de la ECU`. La app inició recuperación, pero CoreBluetooth rechazó inmediatamente las demoras enviadas como `Double`, con `CBErrorDomain (1)`. El rechazo anterior a la demora provocaba un bucle de reintentos; la captura aportada por el usuario muestra ese bucle.
- Se reemplazó la demora por un `NSNumber` entero de segundos y se detiene la recuperación automática si iOS rechaza los parámetros, evitando el bucle inmediato. Se conserva cada etapa de descubrimiento/conexión y el dominio/código del error en el registro, usando la cola existente de almacenamiento.
- **25 pruebas del núcleo, 7 unitarias de iOS y 2 de interfaz aprobadas**. Las dos pruebas nuevas verifican opciones iniciales ausentes y demoras enteras de 1/2/5/10/30 segundos. Tras cambiar el tipo de demora se recompiló para dispositivo y se repitieron las 7 unitarias. La interfaz no cambió.
- La última compilación está instalada y su firma verificada. **La reconexión con demora entera todavía no está validada en hardware**: iOS rechazó el lanzamiento de prueba porque el teléfono estaba bloqueado. El ESP32 no aparece actualmente como puerto USB en el Mac; queda pendiente el trazado directo de K-line y una captura continua.
- Evidencia: `.context/ble-debug-live-check/`, `.context/ble-fix-simulator-tests.log`, `.context/ble-reconnect-unit-tests.xcresult`, `.context/ble-reconnect-install.json` y `.context/ble-reconnect-smoke-launch.json`.

Una compilación Debug admite una prueba de conexión BLE con demora de un segundo, sin iniciar captura ni borrar sesiones:

```sh
xcrun devicectl device process launch --device ID_DEL_IPHONE com.ignaciopardo.e36obd --ble-smoke-test
```

Usarla con la app detenida y el iPhone desbloqueado. Nunca usar `--uitesting` en el teléfono real: ese argumento borra la base local para las pruebas del simulador.

### Traza física de recuperación — 9 de septiembre, 16:18 ART

- El ESP32 volvió a estar disponible en el puerto USB detectado `cu.usbmodem5C4C0875701`. Se respaldaron `main.py`, `ble.py`, `kline.py` y `boot.py` en `.context/ble-sep09/firmware/`. Los tres primeros coinciden byte por byte con el repositorio; no se modificaron archivos del dispositivo.
- Se reinició el panel y se cargaron envoltorios de diagnóstico **solo en RAM** mediante `mpremote resume run .context/ble-sep09/trace.py`. Registran operaciones BLE, mensajes y traceback al fallar K-line. Un reinicio elimina esa instrumentación. Para observar un panel en ejecución, usar `resume`: el `mpremote` instalado hace soft reset por defecto antes de `exec`, `run` o acceso a archivos.
- **La recuperación BLE con demoras enteras funciona en el teléfono físico.** Tras cada error del DME, la consola confirmó desconexión, publicidad, reconexión, `detenido` y un nuevo intento `vivo`. Los intervalos entre el error y la siguiente sincronización BLE fueron 2,595 / 3,875 / 6,675 / 11,555 / 31,716 segundos: corresponden al backoff 1/2/5/10/30 más el establecimiento del enlace. Después continuó usando aproximadamente 30 segundos; no apareció el bucle inmediato de la captura anterior.
- Los **nueve errores** recogidos hasta este corte son `sin respuesta de la ECU` en `kline.init`, esperando el primer byte con `_rx(500)` en la línea 142. No llegó siquiera el sincronismo `0x55`: estos intentos fallaron antes de identificación, sensores o memoria de fallas. No hubo muestras ni códigos en este tramo. La conexión física al vehículo y su estado de contacto todavía deben confirmarse; esta evidencia no permite atribuir el fallo a cableado, alimentación o temporización.
- La última imagen aportada coincide con el registro antiguo del **8 de septiembre a las 11:39:50**. El registro extraído hoy conserva esos eventos históricos; no demuestra que el bucle inmediato continúe en la compilación actual.
- El iPhone estuvo disponible al inicio y ejecutó la app, pero después dejó de estar disponible para `devicectl`. La captura por USB del ESP32 continúa de forma independiente. Evidencia: `.context/ble-sep09/serial-trace.log`, `.context/ble-sep09/capture-summary.json`, `.context/ble-sep09-phone-before/` y `.context/ble-sep09-devices-current.json`.
- Se confirma recuperación del transporte BLE. **La captura continua de datos reales y la lectura completa de fallas siguen pendientes** de una ECU que responda.

### Contacto en posición 2 y prueba directa — 9 de septiembre, 16:29 ART

- El usuario confirmó contacto en **posición 2, motor apagado**. La lectura de fallas transmitida por BLE recibió `error: sin respuesta de la ECU` y luego la ayuda completa hasta `?  esta ayuda`. Esto confirma físicamente la finalización mediante ayuda, incluso cuando el DME no responde; no es una memoria sin fallas.
- Se pausó BLE y se ejecutó `.context/ble-sep09/direct_kline.py` directamente por USB, después de soft reset, sin otro hilo consultando la ECU. GPIO17 alto/bajo/alto produjo cinco lecturas consecutivas de GPIO18 **1/0/1**, respectivamente: el eco local TX/RX funciona.
- La conexión directa a DME `0x10` falló esperando el sincronismo inicial. Un segundo intento con **2.000 ms** para la primera respuesta, en lugar de 500 ms, tampoco recibió ningún byte. La captura está en `.context/ble-sep09/direct-kline.log`. Se restauró el timeout, se dejó TX alto y se reinició el firmware normal; no se grabaron cambios en sus archivos.
- Se reanudó la traza BLE en `.context/ble-sep09/serial-trace-after-probe.log`. Otra lectura de fallas terminó con el mismo error de ECU y la ayuda completa. El usuario confirmó posteriormente que el cableado del ESP es correcto; la investigación continúa sobre el inicio de sesión, sin atribuir el fallo al cableado.
- Se corrigió la interfaz: un error de lectura ya **no muestra el checkmark ni “0 registros”**. La demo incorpora `DME sin respuesta` para reproducir errores de apertura, interrupción en vivo y lectura de fallas. La prueba de interfaz verifica error visible, botón nuevamente habilitado y ausencia del resultado exitoso.
- **7 pruebas unitarias y 3 de interfaz aprobadas**, incluida la nueva regresión. Resultado: `ios/TestResults/20260909T192550028418Z/Tests.xcresult`; captura revisada en `.context/ble-sep09/qa/79902710-76D1-4495-BE15-FF2B18D5941A.png`.
- La app completa para iPhone compiló y pasó la verificación de firma. **Esta corrección visual todavía no está instalada:** tanto `devicectl` como `idevicescreenshot` dejaron de encontrar el iPhone. El usuario autorizó capturas remotas; se necesita volver a conectar el teléfono al Mac para realizarlas y actualizar la app.

### Temporización y recepción UART — 9 de septiembre, 16:35 ART

- Pruebas exclusivas por USB, sin BLE ni otro hilo de adquisición, cargadas solo en RAM. Se comparó el inicio original con dos intentos omitiendo el vaciado de RX posterior a crear el UART. Los tres fallaron antes del primer byte. No hubo bytes descartados por ese vaciado.
- La secuencia GPIO para `0x10` se reflejó correctamente en RX en cada cambio, también después de reutilizar el UART. Los intervalos medidos fueron aproximadamente **200,05–200,08 ms**. Crear el UART llevó **0,858–0,913 ms**; estos intentos no respaldan las hipótesis de pérdida de control del pin ni de un vaciado tardío de la respuesta.
- El UART a 9600 baudios transmitió un byte `0x55` y recibió exactamente su eco. Tras **10 segundos de reposo**, se observó RX durante dos segundos después del wake-up: **cero cambios de nivel y ningún byte**. Se repitió sin crear el UART, con el mismo resultado. Los mayores intervalos entre observaciones fueron 31 y 27 µs, respectivamente. Esto describe la señal observada en GPIO18; no determina por sí solo la causa de la falta de respuesta del DME.
- Evidencia y scripts reproducibles: `.context/ble-sep09/uart-probe.log`, `uart_probe.py`, `rx-probe.log` y `rx_probe.py`. Se reinició el panel normal, se verificó la publicidad y se restauró la traza en `serial-trace-after-uart-probes.log`. **No se modificaron archivos del ESP.**
- Se solicitó apagar el contacto durante diez segundos y volver a posición 2, con el motor apagado, para comprobar si cambia el estado de la sesión del DME. Esa prueba necesita confirmación del usuario antes de ejecutarse. La captura continua sigue sin estar validada.

### Actualización del iPhone — 9 de septiembre, 16:40 ART

- El iPhone 17 Pro volvió a estar accesible mediante CoreDevice por red local. Se respaldó la base antes de actualizar en `.context/ble-sep09-phone-reconnected/`. La firma completa del producto volvió a verificarse.
- **La corrección de la lectura fallida de fallas quedó instalada y abierta en el teléfono.** `devicectl` confirmó instalación y lanzamiento del nuevo bundle; se verificaron los procesos de la app y su widget. Evidencia: `.context/ble-sep09/iphone-fault-fix-install.json`, `iphone-fault-fix-launch.json` e `iphone-processes-after-update.json`.
- La copia posterior en `.context/ble-sep09-phone-after-update/` conserva las **seis sesiones y la única muestra original**. Los eventos pasaron de 17.561 a 17.583. No se utilizaron argumentos que borraran datos ni se desinstaló la app.
- Otra lectura física de fallas completó `error: sin respuesta de la ECU` seguido de la ayuda hasta `?  esta ayuda`. La traza del ESP vuelve a situar el fallo antes del primer byte de sincronismo. La actualización corrige la presentación del error; no resuelve ni valida la captura continua.
- No se obtuvo una captura remota del teléfono: `idevicescreenshot` no pudo abrir la conexión, la alternativa DVT agotó su espera y Xcode mostraba `Take Screenshot` deshabilitado. La comprobación visual de esta corrección sigue siendo la del simulador; instalación, lanzamiento y conservación de datos sí se verificaron en el dispositivo.

### Cierre KWP71 y prueba con motor encendido — 9 de septiembre, 16:54 ART

- Después del ciclo de contacto solicitado, el DME respondió: códigos **100 / condición 0x68** y **36 / condición 0x72**, ambos con 50 ocurrencias. Se recibieron muestras continuas de RAM sin poblar con el motor apagado. Las capturas `IMG_4718.PNG` e `IMG_4719.PNG` aportadas por el usuario muestran una lectura correcta y una lectura posterior fallida; la segunda ya no afirma “0 registros”.
- Se reprodujeron **dos fallos al pasar de En vivo a Fallas**: la captura se detenía correctamente, pero el siguiente wake-up no recibía sincronismo. El panel BLE no enviaba `DISCONNECT` al terminar una operación, a diferencia del lector de fallas por consola. Una prueba en RAM envió ese bloque antes del siguiente `conectar`: se confirmaron **cuatro cierres reconocidos y dos ciclos En vivo → Fallas → En vivo completos**, sin esos errores. El usuario confirmó el resultado. Evidencia: `.context/ble-sep09/serial-session-close-probe.log` y `session_close_probe.py`.
- Se implementó el cierre en `ble.py` al terminar Fallas o una captura, también después de una desconexión BLE. Todo acceso K-line permanece en el hilo de adquisición, después del bloque en curso. Si falla un intercambio, se invalida la sesión y no se envía un cierre sobre un bloque incierto. Se conservan los UUID, comandos BLE, formato de sensores, fragmentación y la barrera de ayuda.
- **12 pruebas de firmware y actualización aprobadas**. Las regresiones simulan una ECU que rechaza un wake-up sobre una sesión abierta, tres ciclos de lectura, fallos de apertura/intercambio/cierre y pérdida de BLE durante una muestra. Registro: `.context/ble-sep09/session-close-tests.log`.
- Durante el arranque del motor se recibieron **39 muestras con RPM > 0**, desde el giro de arranque hasta ralentí, durante 17,227 segundos en el reloj del ESP. Las últimas muestras estaban alrededor de 1.000 rpm y 13,6 V. Luego falló `_rx` dentro de `recv_block`, en medio de una respuesta a ReadRAM. El usuario informó que ocurrió al superar aproximadamente 1.200 rpm; **el último valor recibido fue 1.050 rpm y no se ha establecido un umbral reproducible**. En ese momento no se detuvo ni reinició el ESP ni se instaló firmware.
- El iPhone guardó **las 622 muestras** anunciadas por el firmware en los cinco tramos de esa sesión: 16 + 18 + 270 + 3 + 315. Permanecieron en la misma sesión UUID `0A7ADC02-9B96-4891-9D33-CE7756C809D7`, con pausas registradas. La consola USB conserva 621 líneas parseables; falta una en el tramo que coincide con la carga/reconexión de la instrumentación. Esto no corresponde a una muestra perdida en el iPhone. Evidencia: `.context/ble-sep09-phone-engine-running/` y `.context/ble-sep09/phone-serial-count-comparison.json`.
- Con el flujo ya detenido, se instaló y verificó **solo `ble.py`** a las 16:53. Respaldo: `.context/firmware-backups/20260909T195311069706Z/ble.py`; SHA-256 instalado: `9401c0afb786e5d374675be35c47f4d2a7d46c639632f10ddd8e6a20fb7272b5`. La lectura posterior coincide con el archivo local y el respaldo coincide con la versión anterior. Se verificó BLE activo después del reinicio.
- Se restauró instrumentación en RAM, con un buffer de los últimos 80 eventos de bytes que solo se imprime ante un error. Traza actual: `.context/ble-sep09/serial-permanent-fix.log`; cargador: `post_update_trace.py`. **Quedan pendientes la repetición física después de esta instalación y el diagnóstico del corte al acelerar.** La prueba con el motor encendido no valida todavía una captura continua prolongada ni CarPlay.

Para deshacer únicamente esta corrección del panel BLE:

```sh
python3 ios/tools/update_ble.py --restore .context/firmware-backups/20260909T195311069706Z/ble.py
```

### Repetición con traza de bytes — 9 de septiembre, 16:56 ART

- La versión instalada recibió **38 muestras durante 16,828 segundos**, guardadas también en el iPhone. Hubo diez lecturas por encima de 1.200 rpm, dos saturadas en 2.550 rpm y varias lecturas posteriores al volver al ralentí. La última muestra transmitida fue 940 rpm. Este recorrido descarta que la app esté cortando el flujo al superar 1.200 rpm.
- La última respuesta RAM llegó completa: longitud `0x0E`, secuencia `0xA5`, título `0xFE`, once bytes `C9 52 5C 1C 55 18 61 F1 05 F7 3C` y terminador `0x03`. El ESP envió `03 A6 09 03`; el DME reconoció sus tres primeros bytes con `FC 59 F6`. Después del eco local del terminador no llegó el siguiente bloque durante los 1.200 ms de espera. Los reintentos posteriores volvieron a fallar antes del sincronismo inicial.
- Evidencia: `.context/ble-sep09/rev-repeat-summary.json`, `rev-repeat-phone-summary.json`, `serial-permanent-fix.log` y `.context/ble-sep09-phone-rev-repeat/`. No se reinició ni modificó el ESP durante ese recorrido; la instrumentación imprime el buffer de bytes únicamente cuando falla una lectura.
- Se preparó una prueba **solo en RAM** con `INTER_BYTE_MS = 15` después de conectar, frente a los 5 ms originales. El wake-up y la identificación conservan la temporización anterior. Todavía no se considera una solución ni se guardó en `kline.py`; el cambio requiere la siguiente conexión y una repetición con ralentí y aceleración. Script: `.context/ble-sep09/timing15_probe.py`; captura: `serial-timing15-probe.log`.

### Comparación de temporización — 9 de septiembre, 17:02 ART

- La prueba temporal de 15 ms tampoco mantuvo el flujo: **23 muestras durante 16,105 segundos**, con consultas de 663–760 ms. Las primeras lecturas fueron de ralentí; las últimas incluyeron 1.430, 1.360, 1.320 y 1.290 rpm. No se completaron treinta segundos de ralentí antes de acelerar, por lo que no se puede separar todavía una dependencia del régimen de una dependencia del tiempo.
- El siguiente bloque RAM quedó incompleto: longitud `0x0E`, secuencia `0x69`, título `0xFE` y diez de los once bytes de datos. Después de recibir `0xD8`, el ESP transmitió su reconocimiento `0x27` 15,057 ms más tarde y recibió el eco local. No llegó el byte restante ni el terminador antes del timeout de 1.200 ms. El firmware anunció `detenido (23 muestras)`. Evidencia: `.context/ble-sep09/serial-timing15-probe.log`.
- El respaldo posterior del iPhone conserva las **23 muestras**, con todos los valores de sensores y duraciones de consulta idénticos y en el mismo orden que las líneas USB. La sesión `7DAFFF1B-1771-4E1F-A8CB-F8D0D3ED5D7F` registra el error, la recuperación del enlace y la parada explícita posterior. Evidencia: `.context/ble-sep09-phone-timing15/` y `timing15-phone-summary.json`.
- Se restauraron los **5 ms originales**, sin modificar `kline.py` en disco. Se cargó otra comparación solo en RAM: cinco lecturas de un byte para los cinco sensores, en lugar de una lectura de once bytes. Conserva el formato BLE, pero aumenta el tiempo de consulta y los campos se leen secuencialmente. **Es una prueba diagnóstica pendiente, no un cambio de producto ni una solución validada.** Script: `.context/ble-sep09/short_read_probe.py`; captura: `serial-short-read-probe.log`. Reiniciar el ESP elimina ambas modificaciones temporales.

### Comparación con el cliente de escritorio y recuperación local — 9 de septiembre, 17:19 ART

- Se cancelaron las pruebas físicas adicionales a pedido del usuario y se retiró de RAM la comparación de cinco lecturas. La implementación conserva **una consulta contigua de once bytes**. No se solicitó otro arranque ni aceleración.
- `e36obd/live.py` maneja los errores dentro de `LiveReader.sample()`: intenta cerrar la sesión anterior, cierra el puerto y reconstruye KWP71 hasta cinco veces. El panel BLE no había portado ese comportamiento: emitía `se corto` y terminaba la adquisición ante el primer error. La app interpretaba ese mensaje como motivo para restablecer Bluetooth, aunque las muestras transmitidas habían llegado completas. Esta diferencia de recuperación está comprobada en el código.
- Los CSV del cliente de escritorio `logs/rec_20260815-151925.csv` y `logs/rec_20260815-153104.csv` contienen huecos de **12,664 y 13,207 segundos**, respectivamente, seguidos por nuevas muestras. En ambos casos la siguiente lectura es RAM sin poblar, por lo que esos archivos no prueban por sí solos la causa del primer corte ni continuidad durante esos huecos. Comparación reproducible: `.context/ble-sep09/desktop-recovery-comparison.json`.
- Se portó la recuperación al worker del ESP: cierre de mejor esfuerzo como el cliente de escritorio, liberación del UART, TX alto e inicialización completa antes de otra lectura. El enlace BLE y el contador de muestras permanecen activos. `recuperando DME (N/5): motivo` informa el progreso; Detener, Fallas y pérdida de BLE cancelan los reintentos. La app conserva la misma sesión, marca el hueco inmediatamente, suspende alertas y muestra `Reconectando DME…`; no envía `v` durante esa recuperación, tampoco al restaurarse iOS. Un intento sin progreso durante 30 s o el agotamiento informado por el ESP mantiene la salida de recuperación existente.
- Se corrigieron diferencias adicionales del transporte: se eliminó el vaciado de RX antes de cada transmisión, se adoptaron los 10 ms entre bloques y los 2 s de espera por byte del lector de escritorio, y la identificación incompleta deja de contarse como conexión correcta. Se verifica el eco de la keyword y el terminador; NACK no se interpreta como datos. **No se atribuye el primer byte ausente a ninguna de estas diferencias sin evidencia adicional.** El defecto confirmado que se corrige es el manejo y la recuperación del error.
- **26 pruebas de firmware/actualización y 22 pruebas Swift Core aprobadas**. Incluyen intercambio ReadRAM con los mismos bytes enviados por el cliente de escritorio, respuesta demorada, byte faltante, limpieza tras fallo, cancelación, restauración, límites de tiempo y rollback de ambos archivos si se corrompe la segunda copia. Un escenario idéntico con un fallo después de 38 muestras detiene el firmware anterior en 38 y permite al nuevo completar 600 muestras simuladas: `.context/ble-sep09/recovery-before-after.json`. Otra prueba incorpora errores repetidos y un intento de conexión fallido. Estos resultados son de simulación; no se presentan como validación física con motor encendido.
- La corrección requiere `ble.py` y `kline.py`. El actualizador incorpora `--include-kline`, respaldo de ambos antes de escribir, verificación y restauración del par; conserva la opción antigua de actualizar solamente BLE. **Instalados y verificados por lectura a las 17:18**, con respaldo en `.context/firmware-backups/20260909T201849064346Z/`. La comprobación posterior al reinicio confirmó BLE activo, timeout de 2.000 ms, espera entre bloques de 10 ms y ausencia del experimento temporal. No se iniciaron consultas al vehículo para esta comprobación.
- La nueva app se compiló, verificó su firma, **instaló y abrió en el iPhone** sin argumentos de prueba. Se respaldaron las sesiones antes y después. Pasaron además **7 pruebas de app/widget y 3 de interfaz**; resultado `ios/TestResults/20260909T201627737848Z/Tests.xcresult`. Evidencia de instalación, hashes y conservación de datos: `.context/ble-sep09/recovery-verification.json`, `recovery-firmware-install.log`, `recovery-iphone-install.json` y `recovery-iphone-launch.json`. No se afirma validación prolongada de motor encendido para esta versión.

### Demoras observadas después de la recuperación — 9 de septiembre, 17:28 ART

- El usuario realizó otra captura con la versión instalada, sin solicitarle otro recorrido. La sesión `2F781B3A-236B-475B-983E-CCDBBB69896E` conserva **96 muestras**, consultas de mediana **441 ms** e intervalos normales de mediana **455,24 ms (2,20 Hz)**. Dos pérdidas de respuesta se recuperaron conservando BLE y la sesión: huecos de **10,95 y 11,25 s**, de 980 a 970 rpm y de 1.190 a 940 rpm, respectivamente. Queda físicamente comprobada la recuperación en esos dos episodios; no la continuidad sin cortes.
- La apertura inicial tardó 6,03 s. En los dos episodios, desde `recuperando DME` hasta `en vivo` transcurrieron 8,37 y 8,43 s: además de la apertura, hay un intento de cierre que puede agotar otros 2 s y la espera de 300 ms. A esto se suma la detección inicial del byte faltante y la primera consulta. El registro posterior contiene intentos sin sincronismo; el estado de contacto en ese tramo no está confirmado y no se atribuye su causa. Evidencia: `.context/ble-sep09-phone-recovery-lag/`, `recovery-lag-summary.json` y `cleanup-lag-analysis.json`.
- Se limitó `DISCONNECT` a **300 ms totales**, compartidos por ecos y acuses, manteniendo los 2 s de las lecturas normales. Esto evita gastar otra espera completa sobre una sesión fallida; el ahorro esperado en ese caso es de unos **1,7 s**, todavía no medido en el vehículo. Los 2,6 s de reposo y el wake-up de 5 baudios se conservan. La causa del primer intercambio perdido al acelerar sigue sin estar identificada por la traza disponible.
- **28 pruebas de firmware/actualización aprobadas**, incluidas despedida normal y demora repartida entre varios bytes que no puede multiplicar el plazo de 300 ms. La corrección de `kline.py` quedó instalada, verificada por lectura y reiniciada, con respaldo en `.context/firmware-backups/20260909T202726797361Z/`. El archivo `ble.py` ya estaba actualizado y no cambió de contenido. No se modificó la app. Registros: `cleanup-deadline-tests.log`, `cleanup-deadline-install.log` y `cleanup-deadline-boot.log` dentro de `.context/ble-sep09/`.

### Ciclo de consulta y UART — 9 de septiembre, 17:47 ART

- Se revisaron las trazas existentes y el cliente de escritorio sin pedir otro
  arranque o aceleración. El ESP iniciaba ReadRAM inmediatamente después de
  transmitir la muestra por BLE; el ordenador deja una pausa entre muestras.
  La captura INPA de otro BMW Motronic 1.7 incluye un turno NOP adicional entre
  consultas, y EdiabasLib utiliza una guardia de 50 ms entre bloques. Fuentes y
  límites de extrapolación en `docs/PROTOCOL_NOTES.md`.
- Se instaló un ciclo con acuses DME de 2 ms, guardia entre bloques de 50 ms y
  mínimo de 750 ms entre comienzos de ReadRAM. La espera mantiene intercambios
  NOP; no agrega consultas RAM, no bloquea la publicación de la muestra ya
  recibida y no infla `consulta_ms`. Detener/Fallas/BLE cancelan las pausas en
  pasos de 25 ms. Un NOP fallido entra en la recuperación antes de otra consulta.
- UART tiene `timeout=0` y `timeout_char=0`: el plazo lo controla `_rx`, usando
  `readinto` y buffers reutilizables para reducir asignaciones y cambios de GIL
  por byte. Se conserva el timeout de lectura de 2 s y el cierre total de 300 ms.
- **34 pruebas de firmware/actualizador aprobadas**; se añadieron casos de lectura
  no bloqueante vacía, transmisión no aceptada, secuencias NOP/ReadRAM, 40 muestras
  espaciadas con duración ECU independiente, cancelación y recuperación de NOP.
  Registro: `.context/ble-sep09/paced-polling-tests.log`.
- Ambos archivos se respaldaron y verificaron por lectura en el ESP antes de
  reiniciar: `.context/firmware-backups/20260909T204704367550Z/`. Registro de
  instalación: `.context/ble-sep09/paced-polling-install.log`. La comprobación
  posterior confirmó BLE activo y la configuración nueva, sin iniciar consultas
  desde USB: `.context/ble-sep09/paced-polling-boot.log`. No se modificó la app ni
  su almacenamiento.
- **No hay una captura posterior con motor en marcha para esta versión.** La
  cadencia de hasta aproximadamente 1,3 Hz es un límite configurado, no una
  medición nueva. El cambio aborda diferencias concretas de temporización; no
  demuestra todavía que elimine el primer byte perdido durante aceleración.
- La copia pasiva del iPhone posterior a la instalación conserva 780 muestras.
  La última sesión se había detenido explícitamente a las 17:27:15 ART y no hay
  adquisición nueva que permita medir esta versión. Evidencia:
  `.context/ble-sep09/paced-polling-phone-summary.json`. No se reanudó la captura.

## Comprobaciones en un iPhone y el auto

Registrar dispositivo, iOS, versión del firmware, duración, cantidad de muestras y resultado de cada paso. No marcar un paso como verificado por haberlo probado únicamente en la demo.

- [ ] La app instalada pide permiso Bluetooth con la descripción prevista; denegar el permiso muestra un estado comprensible.
- [ ] Encuentra E36-OBD cuando anuncia solo el nombre y valida NUS antes de habilitar En vivo.
- [ ] Al conectarse desde el iPhone, otro central no ocupa el ESP32.
- [ ] Con contacto y motor apagado, la captura sigue recibiendo y muestra DME sin datos, sin alertas de sensores.
- [ ] Con motor andando, los cinco sensores coinciden con la terminal BLE. La admisión ausente en firmware anterior se muestra como no disponible.
- [ ] Con En vivo activo, girar el teléfono no reinicia el muestreo ni crea otra sesión.
- [ ] Fallas detiene temporalmente los sensores, completa la lectura y reanuda la misma captura. El texto y los códigos coinciden con el firmware.
- [ ] Al detener, comparar el contador `detenido (N muestras)` con las muestras guardadas para ese tramo de adquisición.
- [ ] Una pérdida de alimentación o radio marca un hueco; al recuperar el lector, continúa la misma sesión sin unir los gráficos a través del hueco.
- [ ] Detener durante una reconexión cancela el intento y finaliza la sesión.
- [ ] Una muestra de prueba de carga baja produce un episodio; los umbrales térmicos requieren permanencia y no generan avisos repetidos mientras continúan activos. Usar la demo para generar valores peligrosos, no calentar el motor para probar una alerta.
- [ ] Sonido y vibración funcionan con la app visible y las notificaciones funcionan con pantalla bloqueada, de acuerdo con los ajustes del iPhone.
- [ ] Una captura de **30 minutos o más** alterna pantalla visible, otra app y pantalla bloqueada, incluyendo CarPlay inalámbrico. Verificar continuidad, huecos, CSV y accesibilidad de SQLite bloqueado.
- [ ] Cerrar la app desde el selector y volver a abrirla conserva la captura anterior como interrumpida; no afirma que siguió grabando.
- [ ] Comprobar restauración disparada por iOS sin cierre forzado: conserva sesión y suscripción, no envía `v` sobre un flujo ya activo.
- [ ] El CSV de sensores tiene tantas filas como muestras guardadas; el CSV de eventos conserva avisos, mensajes y huecos.

## Límites observables

La hora guardada es la de **recepción en el iPhone**. El firmware no transmite reloj ni secuencia por muestra. `ECU ms` mide la consulta K-line; `RX Hz` mide los últimos ocho intervalos de llegada de líneas completas. Un hueco permite reconocer una interrupción, pero no cuantificar todos los paquetes perdidos. Los gráficos no sustituyen los datos originales de la exportación.

La restauración de CoreBluetooth depende de iOS. No continúa después de un cierre forzado por el usuario. Antes del primer desbloqueo tras reiniciar el teléfono, el almacenamiento no está disponible. El primer descubrimiento por nombre debe hacerse con la app abierta.

### Rediseño visual y auto del usuario — 9 de septiembre, 18:17 ART

- **7 pruebas unitarias de iOS y 4 recorridos de interfaz aprobados**, sin omisiones. Compilación completa con catálogo de imágenes y widget, Xcode 26.2, iPhone 16 Pro simulado con iOS 18.6. Resultado: `ios/TestResults/20260909T211234891378Z/Tests.xcresult`.
- El recorrido nuevo comprueba **Auto → En vivo → Auto → giro horizontal → Instrumentos → Detener**: sigue siendo una sola sesión. Se conservaron las comprobaciones de posición de las esferas, áreas táctiles, avisos simultáneos, reconexión simulada, error de DME sin falso éxito, exportación y recuperación con texto accesible.
- Tras compactar los accesos del resumen horizontal se repitió específicamente ese recorrido, aprobado: `.context/design-sep09/CompactOverview.xcresult`. Se revisaron visualmente ambas orientaciones; el auto completo y los dos accesos caben en horizontal. El panel de fallas horizontal muestra completo el primer registro. Capturas finales en [`Design/`](Design/) y decisiones en [`DESIGN.md`](DESIGN.md).
- La imagen incluida es el **E36 azul de cuatro puertas de la foto del usuario**, recortado localmente con Vision. Se verificó `E36Vehicle` en el catálogo compilado del iPhone; no se incluye el modelo de otro auto utilizado durante el desarrollo.
- **Compilado, firmado, instalado y abierto en el iPhone 17 Pro**, iOS 27 beta 24A5430a. `codesign --verify --deep --strict` aprobó; CoreDevice confirmó instalación, lanzamiento sin argumentos de prueba y proceso activo. Producto: `.context/design-iphone-build/Build/Products/Debug-iphoneos/E36OBD.app`.
- Se compararon las filas originales antes y después: **10 sesiones, 780 muestras y 17.959 eventos conservados íntegramente**; se añadió un evento al abrir. No se desinstaló la app ni se utilizaron argumentos que borraran datos en el teléfono. Respaldo y evidencia: `.context/design-sep09/phone-before/`, `phone-after/`, `data-preservation.json`, `iphone-install-final.json` e `iphone-launch-final.json`.
- Esta revisión valida presentación, navegación, instalación y conservación de datos. No agrega una nueva prueba física de continuidad BLE ni modifica el firmware.

### Modelo, pintura y vista giratoria — 9 de septiembre, 19:37 ART

- Se reemplazó el recorte fotográfico por **36 vistas renderizadas en Cycles** de la reconstrucción del E36 azul de cuatro puertas. El archivo editable de Blender conserva pintura metálica con barniz, vidrio, neumáticos, materiales separados y entorno de iluminación incluido. También se exportaron GLB y USDZ; archivos y atribuciones en [`Design/Vehicle/`](Design/Vehicle/). Es una reconstrucción visual de las fotos, sin medición del código de pintura ni dimensiones de las ruedas.
- La app presenta una **vista giratoria de imágenes**, con pasos de diez grados, arrastre horizontal y restablecimiento por doble toque. No se presenta como cámara libre ni renderizado 3D en tiempo real. UIKit prepara las imágenes fuera del hilo principal y limita la caché a ocho cuadros / 20 MiB. El ángulo se conserva durante actualizaciones de telemetría y cambios de orientación.
- Se comprobaron los 36 PNG RGBA de 1000 × 640, sus hashes distintos y su presencia íntegra en ambos productos compilados. El recorte común mantiene el auto completo en todos los ángulos. Evidencia: `.context/vehicle-3d/frame-validation.json`. Se revisaron visualmente la hoja de ángulos y las capturas reales del simulador en [vertical](Design/overview-portrait.jpg) y [horizontal](Design/overview-landscape.jpg).
- **Prueba de interfaz aprobada: 1 recorrido, 0 fallos**, después del último ajuste de arrastre. Comprueba giro y restablecimiento, En vivo, cambio Auto/Instrumentos, conservación del ángulo al girar el teléfono y exactamente una sesión al detener. Resultado: `.context/vehicle-3d/VehicleTurntable-Drag.xcresult`; registro: `.context/vehicle-3d/turntable-drag-test.log`. No se repitieron las pruebas de firmware para esta revisión visual.
- **Compilaciones de simulador e iPhone aprobadas**, incluida la atribución dentro del paquete; `codesign --verify --deep --strict` aprobó para el producto firmado en `.context/design-iphone-build/Build/Products/Debug-iphoneos/E36OBD.app`. **Esta versión todavía no se instaló en el iPhone**: CoreDevice informa que el dispositivo está `unavailable`, según `.context/vehicle-3d/devices-delivery.json`. La instalación de las 18:17 corresponde a la versión anterior. Esta revisión no modifica BLE, firmware ni almacenamiento.

### Samoablau, grillas y render nativo — 10 de septiembre

- La app usa geometría USDZ con RealityKit/Metal. Se corrigió la pintura a partir de tres regiones de baja reflexión del RAW del usuario, aplicando primero su orientación EXIF y convirtiendo Display P3 a sRGB. Las muestras de cielo reflejado se conservan por separado. [Comparación](Design/Vehicle/Samoablau-review.jpg), [regiones muestreadas](Design/Vehicle/paint-samples.jpg) y parámetros en `Design/Vehicle/paint-calibration.json`. Son parámetros de representación inferidos de fotos iluminadas, no una medición espectral de la pintura.
- Se retiró el ángulo adicional de 16,7° de las grillas conservando el contorno trazado en X/Z; se corrigió también la profundidad del emblema trasero contra la chapa. La geometría fuente no contiene vértices no finitos, caras de área cero ni triángulos exactamente coincidentes en la comprobación realizada. Esta última no detecta todas las superposiciones parciales posibles.
- Se regeneraron fuente, GLB, USDZ, iluminación difusa del runtime y los dos renders HD de 2400 × 1400. El runtime conserva **4.739.251 triángulos**; la diferencia máxima de posición frente al USDZ portable es **0,246 µm**. La compactación conserva exactamente las normales y UV por esquina. Los hashes de recursos del producto compilado coinciden con los archivos revisados.
- **Dos recorridos de interfaz aprobados**, sin fallos: cámaras de referencia y Auto → giro/zoom → En vivo → cambio de orientación → Instrumentos → Detener, conservando una sesión. Resultado: `.context/vehicle-3d/ducts-sep10/SamoablauReview.xcresult`. Tras el ajuste final de normales del vidrio y sombra se repitieron las tres capturas de referencia, también aprobadas: `SamoablauDelivery.xcresult`. [Capturas del renderer Metal](Design/Vehicle/MetalReview/).
- Compilaciones de simulador e iPhone aprobadas; firma estricta verificada. **Instalado en el iPhone 17 Pro del usuario**, iOS 27 beta 24A5430a, sin desinstalar ni pasar argumentos de prueba. El respaldo y la comparación posterior conservan íntegramente **10 sesiones, 780 muestras y 17.962 eventos**: cero filas originales modificadas o ausentes. Evidencia en `.context/vehicle-3d/ducts-sep10/samoablau-data-preservation.json` e `iphone-install-samoablau.json`.
- iOS bloqueó el primer intento de apertura porque el teléfono estaba bloqueado; `iphone-launch-samoablau.json` registra `Locked`. La revisión visual indicada arriba corresponde al simulador. La fidelidad fotográfica completa sigue pendiente, especialmente en las ópticas y algunos reflejos de la carrocería; no se da por alcanzada con esta corrección de color.
