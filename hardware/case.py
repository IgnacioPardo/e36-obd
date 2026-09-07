"""Caja para el front-end K-Line del E36.

Dos piezas impresas, base y tapa, unidas por cuatro M3 que ademas sujetan la
placa: el tornillo entra por la tapa, baja por un poste hueco, atraviesa el
agujero de la placa y rosca en el separador del piso. Cuatro tornillos hacen
las dos cosas y el poste rigidiza la tapa.

Las medidas salen de la placa real, no de un supuesto: 80 x 50 mm con agujeros
M3 a 5 mm de cada esquina, verificado en kline-frontend.kicad_pcb con DRC
limpio.

Las salidas de cable son muescas en el borde superior de las paredes, no
agujeros cerrados. Dos razones: se imprime sin soportes, y el cable queda
prensado entre tapa y base, lo que hace de sujecion contra la vibracion.

  · pared izquierda -> mazo al conector OBD2 (J1, 5 hilos)
  · pared derecha   -> cable de 7 vias al ESP32 (J2)

La altura interior la fija C2, el electrolitico de 470 uF / 50 V: 10 mm de
diametro y hasta ~20 mm de alto segun fabricante, mas el modulo buck enchufado
en J3.

Uso:
  ./.cadenv/bin/python hardware/case.py     # imprime cotas
  python scripts/step hardware/case.py      # genera el STEP
"""

from build123d import (
    Align, Box, BuildPart, BuildSketch, Circle, Cylinder, Locations, Mode,
    Plane, RectangleRounded, export_step, extrude,
)

# ------------------------------------------------------------------ la placa
PCB_X, PCB_Y, PCB_T = 80.0, 50.0, 1.6
HOLE_INSET = 5.0
HOLE_XY = [
    (-PCB_X / 2 + HOLE_INSET, -PCB_Y / 2 + HOLE_INSET),
    (+PCB_X / 2 - HOLE_INSET, -PCB_Y / 2 + HOLE_INSET),
    (-PCB_X / 2 + HOLE_INSET, +PCB_Y / 2 - HOLE_INSET),
    (+PCB_X / 2 - HOLE_INSET, +PCB_Y / 2 - HOLE_INSET),
]

# --------------------------------------------------------------------- caja
CLEAR = 2.0
WALL = 2.5
FLOOR = 2.5
LID_T = 2.5
STANDOFF_H = 5.0
STANDOFF_OD = 7.0
STANDOFF_PILOT = 2.6          # M3 autorroscante en plastico
HEADROOM = 22.0               # sobre la cara superior de la placa
CORNER_R = 3.0

INNER_X = PCB_X + 2 * CLEAR
INNER_Y = PCB_Y + 2 * CLEAR
OUTER_X = INNER_X + 2 * WALL
OUTER_Y = INNER_Y + 2 * WALL
WALL_H = STANDOFF_H + PCB_T + HEADROOM
BOARD_TOP = FLOOR + STANDOFF_H + PCB_T

# ------------------------------------------------------------ salida cables
SLOT_W_LEFT = 12.0
SLOT_W_RIGHT = 14.0
SLOT_H = 7.0
SLOT_Y = 0.0

# ---------------------------------------------------------------------- tapa
LIP_T = 1.5
LIP_GAP = 0.35                # juego para que entre impresa
POST_OD = 6.0
POST_ID = 3.4                 # paso de M3
CBORE_D = 6.2
CBORE_H = 2.0


def base():
    """Bandeja: piso, paredes, separadores y muescas de cable."""
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            RectangleRounded(OUTER_X, OUTER_Y, CORNER_R)
        extrude(amount=FLOOR + WALL_H)

        with BuildSketch(Plane.XY.offset(FLOOR)):
            RectangleRounded(INNER_X, INNER_Y, max(0.5, CORNER_R - WALL))
        extrude(amount=WALL_H, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XY.offset(FLOOR)):
            with Locations(*HOLE_XY):
                Circle(STANDOFF_OD / 2)
        extrude(amount=STANDOFF_H)

        # piloto: entra en el separador y muerde el piso, sin perforarlo
        with BuildSketch(Plane.XY.offset(FLOOR + STANDOFF_H)):
            with Locations(*HOLE_XY):
                Circle(STANDOFF_PILOT / 2)
        extrude(amount=-(STANDOFF_H + FLOOR * 0.6), mode=Mode.SUBTRACT)

        top = FLOOR + WALL_H
        for x, w in ((-OUTER_X / 2, SLOT_W_LEFT), (OUTER_X / 2, SLOT_W_RIGHT)):
            with Locations((x, SLOT_Y, top - SLOT_H / 2)):
                Box(WALL * 4, w, SLOT_H, mode=Mode.SUBTRACT)
    return p.part


def lid():
    """Tapa con labio de encastre y postes que bajan a apoyar sobre la placa."""
    post_h = (FLOOR + WALL_H) - BOARD_TOP
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            RectangleRounded(OUTER_X, OUTER_Y, CORNER_R)
        extrude(amount=LID_T)

        with BuildSketch(Plane.XY.offset(LID_T)):
            RectangleRounded(INNER_X - 2 * LIP_GAP, INNER_Y - 2 * LIP_GAP,
                             max(0.5, CORNER_R - WALL))
        extrude(amount=LIP_T)

        with BuildSketch(Plane.XY.offset(LID_T)):
            with Locations(*HOLE_XY):
                Circle(POST_OD / 2)
        extrude(amount=post_h)

        with BuildSketch(Plane.XY):
            with Locations(*HOLE_XY):
                Circle(POST_ID / 2)
        extrude(amount=LID_T + post_h, mode=Mode.SUBTRACT)

        with BuildSketch(Plane.XY):
            with Locations(*HOLE_XY):
                Circle(CBORE_D / 2)
        extrude(amount=CBORE_H, mode=Mode.SUBTRACT)

        # las muescas de cable se comparten con la base
        for x, w in ((-OUTER_X / 2, SLOT_W_LEFT), (OUTER_X / 2, SLOT_W_RIGHT)):
            with Locations((x, SLOT_Y, LID_T + LIP_T / 2)):
                Box(WALL * 4, w, LIP_T * 2, mode=Mode.SUBTRACT)
    return p.part


def gen_step():
    """Punto de entrada para scripts/step: devuelve las dos piezas separadas."""
    b = base()
    t = lid()
    t.label = "tapa"
    b.label = "base"
    # la tapa se apoya al lado, para imprimir las dos de una
    t.locate(t.location * Plane.XY.location)
    return [b, t]


if __name__ == "__main__":
    b, t = base(), lid()
    print("placa       %.0f x %.0f x %.1f mm" % (PCB_X, PCB_Y, PCB_T))
    print("interior    %.0f x %.0f x %.1f mm" % (INNER_X, INNER_Y, WALL_H))
    print("exterior    %.0f x %.0f x %.1f mm"
          % (OUTER_X, OUTER_Y, FLOOR + WALL_H + LID_T))
    print("poste tapa  %.1f mm" % ((FLOOR + WALL_H) - BOARD_TOP))
    print("tornillos   4 x M3 x 30, autorroscantes en el separador")
    print()
    print("base  bbox  %s" % (b.bounding_box().size,))
    print("tapa  bbox  %s" % (t.bounding_box().size,))
    export_step(b, "hardware/case-base.step")
    export_step(t, "hardware/case-lid.step")
    print("\nexportado: hardware/case-base.step, hardware/case-lid.step")
