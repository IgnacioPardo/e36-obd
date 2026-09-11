"""Caja para la placa unica (hardware/onboard): base, tapa y placa-emblema, impresas.

  ~/Desktop/E36_OBD/.cadenv/bin/python hardware/onboard/case.py
  CASE_PIGTAIL=1 ~/Desktop/E36_OBD/.cadenv/bin/python hardware/onboard/case.py   # sin ficha OBD2, con pasacable

Coordenadas: X = x de la placa, Y = -y de la placa (la antena queda en +Y, el USB en -Y),
Z hacia arriba con la cara interior del piso en Z = 0. Todas las medidas salen de gen_board.py
y del STEP del conector Macchina CCBDM20:

  . la pared izquierda (1,5 mm) se mete en el cuello de 2 mm del conector, entre su brida
    (adentro, 37,6 x 17,2, hasta 15,6 mm sobre la placa) y su cuerpo (afuera, 40,3 x 19,4);
  . la brida es lo que fija la altura interior: 17 mm sobre la placa;
  . la antena del modulo queda sobre la placa (zona sin cobre): la caja es un prisma liso;
  . la USB-C atraviesa la pared por una abertura con la forma de su blindaje;
  . cuatro M3 x 16 desde abajo, por los separadores y la placa, roscan en los postes de la tapa.

Estetica: esquinas R6, chaflanes de 45 grados arriba y abajo, linea de sombra en la junta, tapa lisa
con el emblema =BMW= como pieza aparte (plata) con nervios y letras en relieve, a ras en la tapa,
LEDs por guias de luz de 3 mm, botones por agujero de clip, insertos M3 en los postes.

Genera case/base.step|stl, case/lid.step|stl (la tapa ya dada vuelta para imprimir),
case/badge.step|stl (emblema, se imprime como esta), case/assembly.step y las variantes -pigtail.
"""
import os, sys
from pathlib import Path
from build123d import (Align, Axis, Box, Compound, Cylinder, FontStyle, Plane, Polygon, Pos, RectangleRounded, Rot, Text,
                       chamfer, export_step, export_stl, extrude)

HERE = Path(__file__).resolve().parent
OUT = HERE / "case"; OUT.mkdir(exist_ok=True)
PIGTAIL = os.environ.get("CASE_PIGTAIL") == "1"
SUFFIX = "-pigtail" if PIGTAIL else ""
FONT = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")

# ------------------------------------------------------------------- medidas
FLOOR, WALL, WALL_L, LID = 2.4, 2.4, 1.5, 3.0   # tapa de 3: el emblema va embutido 1,6
SO, PCB_T = 3.0, 1.6
PCB_TOP = SO + PCB_T                     # 4.6
CLEAR_ABOVE = 17.0                       # brida del conector: 15,6 + 1,4
H_IN = PCB_TOP + CLEAR_ABOVE             # 21.6 = tope de pared = cara interior de la tapa
Z_TOP = H_IN + LID                       # 24.6
CLR = 0.6
BW, BH = 90.0, 50.0                      # placa
OX0 = -4.0 + 0.15                        # cara exterior: 0,15 detras del cuerpo del conector (X = -4,0)
IX0, IX1 = OX0 + WALL_L, BW + CLR
IY0, IY1 = -(BH + CLR), CLR
OX1 = IX1 + WALL
OY0, OY1 = IY0 - WALL, IY1 + WALL
R_OUT, R_IN = 6.0, 1.5                   # esquinas verticales (interior chico: la placa tiene esquinas vivas)
CH_TOP, CH_BOT = 2.0, 1.5                # chaflanes de 45 grados
POST_R, INSERT_R, INSERT_D = 3.75, 2.0, 5.5   # postes de la tapa con insertos M3 termofijados (agujero 4,0 x 5,5)
HOLES = [(10.0, -4.0), (54.5, -46.0), (86.5, -32.0), (4.5, -46.0)]   # de gen_board.py
BUTTONS = [(47.5, -4.0), (77.5, -39.0)]                               # SW1 RESET, SW2 BOOT
LEDS = [(24.0, -10.0), (86.0, -40.5)]                                 # LED1 PWR, LED2 STATUS
USB_X = 66.5
USB_MOUTH = -(BH + 1.6)                  # la boca de la ficha, 1,6 mm fuera del borde de la placa
USB_CZ = PCB_TOP + 3.16 / 2              # centro del blindaje (8,94 x 3,16) sobre la placa
NECK_Y0, NECK_Y1 = -24.0 - 17.1, -24.0 + 17.1        # cuello 33,6 x 14,2 (STEP CCBDM20)
NECK_Z0, NECK_Z1 = 4.0, PCB_TOP + 13.93 + 0.3
BX0, BX1, BY0, BY1, BT, BREL = 3.0, 88.0, -36.0, -14.0, 1.6, 0.8   # emblema 85 x 22 x 1,6; relieve 0,8
RIB_N, RIB_P, RIB_W = 13, 1.6, 0.8                                 # como la tapa M50: nervios finos, paso 1,6
PLAQUE_X = 35.0                                                    # placa BMW corrida hacia la ficha, nervios largos hacia el USB
BCLR = 0.15

