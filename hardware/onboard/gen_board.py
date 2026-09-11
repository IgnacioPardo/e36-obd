"""E36 K-line reader, single board: ESP32-S3-WROOM-1 + L9637D + AP63203 buck + OBD2 plug.

Se corre con el Python de KiCad 10:
  PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
  $PY hardware/onboard/gen_board.py            # placa colocada + redes + zonas, sin pistas
  $PY hardware/onboard/gen_board.py --route    # ademas exporta DSN, corre Freerouting e importa SES

Todo (colocacion, redes, anchos) esta declarado como datos aca abajo. La ficha OBD2 es un
footprint propio construido desde el STEP del conector Macchina CCBDM20 (paso 4,00 mm,
filas a 3,00 mm, patas a 2,25 y 5,25 mm del plano trasero de la brida).
"""
import os, re, subprocess, sys
import pcbnew

FPLIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "e36-kline-onboard.kicad_pcb")
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

OX, OY = 20.0, 20.0            # origen de la placa en la hoja
W, H = 90.0, 50.0              # contorno (50: la ficha USB-C sobresale 1,6 mm para atravesar la pared)

# ------------------------------------------------------------------ componentes
# ref, lib, footprint, x, y, rot, valor, MPN, LCSC, nota
P = [
 ("J1","e36obd","OBD2_Male_RightAngle_16P", 0.0,24.0,  0,"OBD2-M-90","CCBDM20 / J1962 male 90deg PCB","C9900166046 (JLC TH) verificar","paso 4.0, filas 3.0"),
 ("F1","Fuse","Fuse_1206_3216Metric",     10.6,42.0,  0,"1A 63V","S1206-S-1.0A (Sart) o BSMD1206C-1100T","C183160 / C41367221","fusible 1206"),
 ("D1","Diode_SMD","D_SMB",               15.5,43.8, 270,"SMBJ24A","SMBJ24A","C? (buscar SMBJ24A SMB)","TVS unidireccional, catodo (banda) a +12V"),
 ("D2","Diode_SMD","D_SMA",               21.7,42.5,180,"SS34","SS34","C8678","OR de entrada 12V -> VIN"),
 ("R1","Resistor_SMD","R_2010_5025Metric",  9.0,32.5, 90,"510R 0.75W","2010 510R 1%","","pull-up K a VS, 0,3 W pico"),
 ("U1","Package_SO","SOIC-8_3.9x4.9mm_P1.27mm",16.5,33.5, 90,"L9637D","L9637D013TR","C130489 verificar","transceptor ISO9141"),
 ("C1","Capacitor_SMD","C_0603_1608Metric",18.6,38.9, 270,"100n","0603 100nF 50V X7R","C14663","desacople VCC U1"),
 ("R2","Resistor_SMD","R_0603_1608Metric", 12.0,27.0,  0,"100k","0603 100k 1%","C25803","divisor V_SENSE, rama alta"),
 ("R3","Resistor_SMD","R_0603_1608Metric", 15.5,27.0,  0,"22k","0603 22k 1%","C31850","divisor V_SENSE, rama baja"),
 ("C3","Capacitor_SMD","C_0603_1608Metric",15.5,24.8,  0,"100n","0603 100nF","C14663","filtro V_SENSE"),
 ("U2","Package_TO_SOT_SMD","TSOT-23-6",   34.4,40.0,  0,"AP63203","AP63203WU-7","C780769","buck 3.3V 2A, 3.8-32V"),
 ("C10","Capacitor_SMD","C_1210_3225Metric",27.3,43.2, 270,"10u 50V","1210 10uF 50V X7R","C? (1210 10uF 50V)","CIN"),
 ("C11","Capacitor_SMD","C_1210_3225Metric",30.6,43.2, 270,"10u 50V","1210 10uF 50V X7R","","CIN"),
 ("C12","Capacitor_SMD","C_0603_1608Metric",33.6,43.7, 270,"100n 50V","0603 100nF 50V","C14663","CIN hf"),
 ("C13","Capacitor_SMD","C_0603_1608Metric",37.4,35.8,  0,"100n","0603 100nF","C14663","bootstrap BST-SW"),
 ("L1","Inductor_SMD","L_Sunlord_SWPA6045S",40.3,40.0,  0,"4.7uH 3.3A","SWPA6045S4R7MT","C78804 verificar","inductor buck"),
 ("C14","Capacitor_SMD","C_0805_2012Metric",45.5,42.0, 270,"22u 10V","0805 22uF 10V X5R","C45783","COUT"),
 ("C15","Capacitor_SMD","C_0805_2012Metric",47.5,42.0, 270,"22u 10V","0805 22uF 10V X5R","C45783","COUT"),
 ("D3","Diode_SMD","D_SMA",               60.0,34.0, 90,"SS34","SS34","C8678","OR de USB VBUS -> VIN"),
 ("J3","Connector_USB","USB_C_Receptacle_HRO_TYPE-C-31-M-12",66.5,47.9,0,"USB-C 16P","TYPE-C-31-M-12","C165948","programacion / banco"),
 ("R5","Resistor_SMD","R_0603_1608Metric", 63.0,37.4, 270,"5k1","0603 5.1k","C23186","CC1 pull-down"),
 ("R6","Resistor_SMD","R_0603_1608Metric", 70.0,37.4, 270,"5k1","0603 5.1k","C23186","CC2 pull-down"),
 ("U3","RF_Module","ESP32-S3-WROOM-1",     77.0,13.1,  0,"ESP32-S3-WROOM-1-N16R8","ESP32-S3-WROOM-1-N16R8","C2913202 verificar","antena sobre la placa, zona sin cobre"),
 ("C5","Capacitor_SMD","C_0805_2012Metric",65.0, 9.5,  0,"10u","0805 10uF 10V","C15850","desacople 3V3 modulo"),
 ("C6","Capacitor_SMD","C_0603_1608Metric",66.0,15.5, 90,"100n","0603 100nF","C14663","desacople 3V3 modulo"),
 ("R4","Resistor_SMD","R_0603_1608Metric", 64.5,12.0,  0,"10k","0603 10k","C25804","pull-up EN"),
 ("C7","Capacitor_SMD","C_0603_1608Metric",61.5,12.5, 90,"1u","0603 1uF 10V","C15849","RC de EN"),
 ("SW1","Button_Switch_SMD","SW_SPST_PTS645Sx43SMTR92",47.5,4.0,0,"RESET","TS-1187A-B-A-B / PTS645","C318884","reset (EN a GND)"),
 ("SW2","Button_Switch_SMD","SW_SPST_PTS645Sx43SMTR92",77.5,33.0,0,"BOOT","TS-1187A-B-A-B / PTS645","C318884","IO0 a GND"),
 ("R9","Resistor_SMD","R_0603_1608Metric", 66.0,29.5,  0,"10k","0603 10k","C25804","pull-up IO0"),
 ("J2","Connector_PinHeader_2.54mm","PinHeader_1x06_P2.54mm_Vertical",75.0,44.5,90,"DEBUG","1x6 2.54 (no poblar)","","EN IO0 TX0 RX0 GND 3V3"),
 ("LED1","LED_SMD","LED_0603_1608Metric",  24.0,10.0,  0,"PWR verde","0603 LED verde","C72043","3V3 presente"),
 ("R7","Resistor_SMD","R_0603_1608Metric", 24.0,12.5,  0,"2k2","0603 2.2k","C4190","LED1"),
 ("LED2","LED_SMD","LED_0603_1608Metric",  83.0,40.5, 180,"STATUS ambar","0603 LED ambar","C2296","IO38"),
 ("R8","Resistor_SMD","R_0603_1608Metric", 79.5,40.5,  0,"1k","0603 1k","C21190","LED2"),
 ("R10","Resistor_SMD","R_0603_1608Metric",29.5,36.0,  0,"36k","0603 36k 1%","C4083","UVLO buck, rama alta (Eq.1 AP63203)"),
 ("R11","Resistor_SMD","R_0603_1608Metric",32.5,36.0,  0,"3k74","0603 3.74k 1%","C22936 verificar","UVLO buck, rama baja: ON 12,5 V / OFF 11,5 V"),
 ("R12","Resistor_SMD","R_0603_1608Metric",29.5,38.2,  0,"4k7","0603 4.7k","C23162","VBUS fuerza EN: en el banco arranca igual"),
 ("J4","Connector_JST","JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",10.0,17.0, 90,"PIGTAIL","B3B-XH-A","C144394 verificar","cola al redondo de 20: 1 GND(19) 2 K(15+17+20) 3 +12(16 KL15 o 14 KL30)"),
 ("H1","MountingHole","MountingHole_3.2mm_M3",10.0, 4.0,0,"M3","","",""),
 ("H2","MountingHole","MountingHole_3.2mm_M3",54.5,46.0,0,"M3","","",""),
 ("H3","MountingHole","MountingHole_3.2mm_M3",86.5,32.0,0,"M3","","",""),
 ("H4","MountingHole","MountingHole_3.2mm_M3", 4.5,46.0,0,"M3","","",""),
]

