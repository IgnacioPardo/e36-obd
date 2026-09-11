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
MAX_RECUPERACIONES = 5       # igual que LiveReader del cliente de escritorio
PERIODO_MUESTRA_MS = 750     # minimo entre comienzos de consultas RAM
REPOSO_VIVO_MS = 100         # mantener turnos NOP durante la espera


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
        self._sesion = False
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

    def _abrir_sesion(self):
        self._cerrar_sesion()
        kline.conectar(verbose=False)
        self._sesion = True

    def _cerrar_sesion(self):
        # Solo desde el hilo del panel, nunca desde el callback BLE. Dejar de
        # leer no cierra KWP71: otro init sobre esa sesion puede ser ignorado.
        if not self._sesion:
            return
        self._sesion = False
        try:
            if hasattr(kline, "desconectar"):
                kline.desconectar()
            else:  # permite actualizar solo BLE sobre el transporte anterior
                kline.send_block(kline.DISCONNECT)
        except Exception as e:
            # No sustituir una lectura correcta por un fallo al despedirnos.
            # El proximo comando abrira una sesion desde cero.
            print("DME: cierre sin acuse:", e)

    def fallas(self):
        self.enviar("abriendo sesion...")
        try:
            self._abrir_sesion()
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
        finally:
            self._cerrar_sesion()

    def vivo(self):
        self.enviar("abriendo sesion...")
        self._vivo = True
        n = 0
        recuperaciones = 0
        muestra_anterior = None
        try:
            while self._seguir_vivo():
                try:
                    if not self._sesion:
                        self._abrir_sesion()
                        if not self._seguir_vivo():
                            break
                        self.enviar("en vivo. cualquier tecla corta.")
                        muestra_anterior = None
                    if muestra_anterior is not None:
                        if not self._esperar_muestra(muestra_anterior):
                            break
                    t0 = time.ticks_ms()
                    d = kline.leer_core()
                except Exception as e:
                    # La computadora reconstruye la sesion K-line aqui. BLE
                    # es solo el transporte del resultado: no hay que cortarlo.
                    if not self._seguir_vivo():
                        break
                    recuperaciones += 1
                    if recuperaciones > MAX_RECUPERACIONES:
                        self.enviar("se corto: %s" % e)
                        break
                    self.enviar("recuperando DME (%d/%d): %s"
                                % (recuperaciones, MAX_RECUPERACIONES, e))
                    self._cerrar_sesion()
                    # Espera del LiveReader, cancelable por Stop/Fallas/BLE.
                    for _ in range(6):
                        if not self._seguir_vivo():
                            break
                        time.sleep_ms(50)
                    continue
                dt = time.ticks_diff(time.ticks_ms(), t0)
                muestra_anterior = t0
                recuperaciones = 0
                n += 1
                # Una sola linea, legible en una terminal Y parseable por la web:
                # D rpm carga refrig bateria ms [aire]. La admision se agrega al
                # final para preservar los campos de clientes anteriores. Ya viene
                # en leer_core(): no agrega otra consulta ni cambia el round trip.
                self.enviar("D %d %.2f %.1f %.2f %d %.1f"
                            % (d["rpm"], d["carga"], d["refrig"],
                               d["bateria"], dt, d["aire"]))
        finally:
            self._vivo = False
            self._cerrar_sesion()
        self.enviar("detenido (%d muestras)" % n)

    def _seguir_vivo(self):
        return self._vivo and self._conn is not None and self._cmd is None

    def _esperar_muestra(self, comienzo):
        # El bloque EMPTY que termina ReadRAM no sustituye el turno NOP
        # entre consultas. Mantener el dialogo mientras se limita la tasa;
        # dormir todo el intervalo sin intercambiar bloques perderia KWP71.
        while self._seguir_vivo():
            if hasattr(kline, "keepalive"):
                kline.keepalive()
            # Compatibilidad con instalaciones antiguas de solo ble.py:
            # conservan el ritmo, aunque necesitan actualizar kline.py para NOP.
            falta = PERIODO_MUESTRA_MS - time.ticks_diff(time.ticks_ms(), comienzo)
            if falta <= 0:
                return self._seguir_vivo()
            espera = min(REPOSO_VIVO_MS, falta)
            while espera > 0 and self._seguir_vivo():
                paso = min(25, espera)
                time.sleep_ms(paso)
                espera -= paso
        return False

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
                self._cerrar_sesion()
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
