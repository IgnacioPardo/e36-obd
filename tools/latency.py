"""Mide DÓNDE se van los milisegundos, en vez de suponerlo.

Todo el proyecto viene diciendo "~1 Hz, limitado por el round trip" como si
fuera un hecho. Nunca se midió. La cuenta del cable no cierra:

  9600 8N1 -> 1 byte = 10 bits = 1,042 ms de hilo.
  Una lectura del bloque central son ~44 bytes contando los ecos invertidos
  en las dos direcciones, o sea ~46 ms de hilo.

Eso da un techo de ~20 Hz. Estamos a 1. Faltan ~950 ms por muestra y no están
en el cable.

El sospechoso principal es el LATENCY TIMER del FTDI: el driver se sienta
sobre una lectura corta hasta que se le cumple el plazo antes de devolverla.
El valor de fábrica son 16 ms. Con ~44 lecturas de un byte por muestra, eso
es medio segundo de puro driver.

ESTE TEST NO NECESITA EL AUTO. El cable hace loopback de la línea K -- de
hecho el transporte lo detecta solo y se come su propio eco. Así que con el
cable enchufado SOLO al USB, un byte escrito vuelve por sí mismo, y lo que se
mide es nuestra pila completa (Python + pyserial + termios + driver + USB) sin
ninguna ECU en el medio.

Después, con el auto, la diferencia contra esta medición es lo que aporta la
ECU (su retardo entre bytes, que sí es un piso real e inevitable).

Uso:  PYTHONPATH=. ./.venv/bin/python tools/latency.py
"""

from __future__ import annotations

import fcntl
import statistics
import sys
import time

import serial

PORT = "/dev/cu.usbserial-A50285BI"
BAUD = 9600
N = 300

# Un byte a 9600 8N1: bit de arranque + 8 datos + bit de parada.
BIT_TIME_MS = 1000.0 / BAUD
BYTE_MS = 10 * BIT_TIME_MS

# Bytes que cruzan el hilo en una lectura del bloque central, contando el eco
# invertido de cada byte en ambas direcciones.
BLOCK_BYTES = 44


def ioc(inout: int, group: str, num: int, size: int) -> int:
    """Reconstruye la macro _IOC de BSD, que es de donde salen los ioctl de macOS."""
    return inout | ((size & 0x1FFF) << 16) | (ord(group) << 8) | num


IOC_IN = 0x80000000
# <IOKit/serial/ioss.h>: #define IOSSDATALAT _IOW('T', 0, unsigned long)
# El ancho del argumento cambió entre versiones, así que se prueban los dos.
IOSSDATALAT_32 = ioc(IOC_IN, "T", 0, 4)
IOSSDATALAT_64 = ioc(IOC_IN, "T", 0, 8)


def set_data_latency(ser: serial.Serial, micros: int) -> str:
    """Pide al driver que no retenga lecturas cortas. Devuelve qué pasó.

    En Linux pyserial tiene set_low_latency_mode(); en macOS no sirve, porque
    ahí el mecanismo es el ioctl IOSSDATALAT de IOKit.
    """
    fd = ser.fileno()
    last = "no se intentó"
    for name, req, width in (("IOSSDATALAT_64", IOSSDATALAT_64, 8),
                             ("IOSSDATALAT_32", IOSSDATALAT_32, 4)):
        try:
            fcntl.ioctl(fd, req, micros.to_bytes(width, sys.byteorder))
            return f"{name} aceptado ({micros} us)"
        except OSError as exc:
            last = f"{name}: {exc}"
    try:
        ser.set_low_latency_mode(True)
        return "set_low_latency_mode() aceptado (ruta de Linux)"
    except (NotImplementedError, OSError, ValueError) as exc:
        return f"sin efecto -- {last}; set_low_latency_mode: {exc}"