# ------------------------------------------------------------------------ redes
N = {
 "GND": ["J1.4","J1.5","J4.1","D1.2","U1.5","C1.2","C10.2","C11.2","C12.2","U2.4","C14.2","C15.2","R3.2","C3.2",
         "U3.1","U3.40","U3.41","C5.1","C6.2","C7.2","SW1.2","SW2.2","R5.2","R6.2","LED1.1","LED2.1","J2.5","R11.2",
         "J3.A1","J3.A12","J3.SH"],
 "VBAT_RAW": ["J1.16","F1.1","J4.3"],
 "VBAT_F": ["F1.2","D1.1","D2.2","U1.7","R1.2","R2.1","R10.1"],
 "K_LINE": ["J1.7","J1.15","U1.6","R1.1","J4.2"],
 "VIN": ["D2.1","D3.1","C10.1","C11.1","C12.1","U2.3"],
 "EN_BUCK": ["U2.2","R10.2","R11.1","R12.2"],
 "SW": ["U2.5","L1.1","C13.2"],
 "BST": ["U2.6","C13.1"],
 "+3V3": ["L1.2","C14.1","C15.1","U2.1","U1.3","C1.1","U3.2","C5.2","C6.1","R4.1","R7.1","J2.6","R9.1"],
 "K_TX": ["U1.4","U3.10"],
 "K_RX": ["U1.1","U3.11"],
 "V_SENSE": ["R2.2","R3.1","C3.1","U3.4"],
 "EN": ["U3.3","R4.2","C7.1","SW1.1","J2.1"],
 "IO0": ["U3.27","R9.2","SW2.1","J2.2"],
 "TXD0": ["U3.37","J2.3"],
 "RXD0": ["U3.36","J2.4"],
 "IO38": ["U3.31","R8.1"],
 "LED2_A": ["R8.2","LED2.2"],
 "LED1_A": ["R7.2","LED1.2"],
 "VBUS": ["J3.A4","J3.A9","D3.2","R12.1"],
 "USB_DP": ["J3.A6","J3.B6","U3.14"],
 "USB_DN": ["J3.A7","J3.B7","U3.13"],
 "CC1": ["J3.A5","R5.1"],
 "CC2": ["J3.B5","R6.1"],
}
KEEPOUT = (53.0, 0.0, 90.0, 6.5)                  # x0,y0,x1,y1: antena del modulo (+15 mm a los lados)
POWER = {"VBAT_RAW","VBAT_F","VIN","SW","+3V3"}   # 0,8 mm
KLINE = {"K_LINE"}                                # 0,5 mm
MID = {"VBUS"}                                    # 0,4 mm
USB = {"USB_DP","USB_DN","CC1","CC2"}             # 0,2 mm, holgura 0,15 (pads a 0,5 mm)

