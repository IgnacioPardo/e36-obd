"""Genera la placa del front-end K-Line desde cero, con pcbnew.

Se corre con el Python que trae KiCad:

  PY=/Volumes/KiCad/KiCad/KiCad.app/Contents/Frameworks/Python.framework/\\
     Versions/3.9/bin/python3
  $PY hardware/gen_board.py

El punto de todo esto es que el ruteo lo verifique el DRC y no yo a ojo: el
dibujo anterior tenia VBAT y +3V3 a 0,30 mm de eje a eje con anchos de 0,8 y
0,5 mm, o sea un corto de +12 V a +3,3 V que no se ve mirando un SVG.

Decisiones que vienen del netlist y de la hoja de datos:

  · U1 alimentado a 3,3 V (Vcc min 3 V) -> logica compatible con el ESP32
    sin conversor de nivel.
  · K va a los dos pines del OBD2, 7 y 15: el DME despierta por la linea L y
    el L9637D no puede manejarla (LI/LO son comparador, no driver).
  · R1 de 510 ohm entre K y VS, exigido por la hoja de datos (RKO <= 5 kOhm).
  · El MCU NO va en la placa. Sale por J2, asi que la PCB no se rehace si
    cambias de ESP32.

J1 es una tira de 5 pines para cable: la ficha OBD2 se recicla del ELM327 y se
conecta con cables, no montada en la placa.
"""

import os
import sys

import pcbnew

FPLIB = "/Volumes/KiCad/KiCad/KiCad.app/Contents/SharedSupport/footprints"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kline-frontend.kicad_pcb")

MM = pcbnew.FromMM

# Contorno de la placa. 80 x 50 mm: con 60x40 el ruteo quedaba estrangulado.
X0, Y0, W, H = 50.0, 50.0, 80.0, 50.0

# Anchos por clase de red, de LAYOUT.md.
W_PWR = 0.8
W_KLINE = 0.5
W_SIG = 0.3

# ---------------------------------------------------------------- componentes
# (ref, libreria, footprint, x, y, rotacion, valor)
PARTS = [
    ("J1", "Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical",
     53.0, 76.0, 90.0, "OBD2-5"),
    ("F1", "Fuse", "Fuse_1206_3216Metric_Pad1.42x1.75mm_HandSolder",
     62.0, 58.0, 0.0, "1A"),
    ("C2", "Capacitor_THT", "CP_Radial_D10.0mm_P5.00mm",
     64.0, 92.0, 0.0, "470u/50V"),
    ("D1", "Diode_SMD", "D_SMB",
     76.0, 58.0, 0.0, "SMBJ26A"),
    ("R1", "Resistor_SMD", "R_0805_2012Metric",
     70.0, 76.0, 0.0, "510R"),
    ("U1", "Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm",
     88.0, 76.0, 180.0, "L9637D"),
    ("C1", "Capacitor_SMD", "C_0805_2012Metric",
     88.0, 82.0, 180.0, "100n"),
    ("R2", "Resistor_SMD", "R_0805_2012Metric",
    104.0, 58.0, 0.0, "100k"),
    ("R3", "Resistor_SMD", "R_0805_2012Metric",
    104.0, 63.0, 0.0, "22k"),
    ("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical",
     78.0, 94.0, 90.0, "BUCK"),
    ("J2", "Connector_JST", "JST_XH_B7B-XH-A_1x07_P2.50mm_Vertical",
     122.0, 84.0, 90.0, "MCU-7"),
    ("H1", "MountingHole", "MountingHole_3.2mm_M3", 55.0, 55.0, 0.0, "M3"),
    ("H2", "MountingHole", "MountingHole_3.2mm_M3", 125.0, 55.0, 0.0, "M3"),
    ("H3", "MountingHole", "MountingHole_3.2mm_M3", 55.0, 95.0, 0.0, "M3"),
    ("H4", "MountingHole", "MountingHole_3.2mm_M3", 125.0, 95.0, 0.0, "M3"),
]

