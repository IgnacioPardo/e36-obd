"""Dibuja el esquema DESDE el netlist y verifica que coincidan.

El PCB que dibuje a mano tenia un corto de +12 V a +3,3 V porque la geometria
no la verifico nadie. Un esquema no tiene geometria que violar, pero si puede
mentir sobre la conectividad. Asi que aca las conexiones se declaran como
datos, se comparan contra el netlist, y el SVG solo se emite si coinciden.

Uso:  ./.venv/bin/python hardware/gen_schematic.py
"""

import re
import sys

NET = "hardware/kline-salvage.net"
OUT = "hardware/kline-salvage.svg"

# ------------------------------------------------- posicion de cada pin
PINS = {
    ("MOD1", "OBD16"): (250, 90), ("MOD1", "VREG5"): (250, 150),
    ("MOD1", "TXIN"): (250, 250), ("MOD1", "RXOUT"): (250, 310),
    ("MOD1", "GND"): (150, 470),
    ("U2", "5V"): (640, 150), ("U2", "3V3"): (640, 200),
    ("U2", "GPIO17"): (640, 250), ("U2", "GPIO18"): (640, 310),
    ("U2", "GPIO4"): (640, 390), ("U2", "GND"): (740, 470),
    ("R1", "1"): (330, 310), ("R1", "2"): (410, 310),
    ("R2", "1"): (450, 340), ("R2", "2"): (450, 400),
    ("R3", "1"): (330, 90), ("R3", "2"): (330, 360),
    ("R4", "1"): (330, 400), ("R4", "2"): (330, 450),
    ("D1", "1"): (500, 310), ("D1", "2"): (500, 230),
}

# --------------------------------- recorrido de cada red, en orden
WIRES = {
    "VBAT_12V": [[("MOD1", "OBD16"), ("R3", "1")]],
    "+5V": [[("MOD1", "VREG5"), ("U2", "5V")]],
    "K_TX": [[("MOD1", "TXIN"), ("U2", "GPIO17")]],
    "K_RX_RAW": [[("MOD1", "RXOUT"), ("R1", "1")]],
    "K_RX": [[("R1", "2"), (450, 310), ("D1", "1")],
             [(450, 310), ("R2", "1")],
             [("D1", "1"), (560, 310), ("U2", "GPIO18")]],
    "+3V3": [[("D1", "2"), (560, 230), ("U2", "3V3")]],
    "V_SENSE": [[("R3", "2"), ("R4", "1")],
                [(330, 380), (560, 380), (560, 390), ("U2", "GPIO4")]],
    "GND": [[("MOD1", "GND"), (790, 470), ("U2", "GND")],
            [("R2", "2"), (450, 470)],
            [("R4", "2"), (330, 470)]],
}

# los vertices intermedios que caen sobre un tramo ya dibujado de la misma red
IMPLICIT = {"V_SENSE": {(330, 380)}}


def parse_netlist(path):
    src = open(path).read()
    out = {}
    for blk in re.split(r"\(net \(code ", src)[1:]:
        name = re.search(r'\(name "([^"]+)"\)', blk).group(1)
        out[name] = set(re.findall(
            r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)\)', blk))
    return out


def drawn_nodes():
    out = {}
    for net, paths in WIRES.items():
        got = set()
        for path in paths:
            for pt in path:
                if isinstance(pt[0], str) and (pt[0], pt[1]) in PINS:
                    got.add((pt[0], pt[1]))
        out[net] = got
    return out


def verify():
    netlist, drawn = parse_netlist(NET), drawn_nodes()
    print("%-13s %7s %7s  %s" % ("red", "netlist", "dibujo", "estado"))
    fail = 0
    for name in sorted(netlist):
        a, b = netlist[name], drawn.get(name, set())
        if a == b:
            print("%-13s %7d %7d  ok" % (name, len(a), len(b)))
        else:
            fail += 1
            print("%-13s %7d %7d  DISCREPA" % (name, len(a), len(b)))
            if a - b:
                print("               falta dibujar : %s" % sorted(a - b))
            if b - a:
                print("               sobra dibujado: %s" % sorted(b - a))
    for name in set(drawn) - set(netlist):
        fail += 1
        print("%-13s dibujada pero no esta en el netlist" % name)
    return fail


COL = {"VBAT_12V": "#c0392b", "+5V": "#c0392b", "+3V3": "#c0392b",
       "K_TX": "#2166a8", "K_RX": "#2166a8", "K_RX_RAW": "#2166a8",
       "V_SENSE": "#7a5c1e", "GND": "#333333"}


def pt(p):
    return PINS[(p[0], p[1])] if isinstance(p[0], str) and (p[0], p[1]) in PINS else p