def measure(ser: serial.Serial, n: int, batch: int = 1) -> list[float]:
    """Escribe `batch` bytes y cronometra hasta que vuelven por el loopback.

    Sin ECU: lo que se mide es el ida y vuelta por nuestra propia pila. El
    tiempo se devuelve normalizado POR BYTE, para poder comparar batch=1 con
    batch=8 en la misma escala.
    """
    samples: list[float] = []
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    for i in range(n):
        probe = bytes([(i * 37 + k * 11 + 5) & 0xFF for k in range(batch)])
        t0 = time.perf_counter()
        ser.write(probe)
        ser.flush()
        got = ser.read(batch)
        dt = (time.perf_counter() - t0) * 1000.0
        if len(got) == batch:
            samples.append(dt / batch)
    return samples


def report(label: str, s: list[float]) -> None:
    if not s:
        print(f"  {label:22} sin eco -- el cable no hace loopback en este estado")
        return
    s_sorted = sorted(s)
    p = lambda q: s_sorted[min(len(s_sorted) - 1, int(len(s_sorted) * q))]
    # Un byte de ida y uno de vuelta es el mínimo físico posible.
    floor_ms = 2 * BYTE_MS
    print(f"  {label:22} n={len(s):3d}  "
          f"min {min(s):6.2f}  med {statistics.median(s):6.2f}  "
          f"p90 {p(.90):6.2f}  max {max(s):7.2f} ms")
    print(f"  {'':22} piso del hilo {floor_ms:.2f} ms  ->  "
          f"sobrecarga de nuestra pila: {statistics.median(s) - floor_ms:6.2f} ms/byte")
    implied = statistics.median(s) * BLOCK_BYTES / 2
    print(f"  {'':22} a este ritmo, un bloque de {BLOCK_BYTES} bytes "
          f"tarda {implied:.0f} ms  ->  {1000.0 / implied:.2f} Hz")


def main() -> int:
    print("Latencia de la pila serie, SIN auto (loopback del propio cable)\n")
    print(f"  puerto {PORT} @ {BAUD}")
    print(f"  un byte en el hilo: {BYTE_MS:.2f} ms")
    print(f"  techo teórico de un bloque de {BLOCK_BYTES} bytes: "
          f"{1000.0 / (BLOCK_BYTES * BYTE_MS):.1f} Hz\n")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.4)
    except OSError as exc:
        print(f"no se pudo abrir el puerto: {exc}")
        print("\nEnchufá el cable al USB. NO hace falta el auto para este test.")
        return 1

    with ser:
        time.sleep(0.2)
        print("ANTES de tocar el driver:")
        report("como está hoy", measure(ser, N))

        # El discriminador: si ocho bytes cuestan lo mismo que uno, lo que se
        # paga es cada LECTURA, no cada byte -- y eso es exactamente lo que
        # hace un latency timer.
        print("\nMismo test pero de a 8 bytes por vuelta:")
        report("lote de 8", measure(ser, N // 4, batch=8))

        print("\nPidiendo latencia mínima al driver:")
        print(f"  {set_data_latency(ser, 1000)}")
        time.sleep(0.2)
        print()
        report("con latencia mínima", measure(ser, N))
        report("lote de 8, mínima", measure(ser, N // 4, batch=8))

    print("\nLectura del resultado:")
    print("  · Si la mediana cae de ~16 ms a ~1-2 ms, el techo de 1 Hz era del")
    print("    driver y no del protocolo, y el muestreo sube en la misma medida.")
    print("  · Si el lote de 8 bytes tarda casi lo mismo que 1 byte, el costo es")
    print("    POR LECTURA y no por byte: es el latency timer, confirmado.")
    print("    Si tarda 8 veces más, el costo es por byte y el driver no tiene")
    print("    nada que ver.")
    print("  · OJO con la conclusión fácil: en KWP71 NO se puede mandar el bloque")
    print("    de una vez. Cada byte tiene que ser reconocido con su complemento")
    print("    antes de que llegue el siguiente; el handshake ES el protocolo.")
    print("    Por eso mismo este caso es el peor posible para un latency timer")
    print("    de 16 ms: se paga en cada uno de los ~44 bytes, no una vez.")
    print("    (DS2 sí es por bloques, así que el ABS podría muestrear rápido")
    print("    aunque esto no se arregle.)")
    print("  · Lo que mida acá es NUESTRA parte. Con el auto conectado, lo que")
    print("    exceda de esto es el retardo entre bytes de la ECU, que sí es un")
    print("    piso real e inevitable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
