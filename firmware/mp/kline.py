# KWP71 sobre MicroPython / ESP32-S3 + L9637D
# BMW E36 M43B16, Motronic 1.7.2
#
# Puerto directo de e36obd/kline.py y e36obd/kwp71.py, que ya funcionan contra
# este auto desde macOS. Lo que cambia:
#
#   · El init de 5 baudios deja de ser un truco. En macOS habia que hacer
#     bit-bang con TIOCSBRK porque el driver FTDI no deja tocar la linea;
#     aca se escribe el Pin directo.
#   · Desaparecen los 231 ms por lectura del driver FTDI de macOS. El techo
#     real lo pone el handshake de KWP71 y el retardo entre bytes del DME.
#
# El L9637D NO invierte: en la figura 5 de su hoja de datos, TX baja y K baja
# detras. Asi que la logica del Pin es la del UART, sin inversion.
#
# La linea K es UN hilo: todo lo que transmitimos vuelve por RX. Cada escritura
# se sigue de una lectura que descarta ese eco. Es distinto del reconocimiento
# invertido, que es lo que manda la ECU.
#
# Uso desde el REPL:
#     import kline
#     kline.leer_fallas()

from machine import Pin, UART
import time

TX_PIN = 17          # -> L9637D pin 4 (TX)
RX_PIN = 18          # <- L9637D pin 1 (RX)

BAUD = 9600
DME = 0x10           # la caja es 0x6C a 4800
KEYWORDS = 2           # el DME manda 55 00 81: el 55 es sincronismo, quedan DOS

# BMW espera 2600 ms de bus en reposo antes de cada init. Con 260 ms el barrido
# de direcciones daba falsos negativos: es un error que ya cometimos.
BUS_IDLE_MS = 2600
BIT_MS = 200         # 5 baudios
# El DME aguanta 5 ms entre bytes; la CAJA necesita 15. Con 5 la sesion de la
# caja se abre, manda su identificacion, y despues ningun comando contesta --
# se ve como "servicio no soportado" y no lo es. En macOS nunca aparecio porque
# los 231 ms por lectura del driver FTDI hacian todo lentisimo por accidente.
# El DME aguanta 5 ms entre bytes; la CAJA necesita 15. Con 5 la sesion de la
# caja se abre, manda su identificacion, y despues NINGUN comando contesta --
# se ve como "servicio no soportado" y no lo es. En macOS nunca aparecio porque
# los 231 ms por lectura del driver FTDI hacian todo lentisimo por accidente.
INTER_BYTE_MS = 5
INTER_BYTE_EGS_MS = 15
# Medido 2026-09-07: con 5 ms la sesion de la caja se abre y ningun comando
# contesta. Con 15 funciona TODO (RAM, fallas, ROM) pero SOLO con el motor
# apagado. Andando muere en el bloque 5 de 6 de identificacion, y no lo
# arregla ningun valor de espera: probados 15/30/50/80/120 ms y 10 sesiones
# seguidas, cero exitos. A 4800 cada bit dura el doble que a 9600, o sea el
# doble de exposicion al ruido de encendido por byte. El DME a 9600 aguanta.
INTER_BYTE_EGS_MS = 15
BYTE_TIMEOUT_MS = 1200

READ_RAM = 0x01
DISCONNECT = 0x06
READ_FAULTS = 0x07
READ_ADC = 0x08
EMPTY = 0x09
NOT_SUPPORTED = 0x0B
BLOCK_END = 0x03

_uart = None
_seq = 0


class KLineError(Exception):
    pass


def _rx(timeout_ms=BYTE_TIMEOUT_MS):
    """Un byte, o KLineError."""
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if _uart.any():
            return _uart.read(1)[0]
        time.sleep_ms(1)
    raise KLineError("sin respuesta de la ECU")


def _tx(b):
    """Escribe un byte y se come su propio eco."""
    while _uart.any():
        _uart.read(1)
    _uart.write(bytes([b]))
    echo = _rx(300)
    if echo != b:
        raise KLineError("eco malo: mande %02X y volvio %02X" % (b, echo))


EGS = 0x6C           # caja automatica A4S 310R
EGS_BAUD = 4800


def _ritmo(address):
    """Cada modulo tiene su propio aire entre bytes."""
    global INTER_BYTE_MS
    INTER_BYTE_MS = INTER_BYTE_EGS_MS if address == EGS else 5


