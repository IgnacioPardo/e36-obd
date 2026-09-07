"""Barrido de 5 baudios sobre un rango de direcciones, con el código corregido
(2600 ms de bus en reposo, sin dormir el bit de stop antes de vaciar).

Resiste que el FTDI desaparezca un instante: si el puerto se cae, lo reabre y
reintenta esa dirección en vez de abortar todo el barrido.
"""
import sys, time, serial

PORT = "/dev/cu.usbserial-A50285BI"
LO   = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x00
HI   = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0xFF
BIT, IDLE, LISTEN = 0.200, 2.6, 0.9

def open_port():
    for _ in range(20):
        try:
            return serial.Serial(PORT, 9600, timeout=0.05)
        except serial.SerialException:
            time.sleep(1.5)
    raise SystemExit("no se pudo reabrir el puerto")

ser = open_port()

def slow_init(addr):
    global ser
    ser.reset_input_buffer()
    time.sleep(IDLE)
    ser.reset_input_buffer()
    bits = [0] + [(addr >> i) & 1 for i in range(8)]     # start + 8 datos, LSB primero
    t0 = time.monotonic()
    for i, b in enumerate(bits):
        ser.break_condition = (b == 0)
        d = t0 + (i + 1) * BIT - time.monotonic()
        if d > 0: time.sleep(d)
    ser.break_condition = False
    ser.reset_input_buffer()          # el bit de stop es reposo: se escucha ya
    got = b""
    end = time.monotonic() + LISTEN
    while time.monotonic() < end:
        c = ser.read(1)
        if c: got += c
    return got

hits, lost = [], 0
n = HI - LO + 1
print(f"barriendo 0x{LO:02X}-0x{HI:02X} · ~{n*(IDLE+2.0+LISTEN)/60:.0f} min", flush=True)
a = LO
while a <= HI:
    try:
        r = slow_init(a)
    except Exception as e:
        lost += 1
        print(f"  0x{a:02X}: {type(e).__name__}, reabriendo…", flush=True)
        try: ser.close()
        except Exception: pass
        ser = open_port()
        continue
    if r:
        print(f"  0x{a:02X}: {' '.join(f'{b:02X}' for b in r)}   <-- RESPUESTA", flush=True)
        hits.append((a, r))
    elif a % 16 == 0:
        print(f"  ...0x{a:02X}", flush=True)
    a += 1
try: ser.close()
except Exception: pass
print(f"\n=== {len(hits)} dirección(es) respondieron · {lost} caída(s) de puerto ===", flush=True)
for a, r in hits:
    print(f"  0x{a:02X}  {' '.join(f'{b:02X}' for b in r)}", flush=True)