# ------------------------------------------------------------ footprint OBD2
def obd2_footprint(board):
    """Macho OBD2 acodado. Origen: plano trasero de la brida, centro del conector.
    +x entra en la placa. Fila 1-8 a 2,25 mm, fila 9-16 a 5,25 mm. Pin 1 arriba (y-)."""
    tmpl = pcbnew.FootprintLoad(FPLIB + "/Connector_PinHeader_2.54mm.pretty",
                                "PinHeader_1x06_P2.54mm_Vertical")
    pth_layers = tmpl.Pads()[0].GetLayerSet()
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID("e36obd", "OBD2_Male_RightAngle_16P"))
    fp.SetReference("J1"); fp.SetValue("OBD2-M-90")
    for n in range(1, 17):
        row = 2.25 if n <= 8 else 5.25
        y = -14.0 + 4.0 * ((n - 1) % 8)
        pad = pcbnew.PAD(fp)
        pad.SetNumber(str(n))
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(V(2.1, 2.1)); pad.SetDrillSize(V(1.3, 1.3))
        pad.SetLayerSet(pth_layers)
        pad.SetPosition(V(row, y))
        fp.Add(pad)
        t = pcbnew.PCB_TEXT(fp); t.SetText(str(n)); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(V(0.8, 0.8)); t.SetTextThickness(MM(0.12))
        t.SetPosition(V(row + (-1.6 if n <= 8 else 1.6), y)); fp.Add(t)
    def rect(layer, x0, y0, x1, y1, w=0.1):
        s = pcbnew.PCB_SHAPE(fp); s.SetShape(pcbnew.SHAPE_T_RECT); s.SetLayer(layer)
        s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1)); s.SetWidth(MM(w)); fp.Add(s)
    rect(pcbnew.F_Fab, 0.0, -18.8, 6.0, 18.8)          # zona de patas sobre la placa
    rect(pcbnew.F_Fab, -20.0, -20.13, 0.0, 20.13)      # cuerpo fuera de la placa
    rect(pcbnew.F_CrtYd, -0.3, -16.0, 6.7, 16.0, 0.05)
    rect(pcbnew.F_SilkS, 0.6, -16.4, 6.6, 16.4, 0.15)
    for txt, x, y, sz in (("OBD2", 3.5, -19.0, 1.0), ("16=+12V 7+15=K 4/5=GND", 8.5, -17.4, 0.8)):
        t = pcbnew.PCB_TEXT(fp); t.SetText(txt); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(V(sz, sz)); t.SetTextThickness(MM(0.12)); t.SetPosition(V(x, y)); fp.Add(t)
    return fp