def B(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)
def RR(x0, x1, y0, y1, z0, z1, r):
    return extrude(Pos((x0 + x1) / 2, (y0 + y1) / 2, z0) * RectangleRounded(x1 - x0, y1 - y0, r), amount=z1 - z0)
def C(x, y, z0, z1, r):
    return Pos(x, y, (z0 + z1) / 2) * Cylinder(r, z1 - z0)
def text(s, size, align=(Align.CENTER, Align.CENTER)):
    return Text(s, size, font="Arial", font_style=FontStyle.BOLD, font_path=str(FONT) if FONT.exists() else None, align=align)
def chamfer_outer(part, top, length):
    """Chaflan del contorno exterior de la cara superior (top=True) o inferior."""
    try:
        face = part.faces().sort_by(Axis.Z)[-1 if top else 0]
        return chamfer(face.outer_wire().edges(), length)
    except Exception as exc:
        print("sin chaflan:", exc); return part

def obd_body():
    """Cuerpo D del macho J1962 (40,3 abajo, 34,6 arriba, 19,35 de alto), 16 mm hacia -X."""
    zb, zt = PCB_TOP - 1.95, PCB_TOP + 17.4
    wb, wt, cy = 40.26 / 2, 34.6 / 2, -24.0
    prof = Plane.YZ * Polygon((cy - wb, zb), (cy + wb, zb), (cy + wt, zt), (cy - wt, zt), align=None)
    return Pos(-4.0, 0, 0) * extrude(prof, amount=-16.0)      # normal +X: amount negativo = hacia afuera

def usb_opening(y0, y1, w=9.4, h=3.6):
    """Estadio de w x h (blindaje 8,94 x 3,16 + 0,45) que atraviesa la pared entre y0 e y1."""
    r = h / 2
    core = B(USB_X - w / 2 + r, USB_X + w / 2 - r, y0, y1, USB_CZ - r, USB_CZ + r)
    for x in (USB_X - w / 2 + r, USB_X + w / 2 - r):
        core += Pos(x, (y0 + y1) / 2, USB_CZ) * Rot(90, 0, 0) * Cylinder(r, y1 - y0)
    return core

