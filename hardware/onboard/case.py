"""Caja para la placa unica (hardware/onboard), dos piezas impresas.

  ~/Desktop/E36_OBD/.cadenv/bin/python hardware/onboard/case.py

Coordenadas: X = x de la placa, Y = -y de la placa (la antena queda en +Y, el USB en -Y),
Z hacia arriba con la cara interior del piso en Z = 0. Todas las medidas salen de gen_board.py
y del STEP del conector Macchina CCBDM20:

  · la pared izquierda (1,5 mm) se mete en el cuello de 2 mm del conector, entre su brida
    (adentro, 37,6 x 17,2, hasta 15,6 mm sobre la placa) y su cuerpo (afuera, 40,3 x 19,4);
  · la brida es lo que fija la altura interior: 17 mm sobre la placa;
  · la antena del modulo queda sobre la placa (zona sin cobre): la caja es un prisma liso;
  · cuatro M3 x 16 desde abajo, por los separadores y la placa, roscan en los postes de la tapa.

Genera case/base.step|stl, case/lid.step|stl (la tapa ya dada vuelta para imprimir),
case/assembly.step (con la placa y los volumenes de referencia) y case/preview.svg.
"""
import os, sys
from pathlib import Path
from build123d import (Align, Axis, Box, Compound, Cylinder, FontStyle, Pos, RectangleRounded, Rot, Text,
                       export_step, export_stl, extrude, fillet)

HERE = Path(__file__).resolve().parent
OUT = HERE / "case"; OUT.mkdir(exist_ok=True)
PIGTAIL = os.environ.get("CASE_PIGTAIL") == "1"   # sin ficha OBD2: pared cerrada con agujero para la cola al conector redondo
SUFFIX = "-pigtail" if PIGTAIL else ""

# ------------------------------------------------------------------- medidas
FLOOR, WALL, WALL_L, LID = 2.4, 2.4, 1.5, 2.4   # pared izquierda 1,5: entra en el cuello de 2 mm con 0,15 y 0,35 de juego
SO, PCB_T = 3.0, 1.6                     # separadores, espesor de placa
PCB_TOP = SO + PCB_T                     # 4.6
CLEAR_ABOVE = 17.0                       # brida del conector: 15,6 + 1,4
H_IN = PCB_TOP + CLEAR_ABOVE             # 21.6 = tope de pared = cara interior de la tapa
Z_TOP = H_IN + LID                       # 24.0
CLR = 0.6                                # placa - pared
BW, BH = 90.0, 50.0                      # placa
OX0 = -4.0 + 0.15                        # cara exterior: 0,15 detras del cuerpo del conector (X = -4,0)
IX0, IX1 = OX0 + WALL_L, BW + CLR        # interior en X: la brida (X -2..0) queda adentro
IY0, IY1 = -(BH + CLR), CLR              # interior en Y
OX1 = IX1 + WALL                         # exterior
OY0, OY1 = IY0 - WALL, IY1 + WALL
HOLES = [(10.0, -4.0), (54.5, -46.0), (86.5, -32.0), (4.5, -46.0)]   # de gen_board.py
BUTTONS = [(47.5, -4.0), (77.5, -33.0)]                               # SW1 RESET, SW2 BOOT
LEDS = [(24.0, -10.0), (83.0, -40.5)]                                 # LED1 PWR, LED2 STATUS
USB_X = 66.5
USB_MOUTH = -(BH + 1.6)                  # la boca de la ficha, 1,6 mm fuera del borde de la placa
USB_CZ = PCB_TOP + 3.16 / 2              # centro del blindaje (8,94 x 3,16) sobre la placa
# conector: cuello 33,6 x 14,2 centrado a 6,8 mm sobre la placa (STEP CCBDM20)
NECK_Y0, NECK_Y1 = -24.0 - 17.1, -24.0 + 17.1
NECK_Z0, NECK_Z1 = 4.0, PCB_TOP + 13.93 + 0.3

def B(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)
def RR(x0, x1, y0, y1, z0, z1, r):
    return extrude(Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * RectangleRounded(x1 - x0, y1 - y0, r), amount=z1 - z0)
def C(x, y, z0, z1, r):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(r, z1 - z0)

# ---------------------------------------------------------------------- base
def usb_opening(y0, y1, w=9.4, h=3.6):
    """Estadio de w x h (blindaje 8,94 x 3,16 + 0,45) que atraviesa la pared entre y0 e y1."""
    r = h / 2
    core = B(USB_X - w / 2 + r, USB_X + w / 2 - r, y0, y1, USB_CZ - r, USB_CZ + r)
    for x in (USB_X - w / 2 + r, USB_X + w / 2 - r):
        core += Pos(x, (y0 + y1) / 2, USB_CZ) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)
    return core