# ---------------------------------------------------------------------- redes
# red -> [(ref, pad), ...]
NETS = {
    "GND": [("J1", "4"), ("J1", "5"), ("C2", "2"), ("D1", "1"), ("U1", "5"),
            ("J3", "2"), ("J3", "4"), ("R3", "2"), ("C1", "2"),
            ("J2", "1"), ("J2", "7")],
    "VBAT_RAW": [("J1", "1"), ("F1", "1")],
    "VBAT_FUSED": [("F1", "2"), ("C2", "1"), ("D1", "2"), ("U1", "7"),
                   ("J3", "1"), ("R1", "2"), ("R2", "1")],
    "K_LINE": [("J1", "2"), ("J1", "3"), ("R1", "1"), ("U1", "6")],
    "+5V": [("J3", "3"), ("J2", "2")],
    "K_RX": [("U1", "1"), ("J2", "3")],
    "+3V3": [("J2", "4"), ("U1", "3"), ("C1", "1")],
    "K_TX": [("U1", "4"), ("J2", "5")],
    "V_SENSE": [("R2", "2"), ("R3", "1"), ("J2", "6")],
}

# Ruteo explicito: (red, ancho, capa, [(ref,pad) o (x,y) ...]) recorrido en orden.
# GND no se rutea: cada pad lleva via al plano de masa de la capa inferior.
ROUTES = [
    # --- 12 V de entrada -----------------------------------------------
    ("VBAT_RAW", W_PWR, "F", [("J1", "1"), (53.0, 66.0), (60.51, 66.0),
                              ("F1", "1")]),
    # espina superior: fusible -> TVS -> divisor
    ("VBAT_FUSED", W_PWR, "F", [("F1", "2"), (63.49, 54.0), (78.15, 54.0),
                                ("D1", "2")]),
    ("VBAT_FUSED", W_PWR, "F", [(78.15, 54.0), (103.09, 54.0), ("R2", "1")]),
    # bajada unica por x=82, a la izquierda de U1
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 54.0), (82.0, 71.0)]),
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 76.64), ("U1", "7")]),
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 71.0), (70.91, 71.0), ("R1", "2")]),
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 71.0), (82.0, 90.0)]),
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 90.0), (64.0, 90.0), ("C2", "1")]),
    ("VBAT_FUSED", W_PWR, "F", [(82.0, 90.0), (78.0, 90.0), ("J3", "1")]),

    # --- linea K: los dos pines del OBD2, por arriba del conector -------
    ("K_LINE", W_KLINE, "F", [("J1", "2"), (55.54, 72.0), (58.08, 72.0),
                              ("J1", "3")]),
    ("K_LINE", W_KLINE, "F", [(58.08, 72.0), (69.09, 72.0), ("R1", "1")]),
    # salto a la capa inferior para pasar por debajo de la bajada de 12 V
    ("K_LINE", W_KLINE, "F", [("R1", "1"), (69.09, 68.0), (79.0, 68.0)]),
    ("K_LINE", W_KLINE, "B", [(79.0, 68.0), (85.0, 68.0)]),
    ("K_LINE", W_KLINE, "F", [(85.0, 68.0), (86.8, 68.0), (86.8, 70.0),
                              (83.4, 70.0), (83.4, 75.36), ("U1", "6")]),

    # --- los tres del MCU: casi rectos y paralelos ----------------------
    ("K_TX", W_SIG, "F", [("U1", "4"), ("J2", "5")]),
    ("+3V3", W_SIG, "F", [("U1", "3"), ("J2", "4")]),
    ("K_RX", W_SIG, "F", [("U1", "1"), ("J2", "3")]),

    # --- desacople: por abajo, saltando K_RX ----------------------------
    ("+3V3", W_SIG, "B", [(93.0, 75.45), (93.0, 82.0), (90.5, 82.0)]),
    ("+3V3", W_SIG, "F", [(90.5, 82.0), ("C1", "1")]),

    # --- divisor de sensado --------------------------------------------
    ("V_SENSE", W_SIG, "F", [("R2", "2"), (104.91, 60.5), (103.09, 60.5),
                             ("R3", "1")]),
    ("V_SENSE", W_SIG, "F", [("R3", "1"), (103.09, 67.0), (110.0, 67.0),
                             (110.0, 71.5), ("J2", "6")]),

    # --- 5 V del buck al MCU, por el canal inferior ---------------------
    ("+5V", W_PWR, "F", [("J3", "3"), (83.08, 97.0), (118.0, 97.0),
                         (118.0, 81.5), ("J2", "2")]),
]