# ---------------------------------------------------------------------- base
def make_base():
    base = RR(OX0, OX1, OY0, OY1, -FLOOR, H_IN, R_OUT)
    base = chamfer_outer(base, False, CH_BOT)
    base -= RR(IX0, IX1, IY0, IY1, 0, H_IN + 1, R_IN)
    # linea de sombra en la junta: el borde superior exterior retrocede 0,5 mm en los ultimos 0,8
    base -= RR(OX0, OX1, OY0, OY1, H_IN - 0.8, H_IN + 0.1, R_OUT) - RR(OX0 + 0.5, OX1 - 0.5, OY0 + 0.5, OY1 - 0.5, H_IN - 0.9, H_IN + 0.2, R_OUT - 0.5)
    if PIGTAIL:
        base -= Pos((OX0 + IX0) / 2, -24.0, 12.0) * Rot(0, 90, 0) * Cylinder(3.5, WALL_L + 0.6)   # pasacable 7 mm
    else:
        base -= B(OX0 - 0.1, IX0 + 0.1, NECK_Y0, NECK_Y1, NECK_Z0, H_IN + 1)      # muesca del conector
    # USB-C: la pared abraza el blindaje de la ficha y su boca queda a ras del fondo de un bisel
    base += B(USB_X - 8.0, USB_X + 8.0, USB_MOUTH, -BH - 0.3, 0.0, H_IN)          # pared local de 1,3 mm, a 0,3 de la placa
    base -= B(USB_X - 9.0, USB_X + 9.0, OY0 - 0.1, USB_MOUTH, 1.2, 11.2)           # bisel: el sobremoldeado entra hasta la boca
    base -= usb_opening(USB_MOUTH - 0.5, -BH - 0.1)                                  # abertura con la forma del blindaje
    base += B(USB_X - 10.5, USB_X + 10.5, IY0, IY0 + 1.2, 0.0, SO - 0.1)          # repisa bajo el borde de la placa
    for xi in range(14, 45, 5):                                                    # 7 respiraderos por lado
        base -= B(xi - 1.0, xi + 1.0, OY0 - 0.1, IY0 + 0.1, 10.0, 18.0)
        base -= B(xi - 1.0, xi + 1.0, IY1 - 0.1, OY1 + 0.1, 10.0, 18.0)
    for x, y in HOLES:                                                             # separadores y tornillos
        base += C(x, y, 0, SO, 3.5)
        base -= C(x, y, -FLOOR - 0.1, SO + 0.1, 1.7)
        base -= C(x, y, -FLOOR - 0.1, -FLOOR + 1.6, 3.2)                          # cabeza embutida
    for x in (24.0, 44.0):                                                         # ranuras para precinto
        base -= B(x, x + 3.0, -30.0, -18.0, -FLOOR - 0.1, 0.1)
    try:                                                                           # grabado en el piso (se lee desde abajo)
        for s, y in (("E36 K-LINE  rev B", -20.0), ("OBD2: 16 +12V   7+15 K   4/5 GND", -28.0)):
            base -= extrude(Pos(45.0, y, -FLOOR - 0.1) * Rot(0, 180, 0) * text(s, 4.0), amount=-0.5)
    except Exception as exc:
        print("sin grabado en el piso:", exc)
    return base

# ----------------------------------------------------------------------- tapa
def make_lid():
    lid = RR(OX0, OX1, OY0, OY1, H_IN, Z_TOP, R_OUT)
    lid = chamfer_outer(lid, True, CH_TOP)
    lip_out = RR(IX0 + 0.3, IX1 - 0.3, IY0 + 0.3, IY1 - 0.3, H_IN - 2.0, H_IN, 1.2)
    lip_in = RR(IX0 + 1.5, IX1 - 1.5, IY0 + 1.5, IY1 - 1.5, H_IN - 2.1, H_IN + 0.1, 0.5)
    lid += lip_out - lip_in
    lid -= B(IX0 - 0.1, IX0 + 1.6, -43.5, -4.5, H_IN - 2.1, H_IN - 0.01)          # sin labio donde esta la brida
    if not PIGTAIL:
        lid += B(OX0 + 0.1, IX0 - 0.1, NECK_Y0 + 0.2, NECK_Y1 - 0.2, NECK_Z1 + 0.2, H_IN)  # lengueta que cierra la muesca
    for x, y in HOLES:
        lid += C(x, y, PCB_TOP, H_IN, POST_R)
        lid -= C(x, y, PCB_TOP - 0.1, PCB_TOP + INSERT_D, INSERT_R)                # inserto M3 termofijado
    for x, y in BUTTONS:                                                           # RESET / BOOT con un clip
        lid -= C(x, y, H_IN - 0.1, Z_TOP + 0.1, 1.0)
    for x, y in LEDS:                                                              # guia de luz de 3 mm, tope a 0,5 de la cara
        lid -= C(x, y, H_IN - 0.1, Z_TOP - 0.5, 1.55)
        lid -= C(x, y, Z_TOP - 0.6, Z_TOP + 0.1, 1.2)
    lid -= B(BX0 - BCLR, BX1 + BCLR, BY0 - BCLR, BY1 + BCLR, Z_TOP - BT, Z_TOP + 0.1)   # cajeado del emblema, a ras
    try:                                                                            # etiqueta chica, grabada
        lid -= extrude(Pos(6.0, -44.5, Z_TOP - 0.4) * text("E36 K-LINE", 4.0, (Align.MIN, Align.CENTER)), amount=0.6)
    except Exception as exc:
        print("sin etiqueta:", exc)
    return lid