def emit():
    w = []
    for net, paths in WIRES.items():
        c = COL.get(net, "#333")
        for path in paths:
            pts = " ".join("%d,%d" % pt(p) for p in path)
            w.append('<polyline points="%s" fill="none" stroke="%s" '
                      'stroke-width="2.2" stroke-linejoin="round"/>' % (pts, c))
    # nodos de union
    for net, paths in WIRES.items():
        seen = {}
        for path in paths:
            for p in path:
                q = pt(p)
                seen[q] = seen.get(q, 0) + 1
        for q, n in seen.items():
            if n > 1:
                w.append('<circle cx="%d" cy="%d" r="4" fill="%s"/>'
                          % (q[0], q[1], COL.get(net, "#333")))
    body = "\n".join(w)

    sym = []
    def box(x, y, w_, h, ref, val, sub=""):
        sym.append('<rect x="%d" y="%d" width="%d" height="%d" rx="3" '
                   'fill="var(--card)" stroke="currentColor" stroke-width="2"/>'
                   % (x, y, w_, h))
        sym.append('<text x="%d" y="%d" font-weight="600" font-size="15" '
                   'text-anchor="middle" fill="currentColor">%s</text>'
                   % (x + w_ // 2, y + 26, ref))
        sym.append('<text x="%d" y="%d" font-size="12" text-anchor="middle" '
                   'fill="var(--ink-3)">%s</text>' % (x + w_ // 2, y + 44, val))
        if sub:
            sym.append('<text x="%d" y="%d" font-size="11" text-anchor="middle" '
                       'fill="var(--ink-3)">%s</text>' % (x + w_ // 2, y + 60, sub))

    box(100, 60, 150, 380, "MOD1", "ELM327 BT", "desarmado")
    box(640, 120, 165, 300, "U2", "ESP32-S3", "")
    # resistencias como rectangulos IEC
    for ref, x, y, w_, h in (("R1", 352, 300, 36, 20), ("R2", 440, 352, 20, 36),
                             ("R3", 320, 200, 20, 36), ("R4", 320, 408, 20, 36)):
        sym.append('<rect x="%d" y="%d" width="%d" height="%d" fill="var(--card)" '
                   'stroke="currentColor" stroke-width="2"/>' % (x, y, w_, h))
    # diodo D1, catodo arriba (clamp a 3V3)
    sym.append('<polygon points="492,286 508,286 500,266" fill="none" '
               'stroke="currentColor" stroke-width="2"/>')
    sym.append('<line x1="490" y1="266" x2="510" y2="266" stroke="currentColor" '
               'stroke-width="2.4"/>')
    # patas de los componentes: del pin al cuerpo, si no queda hueco
    # cada pata va del color de SU red: asi un cruce sin nodo se lee como cruce
    LEADS = [((330, 310), (352, 310), "K_RX_RAW"), ((388, 310), (410, 310), "K_RX"),
             ((450, 340), (450, 352), "K_RX"),     ((450, 388), (450, 400), "GND"),
             ((330, 90), (330, 200), "VBAT_12V"),  ((330, 236), (330, 360), "V_SENSE"),
             ((330, 400), (330, 408), "V_SENSE"),  ((330, 444), (330, 450), "GND"),
             ((500, 230), (500, 266), "+3V3"),     ((500, 286), (500, 310), "K_RX"),
             ((150, 440), (150, 470), "GND")]
    for a, b, net in LEADS:
        sym.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" '
                   'stroke-width="2.2"/>' % (a[0], a[1], b[0], b[1],
                                             COL.get(net, "#333")))

    # una sola masa, al extremo del riel; los demas son nodos de union
    for x, y in ((790, 470),):
        sym.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" '
                   'stroke-width="2.4"/>' % (x - 13, y, x + 13, y))
        sym.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" '
                   'stroke-width="2"/>' % (x - 8, y + 5, x + 8, y + 5))
        sym.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333" '
                   'stroke-width="2"/>' % (x - 3, y + 10, x + 3, y + 10))

    lab = []
    for (ref, pin), (x, y) in PINS.items():
        if ref == "MOD1" and pin != "GND":
            lab.append('<text x="%d" y="%d" font-size="11.5" text-anchor="end" '
                       'fill="currentColor">%s</text>' % (x - 8, y - 6, pin))
        elif ref == "U2":
            lab.append('<text x="%d" y="%d" font-size="11.5" '
                       'fill="currentColor">%s</text>' % (x + 8, y - 6, pin))
    for ref, x, y in (("R1 10k", 370, 292), ("R2 15k", 470, 374),
                      ("R3 100k", 350, 222), ("R4 22k", 350, 430),
                      ("D1 BAT54", 516, 282)):
        lab.append('<text x="%d" y="%d" font-size="11.5" fill="var(--ink-3)">%s</text>'
                   % (x, y, ref))
    # etiquetas de red sobre los tramos largos
    for txt, x, y, col in (("K_TX", 470, 244, "#2166a8"),
                            ("K_RX", 600, 304, "#2166a8"),
                            ("+5V", 470, 144, "#c0392b"),
                            ("+3V3", 592, 224, "#c0392b"),
                            ("V_SENSE", 470, 596, "#7a5c1e"),
                            ("12 V", 280, 84, "#c0392b")):
        lab.append('<text x="%d" y="%d" font-size="11" fill="%s">%s</text>'
                   % (x, y, col, txt))

    svg = ('<svg viewBox="0 0 880 540" role="img" aria-label="Esquema: la placa '
           'reciclada del ELM327 aporta la ficha OBD2, el front-end de linea K y '
           'el regulador de 5 V; sus pines TXIN y RXOUT van al ESP32, con un '
           'divisor R1 R2 y un clamp D1 en la recepcion, y un divisor R3 R4 que '
           'lleva los 12 V a una entrada ADC.">'
           '<g font-family="IBM Plex Mono, monospace">'
           + "\n".join(sym) + "\n" + body + "\n" + "\n".join(lab)
           + '</g></svg>')
    open(OUT, "w").write(svg)
    return len(sym) + len(w) + len(lab)


if __name__ == "__main__":
    fail = verify()
    print()
    if fail:
        print("%d discrepancias - NO se emite el dibujo" % fail)
        sys.exit(1)
    n = emit()
    print("el dibujo coincide con el netlist en las %d redes"
          % len(parse_netlist(NET)))
    print("%d elementos de cableado en %s" % (n, OUT))
