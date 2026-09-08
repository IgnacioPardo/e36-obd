# Panel del E36 sobre BLE.
#
# El WiFi no sirve en marcha: el celular se va solo a la red del estereo para
# CarPlay inalambrico, y no puede estar en dos redes a la vez. Ademas CarPlay
# usa 5 GHz y la radio del ESP32-S3 es solo de 2,4, asi que unirse a la red
# del estereo tampoco es posible.
#
# BLE no compite con eso: podes tener CarPlay andando y leer el panel al mismo
# tiempo.
#
# Servicio: Nordic UART (NUS), que es el "puerto serie sobre BLE" de facto.
# Cualquier app de terminal BLE lo abre: nRF Connect, Bluefruit Connect,
# LightBlue, Serial Bluetooth Terminal.
#
# Comandos, un caracter y enter:
#     v   sensores en vivo   (cualquier tecla corta)
#     f   memoria de fallas
#     s   detener
#     ?   ayuda
#
# Uso:
#     import ble
#     ble.arrancar()

import struct
import time

import bluetooth

import kline

NOMBRE = "E36-OBD"

_NUS = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_RX = (bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
       bluetooth.FLAG_WRITE)
_TX = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"),
       bluetooth.FLAG_NOTIFY)

_IRQ_CONNECT = 1
_IRQ_DISCONNECT = 2
_IRQ_WRITE = 3

# BLE manda de a ~20 bytes por notificacion con el MTU por defecto, asi que
# todo lo que sale se parte. No es cosmetico: un texto largo de una sola vez
# se trunca sin aviso.
TROZO = 20


def _publicidad(nombre):
    """Payload de advertising: flags + nombre completo. El UUID de 128 bits
    no entra en los 31 bytes junto con el nombre, asi que va solo el nombre."""
    n = nombre.encode()
    return (bytes((2, 0x01, 0x06))            # flags: LE general discoverable
            + bytes((len(n) + 1, 0x09)) + n)  # 0x09 = nombre completo


class Panel:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq)
        ((self._tx, self._rx),) = self._ble.gatts_register_services(
            ((_NUS, (_TX, _RX)),))
        self._conn = None
        self._cmd = None
        self._vivo = False
        self._anunciar()

    def _anunciar(self):
        self._ble.gap_advertise(100_000, adv_data=_publicidad(NOMBRE))
        print("anunciando como", NOMBRE)

    def _irq(self, evento, datos):
        if evento == _IRQ_CONNECT:
            self._conn = datos[0]
            print("celular conectado")
        elif evento == _IRQ_DISCONNECT:
            self._conn = None
            self._vivo = False
            print("celular desconectado")
            self._anunciar()
        elif evento == _IRQ_WRITE:
            v = self._ble.gatts_read(self._rx)
            # El handler de IRQ no puede bloquear: solo anota el comando y el
            # bucle principal hace el trabajo, que dura cientos de ms.
            for c in v:
                if 32 <= c < 127:
                    self._cmd = chr(c).lower()

    def enviar(self, texto):
        if self._conn is None:
            return
        d = (texto + "\r\n").encode()
        for i in range(0, len(d), TROZO):
            try:
                self._ble.gatts_notify(self._conn, self._tx, d[i:i + TROZO])
            except OSError:
                return
            time.sleep_ms(12)          # sin esto se pierden notificaciones

    def ayuda(self):
        self.enviar("=== E36 M43B16 ===")
        self.enviar("v  sensores en vivo")
        self.enviar("f  memoria de fallas")
        self.enviar("s  detener")
        self.enviar("?  esta ayuda")

    def fallas(self):
        self.enviar("abriendo sesion...")
        try:
            kline.conectar(verbose=False)
            hubo = False
            for blk in kline.command(kline.READ_FAULTS):
                for i in range(0, len(blk) - 4, 5):
                    cod, cond, rpm, b3, frec = blk[i:i + 5]
                    hubo = True
                    self.enviar("cod %d  ocurr %d" % (cod, frec))
                    self.enviar("  cond 0x%02X" % cond)
                    if cod in kline.NOMBRES:
                        self.enviar("  " + kline.NOMBRES[cod])
            if not hubo:
                self.enviar("sin fallas almacenadas")
        except Exception as e:
            self.enviar("error: %s" % e)

    def vivo(self):
        self.enviar("abriendo sesion...")
        try:
            kline.conectar(verbose=False)
        except Exception as e:
            self.enviar("error: %s" % e)
            return
        self.enviar("en vivo. cualquier tecla corta.")
        self._vivo = True
        n = 0
        while self._vivo and self._conn is not None:
            if self._cmd is not None:      # cualquier tecla corta
                break
            t0 = time.ticks_ms()
            try:
                d = kline.leer_core()
            except Exception as e:
                self.enviar("se corto: %s" % e)
                break
            dt = time.ticks_diff(time.ticks_ms(), t0)
            n += 1
            # Una sola linea, legible en una terminal Y parseable por la web:
            # D rpm carga refrig bateria ms [aire]. La admision se agrega al
            # final para preservar los campos de clientes anteriores. Ya viene
            # en leer_core(): no agrega otra consulta ni cambia el round trip.
            self.enviar("D %d %.2f %.1f %.2f %d %.1f"
                        % (d["rpm"], d["carga"], d["refrig"],
                           d["bateria"], dt, d["aire"]))
        self._vivo = False
        self.enviar("detenido (%d muestras)" % n)

    def bucle(self):
        while True:
            c, self._cmd = self._cmd, None
            if c is None:
                time.sleep_ms(80)
                continue
            if c == "v":
                self.vivo()
            elif c == "f":
                self.fallas()
            elif c == "s":
                self._vivo = False
                self.enviar("detenido")
            else:
                self.ayuda()


def arrancar(en_hilo=True):
    """Arranca el panel. Con en_hilo=True el bucle va en un hilo aparte, para
    que conectarse al REPL con mpremote no lo mate: cada conexion manda un
    Ctrl-C y eso cortaba el bucle y con el la publicidad BLE."""
    p = Panel()
    print("=== panel BLE del E36 ===")
    print("  nombre  %s" % NOMBRE)
    print("  ? para la ayuda")
    if not en_hilo:
        p.bucle()
        return p
    import _thread
    _thread.stack_size(32 * 1024)

    def _correr():
        while True:
            try:
                p.bucle()
            except Exception as e:
                print("panel:", e)
                time.sleep(2)

    _thread.start_new_thread(_correr, ())
    print("  bucle en hilo aparte, REPL libre")
    return p