# -------------------------------------------------------------------- emblema
def make_badge():
    """Placa =BMW= de 85 x 22 x 1,6: campo negro, 13 nervios finos y letras en relieve de 0,8 (plata por cambio de filamento en Z=1,6)."""
    z0, z1 = Z_TOP - BT, Z_TOP
    badge = B(BX0, BX1, BY0, BY1, z0, z1)
    letters = None
    yc = (BY0 + BY1) / 2
    try:
        letters = extrude(Pos(PLAQUE_X, yc, z1 - 0.01) * text("BMW", 13.0), amount=BREL + 0.01)
        lb = letters.bounding_box()
        gx0, gx1, gy0, gy1 = lb.min.X - 2.5, lb.max.X + 2.5, lb.min.Y - 1.4, lb.max.Y + 1.4   # placa de las letras
    except Exception as exc:
        print("sin letras BMW:", exc); gx0, gx1, gy0, gy1 = PLAQUE_X - 18.0, PLAQUE_X + 18.0, yc - 6.0, yc + 6.0
    for i in range(RIB_N):
        yi = yc + (i - (RIB_N - 1) / 2) * RIB_P
        if yi + RIB_W / 2 > gy0 + 0.05 and yi - RIB_W / 2 < gy1 - 0.05:   # nervio a la altura de la placa: se interrumpe
            spans = ((BX0 + 1.5, gx0), (gx1, BX1 - 1.5))
        else:                                                             # arriba y abajo de BMW siguen enteros
            spans = ((BX0 + 1.5, BX1 - 1.5),)
        for x0, x1 in spans:
            badge += B(x0, x1, yi - RIB_W / 2, yi + RIB_W / 2, z1 - 0.01, z1 + BREL)
    if letters is not None: badge += letters
    return badge

# -------------------------------------------------- volumenes de referencia
def envelope():
    """Placa, modulo, conector y lo mas alto de la placa. Nada de esto puede tocar la caja."""
    return {
        "pcb": B(0, BW, -BH, 0, SO, PCB_TOP),
        "modulo": B(68.0, 86.0, -25.9, -0.3, PCB_TOP, PCB_TOP + 3.1),
        "brida": B(-2.0, 0.0, -42.8, -5.2, SO, PCB_TOP + 15.6),
        "cuello": B(-4.0, -2.0, -40.8, -7.2, PCB_TOP - 0.3, PCB_TOP + 13.93),
        "cuerpo": obd_body(),
        "usbc": usb_opening(USB_MOUTH, USB_MOUTH + 7.4, w=8.94, h=3.16),
        "usbc_patas": B(62.0, 71.0, -BH + 1.05, -BH + 5.5, SO - 1.2, SO),
        "j4": B(7.1, 12.9, -21.95, -12.05, PCB_TOP, PCB_TOP + 7.0),
        "sw1": B(47.5 - 3.05, 47.5 + 3.05, -4.0 - 3.05, -4.0 + 3.05, PCB_TOP, PCB_TOP + 5.0),
        "sw2": B(77.5 - 3.05, 77.5 + 3.05, -39.0 - 3.05, -39.0 + 3.05, PCB_TOP, PCB_TOP + 5.0),
        "L1": B(40.3 - 3.05, 40.3 + 3.05, -43.05, -36.95, PCB_TOP, PCB_TOP + 4.5),
        "D1": B(13.35, 17.65, -46.6, -41.0, PCB_TOP, PCB_TOP + 2.5),
        "F1": B(8.3, 12.9, -43.15, -40.85, PCB_TOP, PCB_TOP + 1.0),
        "R1": B(7.55, 10.45, -35.25, -29.75, PCB_TOP, PCB_TOP + 0.7),
        "J1pads": B(1.2, 6.3, -39.05, -8.95, PCB_TOP, PCB_TOP + 0.1),
    }