def make_base():
    outer = RR(OX0, OX1, OY0, OY1, -FLOOR, H_IN, 3.0)
    cavity = RR(IX0, IX1, IY0, IY1, 0, H_IN + 1, 1.5)
    base = outer - cavity
    if PIGTAIL:
        base -= Pos((OX0 + IX0) / 2, -24.0, 12.0) * Rot(0, 90, 0) * Cylinder(3.5, WALL_L + 0.6)   # pasacable 7 mm
    else:
        base -= B(OX0 - 0.1, IX0 + 0.1, NECK_Y0, NECK_Y1, NECK_Z0, H_IN + 1)      # muesca del conector
    # USB-C: la pared abraza el blindaje de la ficha y su boca queda a ras del fondo de un bisel
    base += B(USB_X - 8.0, USB_X + 8.0, USB_MOUTH, -BH - 0.3, 0.0, H_IN)          # pared local de 1,3 mm, a 0,3 de la placa
    base -= B(USB_X - 9.0, USB_X + 9.0, OY0 - 0.1, USB_MOUTH, 1.2, 11.2)           # bisel: el sobremoldeado entra hasta la boca
    base -= usb_opening(USB_MOUTH - 0.5, -BH - 0.1)                                  # abertura con la forma del blindaje
    base += B(USB_X - 10.5, USB_X + 10.5, IY0, IY0 + 1.2, 0.0, SO - 0.1)          # repisa bajo el borde de la placa
    for xi in range(12, 50, 5):                                                    # respiraderos
        base -= B(xi - 1.0, xi + 1.0, OY0 - 0.1, IY0 + 0.1, 10.0, 18.0)
        base -= B(xi - 1.0, xi + 1.0, IY1 - 0.1, OY1 + 0.1, 10.0, 18.0)
    for x, y in HOLES:                                                             # separadores y tornillos
        base += C(x, y, 0, SO, 3.5)
        base -= C(x, y, -FLOOR - 0.1, SO + 0.1, 1.7)
        base -= C(x, y, -FLOOR - 0.1, -FLOOR + 1.6, 3.2)                          # cabeza embutida
    for x in (24.0, 44.0):                                                         # ranuras para precinto
        base -= B(x, x + 3.0, -30.0, -18.0, -FLOOR - 0.1, 0.1)
    return base

# ----------------------------------------------------------------------- tapa
def make_lid():
    lid = RR(OX0, OX1, OY0, OY1, H_IN, Z_TOP, 3.0)
    lip_out = RR(IX0 + 0.3, IX1 - 0.3, IY0 + 0.3, IY1 - 0.3, H_IN - 2.0, H_IN, 1.2)
    lip_in = RR(IX0 + 1.5, IX1 - 1.5, IY0 + 1.5, IY1 - 1.5, H_IN - 2.1, H_IN + 0.1, 0.5)
    lid += lip_out - lip_in
    lid -= B(IX0 - 0.1, IX0 + 1.6, -43.5, -4.5, H_IN - 2.1, H_IN - 0.01)          # sin labio donde esta la brida
    if not PIGTAIL:
        lid += B(OX0 + 0.1, IX0 - 0.1, NECK_Y0 + 0.2, NECK_Y1 - 0.2, NECK_Z1 + 0.2, H_IN)  # lengueta que cierra la muesca
    for x, y in HOLES:
        lid += C(x, y, PCB_TOP, H_IN, 3.5)
        lid -= C(x, y, PCB_TOP - 0.1, PCB_TOP + 12.0, 1.3)                        # piloto M3 en plastico
    for x, y in BUTTONS:
        lid -= C(x, y, H_IN - 0.1, Z_TOP + 0.1, 3.0)
    for x, y in LEDS:
        lid -= C(x, y, H_IN - 0.1, Z_TOP + 0.1, 1.1)
    # =BMW= estilo tapa M50: campo rebajado 0,5 mm; nervios y letras quedan a ras de la tapa
    FX0, FX1, FY0, FY1, DEPTH = 4.0, 72.0, -35.0, -13.0, 0.5
    field = B(FX0, FX1, FY0, FY1, Z_TOP - DEPTH, Z_TOP + 0.2)
    font = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
    letters = None
    try:
        txt = Text("BMW", 13.0, font="Arial", font_style=FontStyle.BOLD,
                   font_path=str(font) if font.exists() else None, align=(Align.CENTER, Align.CENTER))
        letters = extrude(Pos(38.0, -24.0, Z_TOP - DEPTH - 0.1) * txt, amount=DEPTH + 0.4)
        lb = letters.bounding_box(); gap_x0, gap_x1 = lb.min.X - 3.0, lb.max.X + 3.0
    except Exception as exc:
        print("sin letras BMW:", exc); gap_x0, gap_x1 = 22.0, 54.0
    ribs = None
    for i in range(9):
        yi = -34.0 + 2.5 * i
        for x0, x1 in ((FX0, gap_x0), (gap_x1, FX1)):
            r = B(x0, x1, yi - 0.625, yi + 0.625, Z_TOP - DEPTH - 0.1, Z_TOP + 0.3)
            ribs = r if ribs is None else ribs + r
    cut = field - ribs
    if letters is not None: cut = cut - letters
    lid -= cut
    try:                                                                            # etiqueta chica, grabada
        small = Text("E36 K-LINE", 4.0, font="Arial", font_style=FontStyle.BOLD,
                     font_path=str(font) if font.exists() else None, align=(Align.MIN, Align.CENTER))
        lid -= extrude(Pos(6.0, -44.5, Z_TOP - 0.4) * small, amount=0.6)
    except Exception as exc:
        print("sin etiqueta:", exc)
    return lid

