# Arranca solo al energizar.
#
# BLE por defecto: en marcha el celular se va a la red del estereo para CarPlay
# y no puede estar en dos redes a la vez. BLE no compite con eso.
#
# El bucle va en un hilo aparte para que conectarse con mpremote no lo mate.
# El WiFi sigue disponible a mano:  import web; web.arrancar()
import time

try:
    import ble
    ble.arrancar()
except Exception as e:
    print("el panel murio:", e)
    time.sleep(2)
