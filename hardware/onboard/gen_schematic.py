"""Esquema SVG + netlist KiCad, generados desde las MISMAS redes que la placa (gen_board.N).

  python3 hardware/onboard/gen_schematic.py

El dibujo se verifica contra N: cada (ref, pin) de cada red tiene que aparecer en el dibujo
exactamente en esa red (por cable o por etiqueta). Si no coincide, no se emite el SVG.
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "gen_board.py")).read()
# leer P y N sin importar pcbnew
ns = {}
exec(re.search(r"^P = \[.*?^\]", src, re.S | re.M).group(0), ns)
exec(re.search(r"^N = \{.*?^\}", src, re.S | re.M).group(0), ns)
P, N = ns["P"], ns["N"]
VAL = {p[0]: p[6] for p in P}

COL = {"VBAT_RAW": "#c0392b", "VBAT_F": "#c0392b", "VIN": "#c0392b", "+3V3": "#c0392b", "VBUS": "#c0392b",
       "SW": "#8e44ad", "BST": "#8e44ad", "K_LINE": "#c2701a", "GND": "#555555"}
def col(net): return COL.get(net, "#2166a8")

svg, pins, used = [], {}, {}      # used[net] = set de "ref.pin" dibujados

def T(x, y, s, size=11, anchor="start", color="#222", weight=400):
    svg.append('<text x="%g" y="%g" font-size="%g" text-anchor="%s" fill="%s" font-weight="%d">%s</text>'
               % (x, y, size, anchor, color, weight, s.replace("&", "&amp;").replace("<", "&lt;")))
def L(x0, y0, x1, y1, color="#222", w=1.6):
    svg.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="%s" stroke-width="%g"/>' % (x0, y0, x1, y1, color, w))

def box(ref, x, y, w, h, sub, plist):
    """Caja con pines: plist = [(pin, lado L/R, offset, etiqueta)]. Guarda el extremo del stub."""
    svg.append('<rect x="%g" y="%g" width="%g" height="%g" rx="3" fill="#fff" stroke="#222" stroke-width="1.8"/>' % (x, y, w, h))
    T(x + w / 2, y + 16, ref, 13, "middle", weight=600); T(x + w / 2, y + 30, sub, 10, "middle", "#666")
    for pid, side, off, lab in plist:
        if side == "L":
            L(x - 22, y + off, x, y + off); pins[(ref, pid)] = (x - 22, y + off); T(x + 5, y + off + 4, lab, 10)
        else:
            L(x + w, y + off, x + w + 22, y + off); pins[(ref, pid)] = (x + w + 22, y + off); T(x + w - 5, y + off + 4, lab, 10, "end")

def part2(ref, kind, x, y, orient):
    """Dos terminales centrado en (x,y). H: pin1 izq, pin2 der. V: pin1 arriba, pin2 abajo."""
    d = 30
    if orient == "H":    p1, p2 = (x - d, y), (x + d, y)
    elif orient == "Vr": p1, p2 = (x, y + d), (x, y - d)      # pin 2 arriba
    else:                p1, p2 = (x, y - d), (x, y + d)
    pins[(ref, "1")], pins[(ref, "2")] = p1, p2
    g = 'transform="translate(%g %g) rotate(%d)"' % (x, y, 0 if orient == "H" else 90)
    body = {"R": '<rect x="-16" y="-6" width="32" height="12" fill="#fff" stroke="#222" stroke-width="1.6"/>',
            "C": '<line x1="-3" y1="-9" x2="-3" y2="9" stroke="#222" stroke-width="2.2"/><line x1="3" y1="-9" x2="3" y2="9" stroke="#222" stroke-width="2.2"/>',
            "D": '<polygon points="8,-8 8,8 -8,0" fill="#fff" stroke="#222" stroke-width="1.6"/><line x1="-8" y1="-8" x2="-8" y2="8" stroke="#222" stroke-width="2.4"/>',
            "Z": '<polygon points="8,-8 8,8 -8,0" fill="#fff" stroke="#222" stroke-width="1.6"/><polyline points="-11,-8 -8,-8 -8,8 -5,8" fill="none" stroke="#222" stroke-width="2.4"/>',
            "LED": '<polygon points="8,-8 8,8 -8,0" fill="#fff" stroke="#222" stroke-width="1.6"/><line x1="-8" y1="-8" x2="-8" y2="8" stroke="#222" stroke-width="2.4"/><line x1="0" y1="-10" x2="6" y2="-16" stroke="#222" stroke-width="1.4"/><line x1="-4" y1="-10" x2="2" y2="-16" stroke="#222" stroke-width="1.4"/>',
            "L": '<path d="M-16,0 a4,4 0 0,1 8,0 a4,4 0 0,1 8,0 a4,4 0 0,1 8,0 a4,4 0 0,1 8,0" fill="none" stroke="#222" stroke-width="1.8"/>',
            "F": '<rect x="-14" y="-5" width="28" height="10" fill="#fff" stroke="#222" stroke-width="1.6"/><line x1="-14" y1="0" x2="14" y2="0" stroke="#222" stroke-width="1.4"/>',
            "SW": '<line x1="-14" y1="0" x2="-6" y2="0" stroke="#222" stroke-width="1.8"/><line x1="6" y1="0" x2="14" y2="0" stroke="#222" stroke-width="1.8"/><line x1="-6" y1="2" x2="8" y2="-8" stroke="#222" stroke-width="1.8"/>'}[kind]
    stub = 14 if kind in ("R", "F") else 8 if kind in ("C",) else 14
    svg.append('<g %s>%s<line x1="-30" y1="0" x2="%g" y2="0" stroke="#222" stroke-width="1.6"/><line x1="%g" y1="0" x2="30" y2="0" stroke="#222" stroke-width="1.6"/></g>'
               % (g, body, -stub, stub))
    lx, ly = (x, y - 12) if orient == "H" else (x + 14, y - 2)
    T(lx, ly, ref, 10, "middle" if orient == "H" else "start", weight=600)
    T(lx, ly + 11 if orient == "H" else ly + 11, VAL[ref].split(" ")[0], 9.5, "middle" if orient == "H" else "start", "#666")
    # el pin 1 (catodo en D/LED/Z) queda marcado con la barra: en H a la izquierda, en V arriba

def wire(net, path):
    """path: lista de "ref.pin" o (x,y). Se dibuja en orden, y todos los pines quedan en la red."""
    pts = []
    for p in path:
        if isinstance(p, str):
            ref, pid = p.split("."); pts.append(pins[(ref, pid)]); used.setdefault(net, set()).add(p)
        else: pts.append(p)
    svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round"/>'
               % (" ".join("%g,%g" % q for q in pts), col(net)))
    for q in pts:
        if sum(1 for r in pts if r == q) > 1 or any(q == pins.get(k) for k in ()):
            pass
    return pts

def dot(x, y, net): svg.append('<circle cx="%g" cy="%g" r="3.4" fill="%s"/>' % (x, y, col(net)))

def label(net, pin, dx=0, dy=0, side="R"):
    """Etiqueta de red en el extremo de un pin (o desplazada)."""
    ref, pid = pin.split("."); x, y = pins[(ref, pid)]
    used.setdefault(net, set()).add(pin)
    if dx or dy: L(x, y, x + dx, y + dy, col(net), 2); x, y = x + dx, y + dy
    if net == "GND":
        L(x, y, x, y + 10, col(net), 2); L(x - 9, y + 10, x + 9, y + 10, "#555", 2.2)
        L(x - 6, y + 14, x + 6, y + 14, "#555", 2); L(x - 3, y + 18, x + 3, y + 18, "#555", 2); return
    if side == "R": T(x + 5, y + 4, net, 10, "start", col(net), 600)
    elif side == "L": T(x - 5, y + 4, net, 10, "end", col(net), 600)
    elif side == "T": T(x, y - 5, net, 10, "middle", col(net), 600)
    else: T(x, y + 14, net, 10, "middle", col(net), 600)

# =============================================================== componentes
box("J1", 40, 150, 130, 330, "OBD2 macho", [("16", "R", 60, "16 +12V"), ("7", "R", 120, "7 K"), ("15", "R", 150, "15 L"),
                                             ("4", "R", 240, "4 GND"), ("5", "R", 270, "5 GND")])
box("J4", 40, 700, 130, 110, "cola 20 pines", [("1", "R", 40, "1 GND"), ("2", "R", 65, "2 K"), ("3", "R", 90, "3 +12")])
label("GND", "J4.1"); label("K_LINE", "J4.2"); label("VBAT_RAW", "J4.3")
T(40, 830, "al conector redondo: 19 GND, 15+17+20 K, 16 (KL15) o 14 (KL30) +12", 9.5, color="#555")
part2("F1", "F", 270, 210, "H"); part2("D1", "Z", 340, 290, "V"); part2("D2", "D", 470, 210, "H")
box("U2", 640, 170, 130, 130, "AP63203 3V3", [("3", "L", 55, "VIN"), ("2", "L", 80, "EN"), ("1", "L", 110, "FB"),
                                              ("6", "R", 55, "BST"), ("5", "R", 80, "SW"), ("4", "R", 110, "GND")])
part2("C10", "C", 380, 330, "V"); part2("C11", "C", 410, 330, "V"); part2("C12", "C", 440, 330, "V")
part2("R10", "R", 560, 255, "V"); part2("R11", "R", 560, 345, "V"); part2("R12", "R", 600, 345, "V")
part2("C13", "C", 830, 195, "V"); part2("L1", "L", 860, 250, "H")
part2("C14", "C", 930, 330, "V"); part2("C15", "C", 960, 330, "V")
box("U1", 300, 560, 150, 150, "L9637D", [("7", "L", 50, "7 VS"), ("6", "L", 80, "6 K"), ("8", "L", 110, "8 LI"), ("2", "L", 135, "2 LO"),
                                         ("3", "R", 50, "VCC 3"), ("1", "R", 80, "RX 1"), ("4", "R", 110, "TX 4"), ("5", "R", 135, "GND 5")])
part2("R1", "R", 230, 640, "V"); part2("C1", "C", 520, 660, "V")
part2("R2", "R", 300, 790, "V"); part2("R3", "R", 300, 880, "V"); part2("C3", "C", 360, 880, "V")
box("J3", 620, 560, 130, 250, "USB-C 16p", [("A4", "R", 50, "VBUS A4"), ("A9", "R", 70, "VBUS A9"), ("A6", "R", 105, "D+ A6"), ("B6", "R", 125, "D+ B6"),
                                             ("A7", "R", 155, "D- A7"), ("B7", "R", 175, "D- B7"), ("A5", "R", 205, "CC1 A5"), ("B5", "R", 225, "CC2 B5"),
                                             ("A1", "L", 190, "A1"), ("A12", "L", 210, "A12"), ("SH", "L", 230, "SH")])
part2("D3", "D", 820, 615, "H"); part2("R5", "R", 800, 800, "V"); part2("R6", "R", 840, 830, "V")
box("U3", 1110, 400, 200, 460, "ESP32-S3-WROOM-1-N16R8", [("2", "L", 50, "2 3V3"), ("3", "L", 90, "3 EN"), ("4", "L", 130, "4 IO4 ADC"),
    ("10", "L", 170, "10 IO17"), ("11", "L", 210, "11 IO18"), ("13", "L", 250, "13 USB D-"), ("14", "L", 290, "14 USB D+"),
    ("1", "L", 400, "1 GND"), ("40", "L", 420, "40 GND"), ("41", "L", 440, "41 GND"),
    ("27", "R", 50, "IO0 27"), ("31", "R", 130, "IO38 31"), ("37", "R", 210, "TXD0 37"), ("36", "R", 250, "RXD0 36")])
part2("C5", "C", 1000, 500, "Vr"); part2("C6", "C", 1040, 500, "V")
part2("R4", "R", 1060, 450, "V"); part2("C7", "C", 1000, 560, "V"); part2("SW1", "SW", 940, 560, "V")
part2("R9", "R", 1400, 410, "V"); part2("SW2", "SW", 1440, 500, "V")
part2("R8", "R", 1400, 530, "H"); part2("LED2", "LED", 1470, 570, "V")
part2("R7", "R", 1400, 720, "H"); part2("LED1", "LED", 1470, 760, "V")
box("J2", 1370, 790, 150, 180, "DEBUG 1x6 (sin poblar)", [("1", "L", 50, "1 EN"), ("2", "L", 70, "2 IO0"), ("3", "L", 90, "3 TXD0"),
                                                          ("4", "L", 110, "4 RXD0"), ("5", "L", 130, "5 GND"), ("6", "L", 150, "6 3V3")])

# ==================================================================== cables
# --- entrada 12 V
wire("VBAT_RAW", ["J1.16", "F1.1"])
wire("VBAT_F", ["F1.2", (340, 210), "D1.1"]); wire("VBAT_F", [(340, 210), "D2.2"]); dot(340, 210, "VBAT_F")
T(370, 200, "VBAT_F", 10, "start", col("VBAT_F"), 600)
label("GND", "D1.2")
# --- linea K: 7 y 15 puenteados en la placa
wire("K_LINE", ["J1.7", (230, 270), "J1.15"]); dot(230, 300, "K_LINE")
wire("K_LINE", [(230, 300), (230, 610), "R1.1"]); wire("K_LINE", [(230, 640), (260, 640), "U1.6"])
dot(230, 640, "K_LINE"); T(236, 460, "K_LINE", 10, "start", col("K_LINE"), 600)
wire("VBAT_F", ["R1.2", (230, 690), (200, 690), (200, 610), "U1.7"]); T(160, 606, "VBAT_F", 10, "start", col("VBAT_F"), 600)
# --- buck
wire("VIN", ["D2.1", (600, 210), (600, 225), "U2.3"]); T(520, 204, "VIN", 10, "start", col("VIN"), 600)
wire("VIN", [(500, 210), (500, 300), "C12.1"]); wire("VIN", ["C12.1", "C11.1"]); wire("VIN", ["C11.1", "C10.1"])
dot(500, 210, "VIN"); dot(440, 300, "VIN"); dot(410, 300, "VIN")
# UVLO: EN del buck por divisor desde VBAT_F, con hysteresis interna; VBUS lo fuerza a encendido
wire("EN_BUCK", ["U2.2", (580, 250), (580, 300), (560, 300)]); wire("EN_BUCK", ["R10.2", "R11.1"]); wire("EN_BUCK", ["R12.2", (600, 300), (560, 300)])
dot(560, 300, "EN_BUCK"); T(586, 296, "EN_BUCK", 9.5, "start", col("EN_BUCK"), 600)
label("VBAT_F", "R10.1", -20, 0, "L"); label("GND", "R11.2"); label("VBUS", "R12.1", -20, 0, "L")
label("GND", "C10.2"); label("GND", "C11.2"); label("GND", "C12.2"); label("GND", "U2.4")
wire("BST", ["U2.6", (830, 225), "C13.1"]); dot(830, 225, "BST")
wire("SW", ["U2.5", (830, 250), "L1.1"]); wire("SW", ["C13.2", (830, 250)]); dot(830, 250, "SW")
wire("+3V3", ["L1.2", (930, 250), "C14.1"]); wire("+3V3", [(930, 300), (960, 300), "C15.1"]); dot(930, 300, "+3V3"); dot(960, 300, "+3V3")
wire("+3V3", ["U2.1", (618, 395), (990, 395), (990, 250), (930, 250)]); dot(930, 250, "+3V3")
T(1000, 254, "+3V3", 10, "start", col("+3V3"), 600)
label("GND", "C14.2"); label("GND", "C15.2")
# --- L9637D
label("+3V3", "U1.3", 40, 0); wire("+3V3", [(490, 610), (520, 610), "C1.1"]); dot(490, 610, "+3V3")
wire("K_RX", ["U1.1", (500, 640)]); label("K_RX", "U1.1", 28, 0)
wire("K_TX", ["U1.4", (500, 670)]); label("K_TX", "U1.4", 28, 0)
label("GND", "U1.5", 10, 0); label("GND", "C1.2")
T(255, 664, "nc", 9, "start", "#888"); T(255, 689, "nc", 9, "start", "#888")
# --- divisor de sensado
label("VBAT_F", "R2.1", 0, -20, "T"); wire("V_SENSE", ["R2.2", (300, 835), "R3.1"]); wire("V_SENSE", [(300, 835), (360, 835), "C3.1"])
dot(300, 835, "V_SENSE"); T(372, 830, "V_SENSE", 10, "start", col("V_SENSE"), 600)
label("GND", "R3.2"); label("GND", "C3.2")
# --- USB
wire("VBUS", ["J3.A4", (790, 610), "J3.A9"]); wire("VBUS", [(790, 615), "D3.2"]); dot(790, 615, "VBUS")
label("VIN", "D3.1")
wire("USB_DP", ["J3.A6", (790, 665), "J3.B6"]); label("USB_DP", "J3.A6", 40, 0)
wire("USB_DN", ["J3.A7", (790, 715), "J3.B7"]); label("USB_DN", "J3.A7", 40, 0)
wire("CC1", ["J3.A5", (800, 765), "R5.1"]); wire("CC2", ["J3.B5", (840, 785), "R6.1"])
label("GND", "R5.2"); label("GND", "R6.2")
wire("GND", ["J3.A1", (580, 750), "J3.A12"]); wire("GND", [(580, 770), "J3.SH"]); label("GND", "J3.SH", -30, 0)
# --- ESP32
wire("+3V3", ["U3.2", (1000, 450), "C5.2"]); wire("+3V3", [(1040, 450), "C6.1"]); dot(1040, 450, "+3V3"); dot(1000, 450, "+3V3")
label("+3V3", "C5.2", 0, -20, "T"); wire("+3V3", [(1060, 450), "R4.1"]); dot(1060, 450, "+3V3")
wire("EN", ["U3.3", (940, 490), "SW1.1"]); wire("EN", ["R4.2", (1060, 490)]); wire("EN", ["C7.1", (1000, 490)])
dot(1060, 490, "EN"); dot(1000, 490, "EN"); T(900, 486, "EN", 10, "end", col("EN"), 600)
label("GND", "C5.1"); label("GND", "C6.2"); label("GND", "C7.2"); label("GND", "SW1.2")
label("V_SENSE", "U3.4", -30, 0, "L"); label("K_TX", "U3.10", -30, 0, "L"); label("K_RX", "U3.11", -30, 0, "L")
label("USB_DN", "U3.13", -30, 0, "L"); label("USB_DP", "U3.14", -30, 0, "L")
wire("GND", ["U3.1", (1070, 800), (1070, 840), "U3.41"]); wire("GND", ["U3.40", (1070, 820)]); label("GND", "U3.41", -30, 0)
wire("IO0", ["U3.27", (1400, 450), "R9.2"]); wire("IO0", [(1440, 450), "SW2.1"]); dot(1400, 450, "IO0"); dot(1440, 450, "IO0")
label("+3V3", "R9.1", 0, -20, "T"); label("GND", "SW2.2"); T(1350, 446, "IO0", 10, "start", col("IO0"), 600)
wire("IO38", ["U3.31", "R8.1"]); wire("LED2_A", ["R8.2", (1470, 530), "LED2.2"]); label("GND", "LED2.1", 0, -20 if False else 0)
label("TXD0", "U3.37", 30, 0); label("RXD0", "U3.36", 30, 0)
label("+3V3", "R7.1", -20, 0, "L"); wire("LED1_A", ["R7.2", (1470, 720), "LED1.2"]); label("GND", "LED1.1")
label("EN", "J2.1", -20, 0, "L"); label("IO0", "J2.2", -20, 0, "L"); label("TXD0", "J2.3", -20, 0, "L")
label("RXD0", "J2.4", -20, 0, "L"); label("GND", "J2.5", -20, 0); label("+3V3", "J2.6", -20, 0, "L")
wire("GND", ["J1.4", (200, 390), "J1.5"]); label("GND", "J1.5", 20, 0)

# ------------------------------------------------------------------ notas
T(40, 40, "E36 K-line reader — ESP32-S3 + L9637D + AP63203, una sola placa (rev B)", 16, weight=600)
T(40, 60, "GND, +3V3, VIN y VBAT_F se conectan por etiqueta. LED2 anodo(2)->R8; catodos (pin 1) a GND. D1: banda (pin 1) a VBAT_F.", 10.5, color="#555")
T(40, 76, "K va a OBD2 7 Y 15 (linea L): el DME del E36 despierta por L. R1 510R 0,75W = pull-up K a VS (RKO <= 5k por hoja de datos).", 10.5, color="#555")
T(40, 92, "USB VBUS y 12V se OR-ean por D2/D3 hacia VIN; el buck saca 3V3 directo. R10/R11 = UVLO del buck: arranca a 12,5 V y corta a 11,5 V; R12 hace que con USB arranque siempre.", 10.5, color="#555")

# ============================================================== verificacion
def verify():
    fail = 0
    for net, pl in N.items():
        a, b = set(pl), used.get(net, set())
        if a != b:
            fail += 1; print("%-9s DISCREPA  faltan %s  sobran %s" % (net, sorted(a - b), sorted(b - a)))
    for net in set(used) - set(N):
        fail += 1; print("%s dibujada pero no existe" % net)
    return fail

def netlist():
    out = ['(export (version "E")', '  (design (source "e36-kline-onboard") (tool "gen_schematic.py"))', '  (components']
    for ref, lib, fpn, x, y, rot, val, mpn, lcsc, note in P:
        out.append('    (comp (ref "%s") (value "%s") (footprint "%s:%s") (fields (field (name "MPN") "%s") (field (name "LCSC") "%s") (field (name "Nota") "%s")))'
                   % (ref, val, lib, fpn, mpn, lcsc, note))
    out.append('  )\n  (nets')
    for i, (net, pl) in enumerate(N.items(), 1):
        out.append('    (net (code "%d") (name "%s")' % (i, net))
        for p in pl:
            r, pin = p.split("."); out.append('      (node (ref "%s") (pin "%s"))' % (r, pin))
        out.append('    )')
    out.append('  )\n)')
    open(os.path.join(HERE, "e36-kline-onboard.net"), "w").write("\n".join(out) + "\n")

if __name__ == "__main__":
    f = verify()
    if f:
        print("%d discrepancias: NO se emite el esquema" % f); sys.exit(1)
    body = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1560 1000" font-family="IBM Plex Mono, Menlo, monospace">' \
           '<rect width="1560" height="1000" fill="#fbfbf8"/>' + "\n".join(svg) + "</svg>"
    open(os.path.join(HERE, "schematic.svg"), "w").write(body)
    netlist()
    print("esquema coincide con las %d redes; %d elementos -> schematic.svg, e36-kline-onboard.net" % (len(N), len(svg)))