def check(name, part, env):
    ok = part.is_valid and len(part.solids()) == 1
    bb = part.bounding_box()
    print("%-7s valido=%s solidos=%d volumen=%.0f mm3  bbox (%.1f,%.1f,%.1f)-(%.1f,%.1f,%.1f)" % (
        name, part.is_valid, len(part.solids()), part.volume, bb.min.X, bb.min.Y, bb.min.Z, bb.max.X, bb.max.Y, bb.max.Z))
    for k, v in env.items():
        inter = part & v
        vol = inter.volume if inter is not None else 0.0
        if vol > 0.01:
            ok = False; print("   CHOQUE %s con %s: %.2f mm3" % (name, k, vol))
    return ok

if __name__ == "__main__":
    base, lid, badge, env = make_base(), make_lid(), make_badge(), envelope()
    if PIGTAIL:
        for k in ("brida", "cuello", "cuerpo"): env.pop(k)
    ok = check("base", base, env) & check("tapa", lid, env) & check("emblema", badge, env)
    inter = lid & badge
    if inter is not None and inter.volume > 0.01:
        ok = False; print("   CHOQUE tapa con emblema: %.2f" % inter.volume)
    print("exterior: %.1f x %.1f x %.1f mm (+16 de conector); emblema %.0f x %.0f, relieve %.1f" %
          (OX1 - OX0, OY1 - OY0, Z_TOP + FLOOR, BX1 - BX0, BY1 - BY0, BREL))
    print("interior sobre la placa: %.1f mm; tornillos M3 x 12 desde abajo a insertos en la tapa; separadores %.0f mm" % (CLEAR_ABOVE, SO))
    export_step(base, str(OUT / ("base%s.step" % SUFFIX))); export_stl(base, str(OUT / ("base%s.stl" % SUFFIX)), tolerance=0.03)
    export_step(lid, str(OUT / ("lid%s.step" % SUFFIX)))
    lid_print = Rot(180, 0, 0) * lid
    lid_print = Pos(0, 0, -lid_print.bounding_box().min.Z) * lid_print
    export_stl(lid_print, str(OUT / ("lid%s.stl" % SUFFIX)), tolerance=0.03)
    export_step(Compound(children=[base, lid, badge] + list(env.values())), str(OUT / ("assembly%s.step" % SUFFIX)))
    if not PIGTAIL:
        try: export_step(badge, str(OUT / "badge.step"))
        except Exception as exc: print("badge.step no se pudo escribir (queda el STL):", exc)
        export_stl(Pos(0, 0, -badge.bounding_box().min.Z) * badge, str(OUT / "badge.stl"), tolerance=0.02)
        export_stl(lid, str(OUT / "_lid-assembly.stl"), tolerance=0.03); export_stl(base, str(OUT / "_base-assembly.stl"), tolerance=0.03)
        export_stl(badge, str(OUT / "_badge-assembly.stl"), tolerance=0.02)
        plate = badge & B(BX0 - 1, BX1 + 1, BY0 - 1, BY1 + 1, Z_TOP - BT - 1, Z_TOP)
        relief = badge & B(BX0 - 1, BX1 + 1, BY0 - 1, BY1 + 1, Z_TOP, Z_TOP + BREL + 1)
        export_stl(plate, str(OUT / "_badge-plate.stl"), tolerance=0.02); export_stl(relief, str(OUT / "_badge-relief.stl"), tolerance=0.02)
        export_stl(Compound(children=[env["brida"], env["cuello"], env["cuerpo"]]), str(OUT / "_connector-ref.stl"), tolerance=0.05)
    print("OK" if ok else "HAY PROBLEMAS")
    sys.exit(0 if ok else 1)