def _ritmo(address):
    """Cada modulo tiene su propio aire entre bytes."""
    global INTER_BYTE_MS
    INTER_BYTE_MS = INTER_BYTE_EGS_MS if address == EGS else 5


def init(address=DME, keywords=KEYWORDS, verbose=True, baud=BAUD):
    """Init de 5 baudios. Devuelve la lista de keywords.

    El init en si NO depende del baudio -- son 200 ms por bit siempre. Lo que
    cambia es el UART que se abre despues: el DME a 9600, la caja a 4800.
    """
    global _uart, _seq
    if _uart:
        _uart.deinit()
        _uart = None

    if verbose:
        print("bus en reposo %d ms" % BUS_IDLE_MS)
    tx = Pin(TX_PIN, Pin.OUT, value=1)      # recesivo = alto
    time.sleep_ms(BUS_IDLE_MS)

    if verbose:
        print("init de 5 baudios, direccion 0x%02X" % address)
    tx.value(0)                             # bit de arranque
    time.sleep_ms(BIT_MS)
    for i in range(8):                      # ocho datos, LSB primero
        tx.value((address >> i) & 1)
        time.sleep_ms(BIT_MS)
    # El bit de parada NO se duerme: es la linea descansando alta. Si esperamos
    # los 200 ms completos antes de escuchar, tiramos el 0x55 de la ECU, que
    # puede llegar a los ~60 ms. Este bug ya nos costo semanas.
    tx.value(1)

    _uart = UART(1, baudrate=baud, bits=8, parity=None, stop=1,
                 tx=TX_PIN, rx=RX_PIN, timeout=200)
    while _uart.any():
        _uart.read(1)

    b = _rx(500)
    if b != 0x55:
        if b == 0x66 and baud == 9600:
            # Un 0x55 a 4800 muestreado a 9600 se lee 0x66. Asi encontramos la caja.
            raise KLineError("llego 0x66: la ECU esta a 4800, no a 9600")
        raise KLineError("se esperaba 0x55 y llego 0x%02X" % b)
    if verbose:
        print("  0x55 sincronismo OK")

    kws = [_rx(500) for _ in range(keywords)]
    if verbose:
        print("  keywords:", " ".join("%02X" % k for k in kws))

    # La ultima keyword se reconoce invertida y ahi arranca la sesion.
    time.sleep_ms(INTER_BYTE_MS * 5)
    _uart.write(bytes([(~kws[-1]) & 0xFF]))
    try:
        _rx(300)
    except KLineError:
        pass
    _seq = 0
    return kws


def send_block(title, payload=b""):
    global _seq
    _seq = (_seq + 1) & 0xFF
    length = 1 + 1 + len(payload) + 1
    buf = bytes([length, _seq, title]) + bytes(payload) + bytes([BLOCK_END])
    for i, b in enumerate(buf):
        _tx(b)
        if i < length:                      # todos menos el ultimo van con acuse
            ack = _rx()
            if ack != ((~b) & 0xFF):
                raise KLineError(
                    "acuse malo en byte %d: esperaba %02X, llego %02X"
                    % (i, (~b) & 0xFF, ack))
        time.sleep_ms(INTER_BYTE_MS)


def recv_block():
    length = _rx()
    if length < 3:
        raise KLineError("bloque corto: len=%d" % length)
    time.sleep_ms(INTER_BYTE_MS)
    _tx((~length) & 0xFF)

    raw = [length]
    for i in range(1, length + 1):
        raw.append(_rx())
        if i < length:
            time.sleep_ms(INTER_BYTE_MS)
            _tx((~raw[i]) & 0xFF)
    global _seq
    _seq = raw[1]
    return raw[2], bytes(raw[3:length])     # titulo, payload


def command(title, payload=b""):
    """Manda un bloque y junta la respuesta hasta el Empty."""
    send_block(title, payload)
    out = []
    while True:
        t, p = recv_block()
        if t == NOT_SUPPORTED:
            raise KLineError("la ECU no soporta el titulo 0x%02X" % title)
        if t == EMPTY:
            return out
        out.append(p)
        time.sleep_ms(INTER_BYTE_MS)
        send_block(EMPTY)