# -------------------------------------------------- volumenes de referencia
def envelope():
    """Placa, modulo, conector y lo mas alto de la placa. Nada de esto puede tocar la caja."""
    e = {
        "pcb": B(0, BW, -BH, 0, SO, PCB_TOP),
        "modulo": B(68.0, 86.0, -25.9, -0.3, PCB_TOP, PCB_TOP + 3.1),
        "brida": B(-2.0, 0.0, -42.8, -5.2, SO, PCB_TOP + 15.6),
        "cuello": B(-4.0, -2.0, -40.8, -7.2, PCB_TOP - 0.3, PCB_TOP + 13.93),
        "cuerpo": B(-20.0, -4.0, -44.13, -3.87, PCB_TOP - 1.95, PCB_TOP + 17.4),
        "usbc": usb_opening(USB_MOUTH, USB_MOUTH + 7.4, w=8.94, h=3.16),     # blindaje real: estadio 8,94 x 3,16
        "usbc_patas": B(62.0, 71.0, -BH + 1.05, -BH + 5.5, SO - 1.2, SO),
        "j4": B(7.1, 12.9, -21.95, -12.05, PCB_TOP, PCB_TOP + 7.0),
        "sw1": B(47.5 - 3.05, 47.5 + 3.05, -4.0 - 3.05, -4.0 + 3.05, PCB_TOP, PCB_TOP + 5.0),
        "sw2": B(77.5 - 3.05, 77.5 + 3.05, -33.0 - 3.05, -33.0 + 3.05, PCB_TOP, PCB_TOP + 5.0),
        "L1": B(40.3 - 3.05, 40.3 + 3.05, -43.05, -36.95, PCB_TOP, PCB_TOP + 4.5),
        "D1": B(13.35, 17.65, -46.6, -41.0, PCB_TOP, PCB_TOP + 2.5),
        "F1": B(8.3, 12.9, -43.15, -40.85, PCB_TOP, PCB_TOP + 1.0),
        "R1": B(7.55, 10.45, -35.25, -29.75, PCB_TOP, PCB_TOP + 0.7),
        "J1pads": B(1.2, 6.3, -39.05, -8.95, PCB_TOP, PCB_TOP + 0.1),
    }
    return e

def check(name, part, env):
    ok = part.is_valid and len(part.solids()) == 1
    print("%-5s valido=%s solidos=%d volumen=%.0f mm3  bbox %s" % (name, part.is_valid, len(part.solids()), part.volume,
          tuple(round(v, 1) for v in (part.bounding_box().min.X, part.bounding_box().min.Y, part.bounding_box().min.Z,
                                      part.bounding_box().max.X, part.bounding_box().max.Y, part.bounding_box().max.Z))))
    for k, v in env.items():
        inter = part & v
        vol = inter.volume if inter is not None else 0.0
        if vol > 0.01:
            ok = False; print("   CHOQUE %s con %s: %.2f mm3" % (name, k, vol))
    return ok

if __name__ == "__main__":
    base, lid, env = make_base(), make_lid(), envelope()
    if PIGTAIL:
        for k in ("brida", "cuello", "cuerpo"): env.pop(k)
    ok = check("base", base, env) & check("tapa", lid, env)
    print("exterior: %.1f x %.1f x %.1f mm (+16 de conector)" % (OX1 - OX0, OY1 - OY0, Z_TOP + FLOOR))
    print("interior sobre la placa: %.1f mm; tornillos M3 x 16 desde abajo; separadores %.0f mm" % (CLEAR_ABOVE, SO))
    export_step(base, str(OUT / ("base%s.step" % SUFFIX))); export_stl(base, str(OUT / ("base%s.stl" % SUFFIX)), tolerance=0.03)
    export_step(lid, str(OUT / ("lid%s.step" % SUFFIX)))
    lid_print = Rot(180, 0, 0) * lid
    lid_print = Pos(0, 0, -lid_print.bounding_box().min.Z) * lid_print
    export_stl(lid_print, str(OUT / ("lid%s.stl" % SUFFIX)), tolerance=0.03)
    export_step(Compound(children=[base, lid] + list(env.values())), str(OUT / ("assembly%s.step" % SUFFIX)))
    if PIGTAIL: sys.exit(0 if ok else 1)
    try:
        from build123d import ExportSVG
        view = Compound(children=[base, lid, env["cuerpo"]])
        vis, hid = view.project_to_viewport((-170, -260, 170))
        svg = ExportSVG(scale=2.2); svg.add_layer("v", line_weight=0.3)
        svg.add_shape(vis, layer="v"); svg.write(str(OUT / "preview.svg"))
        print("preview.svg listo")
    except Exception as exc:
        print("sin preview:", exc)
    print("OK" if ok else "HAY PROBLEMAS")
    sys.exit(0 if ok else 1)
