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