def drenar_id(verbose=False):
    """La ECU manda sus cadenas de identificacion sin que se las pidan.
    Hay que consumirlas antes de mandar cualquier comando, o el largo del
    bloque de ID se confunde con el acuse del nuestro."""
    ids = []
    for _ in range(10):
        try:
            t, p = recv_block()
        except KLineError:
            break
        if t == EMPTY:
            break
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in p)
        ids.append(txt)
        if verbose:
            print("id:", txt)
        time.sleep_ms(INTER_BYTE_MS)
        send_block(EMPTY)
    return ids


def conectar(address=DME, verbose=True, baud=BAUD):
    """Init + drenaje de identificacion. Deja la sesion lista para comandos."""
    _ritmo(address)
    _ritmo(address)
    kws = init(address, verbose=verbose, baud=baud)
    ids = drenar_id(verbose=verbose)
    return kws, ids


def read_ram(address, count):
    """Lectura de RAM: [cantidad][alto][bajo]. Devuelve los bytes crudos."""
    payload = bytes([count, (address >> 8) & 0xFF, address & 0xFF])
    out = b""
    for blk in command(READ_RAM, payload):
        out += blk
    return out


# Mapa validado del M1.7.2 (e36obd/sensors.py). OJO: con el motor apagado
# todas estas posiciones leen 0x00 -- parece enlace muerto y no lo es.
CORE_START = 0x0036
CORE_LEN = 0x0B


def leer_core(velocidad=False):
    """Los sensores del bloque contiguo, en una sola lectura.

    Devuelve tambien los seis bytes SIN IDENTIFICAR del bloque (0x39 0x3A 0x3B
    0x3D 0x3E 0x3F). Viajan gratis en cada lectura y ahi puede estar escondida
    la velocidad de camino, ademas del byte alto del regimen.

    OJO con el techo del regimen: 0x003C es UN byte con escala x10, o sea que
    satura en 2550 rpm. Si 0x003B es el byte alto, 'rpm16' es el valor real y
    'rpm' miente arriba de 2550. Se confirma pasando de 2550 una vez y mirando
    si 0x003B se mueve.
    """
    d = read_ram(CORE_START, CORE_LEN)
    if len(d) < CORE_LEN:
        raise KLineError("bloque corto: %d de %d bytes" % (len(d), CORE_LEN))
    g = lambda a: d[a - CORE_START]
    out = {
        "bateria":   round(0.0681 * g(0x0036), 2),
        "aire":      round(-33.5 + 0.65 * g(0x0037), 1),
        "refrig":    round(-32.5 + 0.65 * g(0x0038), 1),
        "rpm":       10 * g(0x003C),
        "carga":     round(0.05 * g(0x0040), 2),
        # candidato a regimen de 16 bits: 0x003B como byte alto
        "rpm16":     10 * ((g(0x003B) << 8) | g(0x003C)),
        # los sin identificar, para poder cazarlos manejando
        "b39": g(0x0039), "b3A": g(0x003A), "b3B": g(0x003B),
        "b3D": g(0x003D), "b3E": g(0x003E), "b3F": g(0x003F),
        "crudo": " ".join("%02X" % b for b in d),
    }
    if velocidad:
        # 0x008B, documentada y NUNCA validada. Fuera del bloque, cuesta un
        # round trip extra: la tasa cae a la mitad.
        try:
            out["kmh"] = round(1.102 * read_ram(0x008B, 1)[0], 1)
        except Exception:
            out["kmh"] = None
    return out


# Cada falla son 5 bytes: [codigo][condicion][rpm][byte3][frecuencia].
# El codigo es solido; las escalas del freeze frame no estan cerradas.
NOMBRES = {
    100: "Amplifier/output stage 1 in DME",
    36: "EVAP / valvula del canister",
    73: "Vehicle speed signal (VSS), or TPS",
}


