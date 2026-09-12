# Widget E36 para iPhone y CarPlay

La extensión WidgetKit incluye tres diseños:

| Widget | Tamaños | Contenido |
|---|---|---|
| **Instrumento E36** | Pequeño | Esfera, aguja y lectura del sensor elegido. |
| **Garage E36** | Pequeño y mediano | Render del 316i en **295 · Samoablau Metallic**, junto a la última lectura. |
| **OBC E36** | Pequeño y mediano | Los cinco canales, con el sensor elegido como lectura principal. |

Todos conservan unidades, antigüedad y fondo removible. Los tres ofrecen `systemSmall` para StandBy y CarPlay. El render de Garage es una imagen con transparencia exportada del mismo pase Metal, materiales y geometría de la app; la extensión no carga el modelo 3D ni ejecuta el renderer. Tocar Garage en el iPhone abre Auto; Instrumento y OBC abren Instrumentos. [Soporte de StandBy y CarPlay](https://developer.apple.com/documentation/widgetkit/adding-standby-and-carplay-support-to-your-widget).

## Agregarlo

1. Instalar la app completa y abrirla una vez. Iniciar una captura para compartir lecturas del ESP32.
2. En iPhone: mantener pulsada la pantalla de inicio → Editar → Agregar widget → E36 OBD → elegir un diseño.
3. En **CarPlay con iOS 26 o posterior**: Ajustes del iPhone → General → CarPlay → tu auto → Widgets → Agregar widgets → elegir un diseño.
4. Editar la configuración del widget para elegir **Instrumento** y **Origen**. El origen predeterminado es ESP32. Para probar sin hardware, elegir **Simulación** y ejecutar la app con el esquema E36OBD Demo. Sus datos se guardan por separado; las superficies no llevan una insignia DEMO.

La cantidad de columnas y pilas depende de la pantalla del vehículo. El widget funciona sin abrir una aplicación CarPlay propia. La flecha de actualización de Instrumento funciona en iPhone y en pantallas CarPlay táctiles; los vehículos sin pantalla táctil muestran información sin controles interactivos. Tocar el fondo no abre una app CarPlay de E36.

Fuentes: [agregar widgets en CarPlay](https://support.apple.com/es-es/guide/iphone/iphb4d6a0bbb/ios), [soporte de StandBy y CarPlay](https://developer.apple.com/documentation/widgetkit/adding-standby-and-carplay-support-to-your-widget).

## Qué se actualiza

El widget muestra una **observación fechada**, no una transmisión continua. La adquisición BLE y las alertas siguen perteneciendo a la app. El widget no consulta al ESP32, no envía comandos al DME y no inicia ni detiene una sesión.

La app comparte muestras nuevas como máximo una vez por segundo, y los cambios de estado al producirse. Solicita recargar WidgetKit cada 15 segundos con la app visible, cada 5 minutos en segundo plano y ante cambios de captura o alertas. **Esas son solicitudes, no frecuencias garantizadas.** WidgetKit administra el presupuesto y puede retrasarlas. Cada lectura muestra su antigüedad mediante una fecha dinámica del sistema. No se muestra un indicador REC que afirme que una captura antigua sigue activa.

La flecha pide al sistema volver a leer la última muestra que la app ya compartió; no fuerza una consulta BLE. Si la captura no está funcionando, la antigüedad sigue aumentando. Sin datos, con RAM vacía o con admisión ausente, el widget muestra un guion. Por encima de 2550 rpm conserva la indicación de saturación. Los cambios de color de una muestra no sustituyen las alertas de la app.

Fuente: [presupuesto y actualización de widgets](https://developer.apple.com/documentation/widgetkit/keeping-a-widget-up-to-date).

## Firma y almacenamiento

La app y la extensión usan el mismo App Group: `group.com.ignaciopardo.e36obd`. En un iPhone físico, seleccionar el mismo equipo de desarrollo en ambos targets y habilitar ese grupo en sus perfiles de firma. No se solicita un entitlement de aplicación CarPlay: este target utiliza WidgetKit.

La primera firma requiere **registrar** el grupo: en el target E36OBD, abrir Signing & Capabilities → App Groups → `+` y agregar `group.com.ignaciopardo.e36obd`. Seleccionarlo también en E36OBDWidgets. Declararlo solamente en los archivos `.entitlements` puede producir perfiles con una lista de grupos vacía; `-allowProvisioningUpdates` por sí solo no resolvió ese caso. La inscripción y ambos perfiles se verificaron con el Personal Team del usuario.

Al instalar por primera vez, iOS puede pedir confiar en el certificado en Ajustes → General → VPN y gestión de dispositivos. Los perfiles de desarrollo tienen vencimiento; verificar su fecha y volver a compilar e instalar para renovarlos. No es necesario borrar la app ni sus sesiones para actualizarla.

Si se cambia el identificador del grupo, actualizar las dos declaraciones `.entitlements` y `WidgetSnapshotStore.appGroup` en el paquete E36Core. La app muestra problemas al compartir datos en Ajustes → Widget y CarPlay; un fallo del widget no cambia el indicador REC ni detiene el almacenamiento de sesiones.

El intercambio usa dos archivos JSON separados, uno para ESP32 y otro para demo. La app escribe de forma atómica desde un actor, fuera del callback Bluetooth. La extensión es lectora y valida la versión y el origen. Los archivos permiten acceso después del primer desbloqueo del iPhone; antes de ese desbloqueo puede mostrarse el estado sin lecturas.

`test_simulator.py` usa firma ad hoc local para que Xcode incluya los entitlements simulados. Compilar con `CODE_SIGNING_ALLOWED=NO` no valida el App Group. La firma ad hoc del simulador no sirve para instalar en un iPhone físico.

## Verificación

- El núcleo prueba separación de fuentes, lectura atómica, archivos corruptos, versiones desconocidas, canales ausentes, RAM vacía, antigüedad y límites de publicación.
- XCTest verifica que la extensión esté embebida y que el publicador escriba en el contenedor real del App Group del simulador.
- Se agregó y configuró Instrumento E36 desde la galería real del simulador iOS 18.6. Se revisaron la ausencia de datos ESP32, los cinco sensores del selector, refrigerante alto y RPM saturadas. Resultados y capturas en [VALIDATION.md](VALIDATION.md).
- Antes de dar por validado CarPlay físico: instalar la app firmada, agregar el widget desde los ajustes del vehículo, comprobar la lectura y su antigüedad, probar la flecha en una pantalla táctil y mantener una captura BLE con el iPhone bloqueado.