# --------------------------------------------------------------------- armado
def build():
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_MinClearance = MM(0.15)
    ds.m_TrackMinWidth = MM(0.15)        # JLCPCB: 0,127 mm; Freerouting estrecha a 0,187 en los pines
    ds.m_ViasMinSize = MM(0.6); ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.2)   # las patas de la USB-C quedan a 0,25 del borde
    fps = {}
    for ref, lib, name, x, y, rot, val, *_ in P:
        if lib == "e36obd":
            fp = obd2_footprint(board)
        else:
            fp = pcbnew.FootprintLoad(FPLIB + "/" + lib + ".pretty", name)
            if fp is None: sys.exit("falta %s:%s" % (lib, name))
        fp.SetReference(ref); fp.SetValue(val)
        if ref == "J3":                      # SBU no se usa: sin esos pads pasa D+/D-
            for pad in list(fp.Pads()):
                if pad.GetNumber() in ("A8", "B8", "B1", "B4", "B9", "B12"): fp.Remove(pad)  # duplicados
        if ref == "U3":                      # vias termicas del pad central: JLC pide taladro >= 0,3
            for pad in fp.Pads():
                if pad.GetDrillSize().x and pad.GetDrillSize().x < MM(0.3):
                    pad.SetDrillSize(V(0.3, 0.3)); pad.SetSize(V(0.6, 0.6))
        board.Add(fp)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(OX + x, OY + y))
        fps[ref] = fp
    nets = {}
    for name in N:
        ni = pcbnew.NETINFO_ITEM(board, name); board.Add(ni); nets[name] = ni
    for name, pins in N.items():
        for spec in pins:
            ref, pn = spec.split(".", 1)
            found = [p for p in fps[ref].Pads() if p.GetNumber() == pn]
            if not found: sys.exit("no existe el pad %s" % spec)
            for p in found: p.SetNet(nets[name])
    # contorno
    cs = [(OX, OY), (OX + W, OY), (OX + W, OY + H), (OX, OY + H)]
    for a, b in zip(cs, cs[1:] + cs[:1]):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
    ds.SetAuxOrigin(V(OX, OY + H))       # origen de fabricacion: esquina inferior izquierda
    for fp in fps.values():              # pads SMD de GND: conexion solida al plano (sin alivios que se quedan cortos)
        for pad in fp.Pads():
            if pad.GetNetname() == "GND" and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                for meth in ("SetLocalZoneConnection", "SetZoneConnection"):
                    if hasattr(pad, meth): getattr(pad, meth)(pcbnew.ZONE_CONNECTION_FULL); break
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):   # antena del modulo: nada de cobre debajo ni al lado
        k = pcbnew.ZONE(board); k.SetLayer(layer); k.SetIsRuleArea(True)
        for meth, val in (("SetDoNotAllowZoneFills", True), ("SetDoNotAllowCopperPour", True), ("SetDoNotAllowTracks", True),
                          ("SetDoNotAllowVias", True), ("SetDoNotAllowPads", False), ("SetDoNotAllowFootprints", False)):
            if hasattr(k, meth): getattr(k, meth)(val)
        o = k.Outline(); o.NewOutline()
        for cx, cy in ((KEEPOUT[0], KEEPOUT[1]), (KEEPOUT[2], KEEPOUT[1]), (KEEPOUT[2], KEEPOUT[3]), (KEEPOUT[0], KEEPOUT[3])):
            o.Append(MM(OX + cx), MM(OY + cy))
        board.Add(k)
    gnd_zone(board, nets["GND"], pcbnew.B_Cu)   # el plano superior se agrega despues de rutear
    for fp in fps.values():
        fp.Reference().SetTextSize(V(0.8, 0.8)); fp.Reference().SetTextThickness(MM(0.12))
    netclasses(board)
    silk(board)
    return board, fps, nets