def leer_fallas():
    """El 'hola mundo': init, identificacion y memoria de fallas."""
    print("=== KWP71 / E36 M43B16 ===")
    print("TX=GPIO%d RX=GPIO%d %d baudios  contacto en posicion 2\n"
          % (TX_PIN, RX_PIN, BAUD))
    try:
        init()
    except KLineError as e:
        print("\nINIT FALLIDO:", e)
        print("Revisar, en orden:")
        print("  1. llave en posicion 2, no en 1")
        print("  2. OBD2 pin 7 Y pin 15 juntos al pin 6 del L9637D")
        print("  3. pin 3 del L9637D en 3,3 V")
        print("  4. pin 6 en reposo cerca de 12 V")
        return
    print("\nSESION ABIERTA\n")

    drenar_id(verbose=True)

    print("\n--- memoria de fallas ---")
    try:
        for blk in command(READ_FAULTS):
            if not blk:
                continue
            for i in range(0, len(blk) - 4, 5):
                cod, cond, rpm, b3, frec = blk[i:i + 5]
                print("codigo %3d  cond 0x%02X  ocurrencias %2d  crudo %02X %02X"
                      % (cod, cond, frec, rpm, b3))
                if cod in NOMBRES:
                    print("    -> %s" % NOMBRES[cod])
    except KLineError as e:
        print("error leyendo fallas:", e)

    print("\nSe esperan los codigos 100 y 36, los dos con contador en 50.")
    try:
        send_block(DISCONNECT)
    except KLineError:
        pass


# ---------------------------------------------------------------- caja
# Relaciones del A4S 310R (GM 4L30-E). Dos juegos segun version.
RELACIONES = (2.86, 1.62, 1.00, 0.72)

# La caja NO tiene servicio de canales analogicos: leer 0x08 devuelve el
# contador de secuencia, que sube 4 por lectura. Solo sirve ReadRAM.
# Del freeze frame sabemos la escala: regimen y salida van x32.
ESCALA_RPM = 32


def _reconectar(address, baud, intentos=4):
    for _ in range(intentos):
        try:
            conectar(address=address, baud=baud, verbose=False)
            return True
        except KLineError:
            time.sleep(2)
    return False


def volcar(base=0x00, largo=0x40, trozo=8, address=None, baud=None):
    """Vuelca RAM. Reconecta y reintenta cada trozo: con el motor al ralenti el
    ruido de encendido tira la sesion, y un volcado de varios round trips se
    corta a la mitad. Es el mismo problema que en macOS.

    Los bytes que no se pudieron leer quedan afuera del dict.
    """
    address = EGS if address is None else address
    baud = EGS_BAUD if baud is None else baud
    out = {}
    for a in range(base, base + largo, trozo):
        n = min(trozo, base + largo - a)
        for intento in range(3):
            try:
                for i, b in enumerate(read_ram(a, n)):
                    out[a + i] = b
                break
            except KLineError:
                if not _reconectar(address, baud):
                    return out
    return out


def buscar(base=0x00, largo=0x40, vueltas=6, espera_ms=1200):
    """Busqueda guiada: vuelca la RAM varias veces y reporta que bytes se
    mueven. Con el motor al ralenti y moviendo la palanca, el byte de la
    marcha ordenada aparece solo. Los de regimen y salida se mueven con el
    acelerador.

    Devuelve dict direccion -> (minimo, maximo, cantidad_de_valores).
    """
    hist = {}
    for v in range(vueltas):
        d = volcar(base, largo)
        for a, b in d.items():
            hist.setdefault(a, []).append(b)
        print("  vuelta %d de %d" % (v + 1, vueltas))
        time.sleep_ms(espera_ms)
    movidos = {}
    for a, vals in hist.items():
        if min(vals) != max(vals):
            movidos[a] = (min(vals), max(vals), len(set(vals)))
    return movidos


def marchas(dir_motor, dir_salida, dir_ordenada=None):
    """Marcha REAL (por relacion) y ORDENADA (por el byte que le digas).

    La real sale de regimen/salida contra las relaciones del A4S 310R. Si las
    dos difieren, ESA es la falla que registra el codigo 100.
    """
    motor = read_ram(dir_motor, 1)[0] * ESCALA_RPM
    salida = read_ram(dir_salida, 1)[0] * ESCALA_RPM
    rel = (motor / salida) if salida else None
    real, dif = None, None
    if rel:
        for i, r in enumerate(RELACIONES):
            e = abs(rel - r)
            if dif is None or e < dif:
                real, dif = i + 1, e
        if dif > 0.25 * rel:          # no coincide con ninguna: patinando
            real = None
    orden = read_ram(dir_ordenada, 1)[0] if dir_ordenada is not None else None
    return {"motor": motor, "salida": salida,
            "relacion": round(rel, 2) if rel else None,
            "real": real, "ordenada": orden,
            "error": round(dif, 2) if dif is not None else None}