# Vias que cosen los saltos de capa a la capa inferior.
JUMP_VIAS = [("K_LINE", 79.0, 68.0), ("K_LINE", 85.0, 68.0),
             ("+3V3", 93.0, 75.45), ("+3V3", 90.5, 82.0)]

# Vias solo para los pads SMD de masa: los pasantes ya llegan al plano inferior.
GND_VIAS = [("D1", "1", 71.5, 58.0), ("U1", "5", 85.53, 72.6),
            ("R3", "2", 107.0, 63.0), ("C1", "2", 85.0, 82.0)]



def main():
    board = pcbnew.CreateEmptyBoard()

    # -------------------------------------------------------- reglas
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    try:
        nc = ds.GetDefault()
        nc.SetClearance(MM(0.2))
        nc.SetTrackWidth(MM(0.3))
        nc.SetViaDiameter(MM(0.7))
        nc.SetViaDrill(MM(0.35))
    except Exception as exc:                      # pragma: no cover
        print("aviso: no se pudieron fijar reglas por defecto:", exc)

    # -------------------------------------------------------- componentes
    fps = {}
    for ref, lib, name, x, y, rot, val in PARTS:
        fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
        if fp is None:
            sys.exit("no se pudo cargar %s:%s" % (lib, name))
        fp.SetReference(ref)
        fp.SetValue(val)
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        if rot:
            fp.SetOrientationDegrees(rot)
        board.Add(fp)
        fps[ref] = fp
    print("componentes colocados: %d" % len(fps))

    # -------------------------------------------------------- redes
    nets = {}
    for name in NETS:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    for name, pads in NETS.items():
        for ref, padnum in pads:
            pad = fps[ref].FindPadByNumber(padnum)
            if pad is None:
                sys.exit("no existe el pad %s.%s" % (ref, padnum))
            pad.SetNet(nets[name])
    print("redes creadas: %d" % len(nets))

    if os.environ.get("DUMP"):
        for ref in sorted(fps):
            for pad in fps[ref].Pads():
                pos = pad.GetPosition()
                print("  %-3s pad %-2s  %7.2f %7.2f  %s" % (
                    ref, pad.GetNumber(), pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y),
                    pad.GetNetname() or "-"))
        return

    def point(spec):
        """Un (ref,pad) devuelve la posicion real del pad; un (x,y) va tal cual."""
        if isinstance(spec[0], str):
            return fps[spec[0]].FindPadByNumber(spec[1]).GetPosition()
        return pcbnew.VECTOR2I(MM(spec[0]), MM(spec[1]))

    # -------------------------------------------------------- pistas
    layer = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
    seg = 0
    for netname, width, lay, path in ROUTES:
        pts = [point(p) for p in path]
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(a)
            t.SetEnd(b)
            t.SetWidth(MM(width))
            t.SetLayer(layer[lay])
            t.SetNet(nets[netname])
            board.Add(t)
            seg += 1
    print("segmentos de pista: %d" % seg)

    # -------------------------------------------------------- vias de masa
    vias = 0
    for ref, padnum, vx, vy in GND_VIAS:
        pos = fps[ref].FindPadByNumber(padnum).GetPosition()
        vpos = pcbnew.VECTOR2I(MM(vx), MM(vy))
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pos); t.SetEnd(vpos)
        t.SetWidth(MM(W_SIG)); t.SetLayer(pcbnew.F_Cu); t.SetNet(nets["GND"])
        board.Add(t)
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(vpos)
        v.SetWidth(MM(0.7))
        v.SetDrill(MM(0.35))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets["GND"])
        board.Add(v)
        vias += 1
    print("vias a masa: %d" % vias)

    for netname, vx, vy in JUMP_VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(vx), MM(vy)))
        v.SetWidth(MM(0.7)); v.SetDrill(MM(0.35))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(nets[netname]); board.Add(v)
    print("vias de salto de capa: %d" % len(JUMP_VIAS))

    # -------------------------------------------------------- contorno
    corners = [(X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)

    # -------------------------------------------------------- plano de masa
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetNet(nets["GND"])
    zone.SetLocalClearance(MM(0.3))
    outline = zone.Outline()
    outline.NewOutline()
    for cx, cy in corners:
        outline.Append(MM(cx), MM(cy))
    board.Add(zone)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("plano de masa: rellenado")

    pcbnew.SaveBoard(OUT, board)
    print("guardado: %s (%d bytes)" % (OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