def gnd_zone(board, net, layer):
    cs = [(OX, OY), (OX + W, OY), (OX + W, OY + H), (OX, OY + H)]
    z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNet(net)
    z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    o = z.Outline(); o.NewOutline()
    for cx, cy in cs: o.Append(MM(cx), MM(cy))
    board.Add(z)
    return z

def silk(board):
    for txt, x, y, sz, rot in (
        ("E36 K-LINE  ESP32-S3 + L9637D   rev B", 24.0, 1.6, 1.0, 0),
        ("e36obd  2026-09", 24.0, 3.2, 0.8, 0),
        ("J2: EN IO0 TX0 RX0 GND 3V3", 81.5, 48.6, 0.8, 0),
        ("USB-C 5V", 66.5, 35.8, 0.8, 0),
        ("12V IN", 12.0, 39.6, 0.8, 0),
        ("3V3", 50.5, 40.0, 0.8, 0),
        ("K", 7.8, 28.0, 0.8, 0),
        ("J4 GND K +12", 10.0, 24.2, 0.7, 0),
        ("ANTENA", 60.0, 3.2, 0.8, 0),
    ):
        t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(V(sz, sz)); t.SetTextThickness(MM(0.12))
        t.SetPosition(V(OX + x, OY + y)); t.SetTextAngleDegrees(rot); board.Add(t)

def netclasses(board):
    """Anchos por clase; Freerouting los lee del DSN."""
    ds = board.GetDesignSettings()
    try:
        ns = ds.m_NetSettings
        dflt = ns.GetDefaultNetclass()
        dflt.SetTrackWidth(MM(0.25)); dflt.SetClearance(MM(0.2))
        dflt.SetViaDiameter(MM(0.7)); dflt.SetViaDrill(MM(0.35))
        for cname, width, clr, via, members in (("Power", 0.8, 0.2, 0.9, POWER), ("KLine", 0.5, 0.2, 0.9, KLINE),
                                                ("Mid", 0.4, 0.2, 0.7, MID), ("USB", 0.2, 0.15, 0.7, USB)):
            nc = pcbnew.NETCLASS(cname)
            nc.SetTrackWidth(MM(width)); nc.SetClearance(MM(clr))
            nc.SetViaDiameter(MM(via)); nc.SetViaDrill(MM(via / 2))
            ns.SetNetclass(cname, nc)
            for n in members: ns.SetNetclassPatternAssignment(n, cname)
        print("netclasses: ok")
    except Exception as exc:
        print("netclasses: NO se pudieron fijar por API:", exc)

def stitch(board, gnd, pitch=6.0, keep=0.6):
    """Vias de costura GND en una grilla, solo donde no molestan a nada."""
    import math
    segs, rects = [], []
    for t in board.GetTracks():
        s, e = t.GetStart(), t.GetEnd()
        segs.append((pcbnew.ToMM(s.x), pcbnew.ToMM(s.y), pcbnew.ToMM(e.x), pcbnew.ToMM(e.y), pcbnew.ToMM(t.GetWidth()) / 2))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            rects.append(tuple(pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())))
    def seg_dist(px, py, x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
    def rect_dist(px, py, l, t, r, b):
        return math.hypot(max(l - px, 0, px - r), max(t - py, 0, py - b))
    n = 0
    x = OX + 3.0
    while x < OX + W - 1.5:
        y = OY + 3.0
        while y < OY + H - 1.5:
            in_keepout = KEEPOUT[0] - 1 <= x - OX <= KEEPOUT[2] + 1 and KEEPOUT[1] - 1 <= y - OY <= KEEPOUT[3] + 1
            if not in_keepout and all(seg_dist(x, y, *sg[:4]) >= sg[4] + keep for sg in segs) and \
               all(rect_dist(x, y, *rc) >= keep for rc in rects):
                v = pcbnew.PCB_VIA(board); v.SetPosition(V(x, y)); v.SetWidth(MM(0.7)); v.SetDrill(MM(0.35))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(gnd); board.Add(v); n += 1
            y += pitch
        x += pitch
    print("vias de costura GND:", n)

def save_footprint_lib(fp):
    """Guarda la ficha OBD2 como libreria del proyecto para que KiCad la encuentre."""
    lib = os.path.join(HERE, "e36obd.pretty")
    os.makedirs(lib, exist_ok=True)
    try:
        io = pcbnew.PCB_IO_KICAD_SEXPR()
        io.FootprintSave(lib, fp)
        print("footprint guardado en", lib)
    except Exception as exc:
        print("no se pudo guardar la libreria de footprints:", exc)
    with open(os.path.join(HERE, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "e36obd")(type "KiCad")(uri "${KIPRJMOD}/e36obd.pretty")(options "")(descr "Ficha OBD2 macho acodada"))\n)\n')

def report(fps):
    for ref, pads in (("U1", ("1","3","4","5","6","7")), ("J1", ("1","7","15","16")),
                      ("U3", ("1","2","3","10","11","13","14","27","31","36","37","40")),
                      ("J2", ("1","6")), ("J3", ("A4","A6","A7","SH")), ("D1", ("1","2")), ("D2", ("1","2")),
                      ("C10", ("1","2")), ("C14", ("1","2")), ("SW1", ("1","2"))):
        out = []
        for p in fps[ref].Pads():
            if p.GetNumber() in pads:
                pos = p.GetPosition(); out.append("%s(%.2f,%.2f)" % (p.GetNumber(), pcbnew.ToMM(pos.x)-OX, pcbnew.ToMM(pos.y)-OY))
        print("  %-3s %s" % (ref, " ".join(sorted(set(out)))))

def route(board):
    dsn = OUT[:-10] + ".dsn"; ses = OUT[:-10] + ".ses"
    pcbnew.SaveBoard(OUT, board)
    if not pcbnew.ExportSpecctraDSN(board, dsn): sys.exit("fallo la exportacion DSN")
    jar = os.environ.get("FREEROUTING", "/tmp/fr/freerouting.jar")
    subprocess.run(["java", "-jar", jar, "-de", dsn, "-do", ses, "-mp", os.environ.get("PASSES", "40"), "-mt", "1"],
                   check=True, timeout=int(os.environ.get("FR_TIMEOUT", "420")))
    if not pcbnew.ImportSpecctraSES(board, ses): sys.exit("fallo la importacion SES")
    gnd = board.FindNet("GND")
    stitch(board, gnd)
    gnd_zone(board, gnd, pcbnew.F_Cu)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print("pistas: %d  vias: %d" % (sum(1 for t in board.GetTracks() if t.GetClass()=="PCB_TRACK"),
                                     sum(1 for t in board.GetTracks() if t.GetClass()=="PCB_VIA")))

if __name__ == "__main__":
    board, fps, nets = build()
    report(fps)
    if "--route" in sys.argv:
        route(board)
    else:
        gnd_zone(board, nets["GND"], pcbnew.F_Cu)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    save_footprint_lib(fps["J1"])
    pcbnew.SaveBoard(OUT, board)
    print("guardado", OUT)
