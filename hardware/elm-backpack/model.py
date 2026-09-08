"""Parametric ELM backpack, mm. Run with Python + build123d 0.11.1.

python model.py [--parameters parameters.json] [--out exports]

Dimensions are provisional; see PLAN.md. Printable parts are exported in bed
orientation. The STEP assembly and scene.json preserve assembly coordinates.
Electronics, soft pads, wiring envelopes and ELM are reference geometry only.
"""
import argparse
import json
import math
from pathlib import Path

from build123d import (
    Align, Box, Color, Compound, Cylinder, FontStyle, Plane, Polygon, Pos, RectangleRounded,
    Rot, Text, export_step, export_stl, extrude,
)

HERE = Path(__file__).resolve().parent


def box(w, l, h, x=0, y=0, z=0):
    return Pos(x, y, z) * Box(w, l, h, align=(Align.CENTER, Align.CENTER, Align.MIN))


def cyl(r, h, x=0, y=0, z=0):
    return Pos(x, y, z) * Cylinder(r, h, align=(Align.CENTER, Align.CENTER, Align.MIN))


def rounded(w, l, h, r, x=0, y=0, z=0):
    return Pos(x, y, z) * extrude(RectangleRounded(w, l, r), amount=h)


def clipped(w, l, h, c, x=0, y=0, z=0):
    """Square shoulders with small straight corner cuts, like a moulded module."""
    outline = Polygon((-w/2+c,-l/2), (w/2-c,-l/2), (w/2,-l/2+c),
        (w/2,l/2-c), (w/2-c,l/2), (-w/2+c,l/2),
        (-w/2,l/2-c), (-w/2,-l/2+c), align=None)
    return Pos(x,y,z) * extrude(outline, amount=h)


def lettering(value, size):
    font_path = Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')
    return Text(value, size, font='Arial', font_style=FontStyle.BOLD,
                font_path=font_path if font_path.exists() else None,
                align=(Align.CENTER, Align.CENTER))


def volume(shape):
    return sum(s.volume for s in shape.solids()) if shape is not None else 0.0


def design(p):
    w, l, h, f, wall = (p[k] for k in
                         ('case_width', 'case_length', 'base_height', 'floor', 'wall'))
    iw, il = w - 2 * wall, l - 2 * wall
    r = p['corner_radius']
    inline = p.get('layout') == 'inline'
    m50 = p.get('exterior_style') == 'm50'
    outer = (lambda height, z=0: clipped(w,l,height,p['outer_corner_clip'],z=z)) if m50 else (
        lambda height, z=0: rounded(w,l,height,r,z=z))
    bx, by, bw, bl = (p[k] for k in ('buck_x', 'buck_y', 'buck_width', 'buck_length'))
    ex, ey, ew, el = (p[k] for k in ('esp_x', 'esp_y', 'esp_width', 'esp_length'))
    tail_usb = p.get('esp_usb_end', 'front') == 'tail'
    if tail_usb:
        ey = -ey  # Construct in the original orientation, then rotate all ESP features.
    def E(shape):
        return Pos(ex,0,0)*Rot(Z=180)*Pos(-ex,0,0)*shape if tail_usb else shape
    usb_overhang = p.get('esp_usb_overhang', 0)
    esp_front = ey-el/2+usb_overhang
    esp_body_y = ey+(usb_overhang-p['esp_antenna_overhang'])/2
    bt = p['pcb_thickness']
    soldered = p.get('esp_connection_mode', 'headers') == 'soldered'
    bz, ez = f + p['buck_under_board'], f + p['esp_under_board']
    kt = p['keeper_thickness']
    kz = bz + bt + p['keeper_gap']
    screw_inset = 5 if inline else 4
    screw_xy = [(x, y) for x in (-w / 2 + screw_inset, w / 2 - screw_inset)
                for y in (-l / 2 + 5.4, l / 2 - 5.4)]
    clamps = [(side, bx + side * (bw / 2 + 3.7), by + offset * bl)
              for side in (-1, 1)
              for offset in (-p['buck_clamp_fraction'], p['buck_clamp_fraction'])]

    base = outer(h) - rounded(iw, il, h + 1, r - wall, z=f)
    # Full-height bosses fuse into the sidewalls; blind pilots leave a floor.
    post_top = h-7.8 if inline else h
    for x, y in screw_xy:
        base += cyl(3.6, post_top - f, x, y, f)
    # Buck pillars sit outside the PCB, with low arms carrying its bare edges.
    support_pads = []
    for side, x, y in clamps:
        base += cyl(3.2, kz - f, x, y, f)
        inner_x = bx + side * (bw / 2 - 0.1)
        arm_x = (inner_x + x) / 2
        support_h = bz - p['support_pad_thickness'] - f
        base += box(abs(x - inner_x) + 1.8, 6.4, support_h, arm_x, y, f)
        support_pads.append(box(1.0, 5, p['support_pad_thickness'],
                                bx + side * (bw / 2 - 0.5), y,
                                bz - p['support_pad_thickness']))
    for y in (by - bl / 2 - 1.35, by + bl / 2 + 1.35):
        base += box(2, 2, bz + bt - f, bx + 0.5, y, f)

    # Central pads avoid the two pin/solder rows in either wiring profile.
    for off in p['esp_support_y_offsets']:
        y = ey + off
        base += E(box(14, 6, ez - f - p['support_pad_thickness'], ex, y, f))
        support_pads.append(E(box(14, 6, p['support_pad_thickness'], ex, y,
                                ez - p['support_pad_thickness'])))
    for side in (-1, 1):
        for off in (-19, 19):
            base += E(box(1.8, 5, ez + bt - f,
                        ex + side * (ew / 2 + 1.35), ey + off, f))
        # Stops lie beside the antenna, not on it or across the USB mouths.
        for y in (esp_front - 1.3,
                  ey + el / 2 - p['esp_antenna_overhang'] + 1.35):
            base += E(box(2, 2, ez + bt - f, ex + side * (ew / 2 - 1.7), y, f))

    # Small bridge anchor: tie threads sideways below the insulated wire bundle.
    anchor_y = p.get('wire_anchor_y',p['wire_entry_y'] - p['wire_entry_length'] / 2 - 5)
    aw = p.get('wire_anchor_width', 14)
    base += rounded(aw, 6, 5, 1, x=p['wire_anchor_x'], y=anchor_y, z=f)
    base -= box(aw+2, 3, 2, x=p['wire_anchor_x'], y=anchor_y, z=f + 1)
    base -= rounded(p['wire_entry_width'], p['wire_entry_length'], f + 2, 3,
                    p['wire_entry_x'], p['wire_entry_y'], -1)
    for x in (ex - ew / 2 - 3, ex + ew / 2 + 3):
        base -= E(rounded(2, 4, f + 2, 0.6, x, ey + p['esp_tie_y_offset'], -1))
    if soldered:
        # Low shared window clears both plug overmolds. Use local support under
        # this 32 mm roof; two overlapping arches would create an unsupported island.
        base -= E(box(p['usb_notch_width'], wall*4, 8.5,
                      ex, -l/2, p['usb_notch_bottom']))
    else:
        # Header profile: seam notch avoids a 32 mm bridge.
        base -= E(box(p['usb_notch_width'], wall * 4, h + 1,
                    ex, -l / 2, p['usb_notch_bottom']))
    for x, y in screw_xy:
        if inline:
            base -= cyl(p['clearance_diameter']/2,post_top+2,x,y,-1)
            base -= cyl(3.15,h-post_top+1,x,y,post_top)
        else:
            base -= cyl(p['pilot_diameter'] / 2, 10.6, x, y, h - 9.6)
    for side, x, y in clamps:
        base -= cyl(p['pilot_diameter'] / 2, kz - f - 0.8 + 1,
                    x, y, f + 0.8)
    if inline:
        for side in (-1,1):
            for y in p['side_vent_y']:
                base -= rounded(8,2,8,0.8,side*w/2,y,h-10)
    elif p.get('vent_layout') == 'side_banks':
        # Vertical side vents leave the lid plain. Keep all openings clear of
        # the strap lanes, corner screw bosses, and the top 2 mm locating rim.
        for side in (-1,1):
            for y in (-43,-39,-21,-17,-13,-9,-5,-1,3,23,27,31,35,39,43):
                base -= rounded(8,2,12,0.8,side*w/2,y,14)
    else:
        for y in (-18, -13, -8, -3, 27, 32, 37):
            base -= rounded(8, 2.4, 8, 1.1, -w / 2, y, 18)
    # Belt lanes are external, leaving the internal wiring unobstructed.
    if inline:
        # Recess the top of the floor so the two mounting straps sit flush
        # below the buck. An extra rear pair accepts a separate support tie.
        for y in p['strap_y']+[p['rear_anchor_y']]:
            base -= box(2*p['strap_slot_x']+2.4,12,1.01,y=y,z=f-1)
            for x in (-p['strap_slot_x'],p['strap_slot_x']):
                base -= rounded(2.4,12,f+2,0.6,x,y,-1)
    else:
        for y in p['strap_y']:
            d = p['strap_groove_depth']
            for side in (-1, 1):
                base -= box(d + 1, p['strap_lane_width'], h + 2,
                            side * (w / 2 + (1 - d) / 2), y, -1)

    if m50 and p['side_panel_depth'] > 0:
        # Shallow moulded-looking panels, entirely outside the packaging space.
        d = p['side_panel_depth']
        for side in (-1,1):
            for y, length in ((-44,12),(-9,26),(33,26)):
                base -= Pos(side*(w/2-d),y,14) * Rot(Y=90*side) * clipped(12,length,d+0.02,1.2)
        base -= Pos(0,-l/2+d,14) * Rot(X=90) * clipped(68,14,d+0.02,1.5)
        if tail_usb:
            base -= Pos(ex,l/2-d,p['usb_notch_bottom']+4.25) * Rot(X=-90) * clipped(40,12.5,d+0.02,1)

    # Lid generated assembled, then inverted for printing.
    lid = outer(p['lid_thickness'], z=h)
    lip_w = iw - 2 * p['lip_clearance']
    lip_l = il - 2 * p['lip_clearance']
    lip = rounded(lip_w, lip_l, p['lip_depth'], r - wall,
                  z=h - p['lip_depth'])
    lip -= rounded(lip_w - 2 * p['lip_thickness'],
                   lip_l - 2 * p['lip_thickness'], p['lip_depth'] + 2,
                   max(0.5, r - wall - p['lip_thickness']),
                   z=h - p['lip_depth'] - 1)
    for x, y in screw_xy:
        lip -= cyl(4.1, 5, x, y, h - 3)
    if not soldered:
        lip -= E(box(p['usb_notch_width'] + 0.8, wall * 4, 5, ex, -l / 2, h - 3))
    lid += lip
    for x, y in screw_xy:
        if inline:
            lid += cyl(2.8,7.5,x,y,h-7.5)
            lid -= cyl(p['pilot_diameter']/2,6.1,x,y,h-7.6)
        else:
            lid -= cyl(p['clearance_diameter'] / 2, 8, x, y, h - 3)
    if m50 and p.get('vent_layout') != 'side_banks':
        # Split slot bank echoes the parallel ribs, with more open area than B.
        for y in (24,28,32,36,40):
            for x in (-17,17):
                lid -= rounded(28,1.8,8,0.8,x,y,h-3)
    elif not m50:
        for y in (-19, -14, -9, -4, 23, 28, 33):
            lid -= rounded(22, 2.6, 8, 1.25, bx, y, h - 3)
    if not inline:
        for y in p['strap_y']:
            lid -= box(w + 2, p['strap_lane_width'], 2, y=y,
                       z=h + p['lid_thickness'] - p['strap_groove_depth'])

    finish_refs = []
    if m50:
        top, depth, cy = h+p['lid_thickness'], p['lid_relief_depth'], 0 if inline else -9
        motif_length = p.get('motif_length',68)
        rib_length = motif_length-4
        def M(shape):
            return Rot(Z=-90)*shape if inline else shape
        assert 0 < depth <= p['lid_thickness']-2+1e-6
        # Recess the field instead of raising the whole lid: ribs and lettering
        # remain on the bed plane when inverted. No extra height or backing part.
        lid -= M(clipped(motif_length,25,depth+0.02,2,y=cy,z=top-depth))
        for row in range(-4,5):
            half_span=(rib_length-34.6)/2
            mid=17.3+half_span/2
            spans = ((0,rib_length),) if abs(row)>2 else ((-mid,half_span),(mid,half_span))
            for x, width in spans:
                y=cy+row*2.5
                lid += M(clipped(width,1.25,depth+0.02,0.3,x,y,top-depth-0.02))
                finish_refs.append(('REF optional silver rib paint',
                    M(clipped(width,1.25,0.012,0.3,x,y,top+0.006)),'#b9b9b2','lid_finish'))
        mark=lettering('BMW',14)
        mark=Pos(0,cy,0)*Rot(Z=180)*mark.scale(30/mark.bounding_box().size.X)
        lid += M(Pos(0,0,top-depth-0.02)*extrude(mark,amount=depth+0.02))
        finish_refs.append(('REF optional silver lettering paint',
            M(Pos(0,0,top+0.006)*extrude(mark,amount=0.012)),'#b9b9b2','lid_finish'))
        # Open the spaces between the short rib ends above the buck and ESP.
        # These give direct upward ventilation beneath the styling field.
        for row in range(-4,4):
            for x in ((-60,-44,-28,28,44,60) if inline else (-24.65,24.65)):
                lid -= M(clipped(12,1.25,8,0.2,x,cy+(row+0.5)*2.5,h-3))
        if p.get('lid_caption','E36'):
            caption=Pos(0,-44,top-depth)*Rot(Z=180)*lettering(p.get('lid_caption','E36'),3.8)
            lid -= extrude(caption,amount=depth+0.02)

    keeper = cyl(3.2, kt) + box(4.7, 6.4, kt, -2.35)
    keeper -= cyl(p['clearance_diameter'] / 2, kt + 2, z=-1)
    keepers = [Pos(x, y, kz) * Rot(Z=180 if side < 0 else 0) * keeper
               for side, x, y in clamps]

    # Cheap pocket gauge: one connected solid with two board outlines and holes.
    gauge = None
    for cx, width, length in ((-19, bw, bl), (19, ew, el)):
        part = rounded(width + 5, length + 5, 2.4, 2, cx)
        part -= rounded(width + 0.6, length + 0.6, 4, 0.3, cx, z=-1)
        gauge = part if gauge is None else gauge + part
    gauge += box(74, 8, 2.4, y=max(bl, el) / 2 + 3)
    for x, dia in ((-8, p['pilot_diameter']), (8, p['clearance_diameter'])):
        gauge += cyl(3.7, 7, x, max(bl, el) / 2 + 3)
        gauge -= cyl(dia / 2, 9, x, max(bl, el) / 2 + 3, -1)

    refs = finish_refs
    def ref(name, shape, color, group='electronics'):
        refs.append((name, shape, color, group))
    def esp_ref(name, shape, color, group='electronics'):
        ref(name, E(shape), color, group)
    # Photo-derived coarse component models. Geometry is for packaging only.
    ref('REF buck PCB', box(bw, bl, bt, bx, by, bz), '#175386')
    z = bz + bt
    ref('REF buck input DC jack', box(10, 13, 11, bx - 7, by + bl / 2 - 6, z), '#1c2229')
    for name, y in (('input', by + bl / 2 - 4), ('output', by - bl / 2 + 4)):
        ref('REF buck ' + name + ' terminal', box(10, 8, 10, bx + 7, y, z), '#188ead')
        for x in (bx + 4.5, bx + 9.5):
            ref('REF terminal screw', cyl(1.7, 0.6, x, y, z + 10), '#b8bfc2')
    ref('REF buck input capacitor', cyl(5, p['buck_top_allowance'], bx + 7, by + 17, z), '#babdb9')
    ref('REF buck output capacitor', cyl(4.5, 12, bx + 7, by - 19, z), '#b5b9b8')
    ref('REF buck inductor', rounded(13, 13, 9, 1, bx - 6, by - 11, z), '#899395')
    ref('REF buck controller', box(6, 8, 2.2, bx + 5, by + 3, z), '#20252c')
    ref('REF buck USB C', box(9, 7, 3.5, bx - 6.5, by - bl / 2 + 2.5, z), '#bac3c8')
    # Main PCB excludes the narrow antenna protrusion.
    body_l = el - p['esp_antenna_overhang'] - usb_overhang
    esp_ref('REF ESP PCB', box(ew, body_l, bt, ex, esp_body_y, ez), '#202d32')
    esp_ref('REF ESP antenna - no tie here', box(18, p['esp_antenna_overhang'], 0.9,
         ex, ey + el / 2 - p['esp_antenna_overhang'] / 2, ez + bt), '#294340')
    esp_ref('REF ESP RF shield - tie here', box(18, 20, 3.2, ex, ey + 13, ez + bt), '#b3bec7')
    for x in (ex - 6.1, ex + 6.1):
        esp_ref('REF ESP USB C', box(9, 7.5, 3.4, x, esp_front + 2.3, ez + bt), '#b4bec7')
    for side in (-1, 1):
        px = ex + side * p['esp_pin_row_spacing'] / 2
        if not soldered:
            esp_ref('REF ESP header insulator', box(2.5, 54.4, 2.5, px,
                 esp_body_y, ez - 2.5), '#dbb747')
        for j in range(22):
            py = esp_body_y - 26.67 + j * 2.54
            if soldered:
                esp_ref('REF ESP solder pad', cyl(0.7, 0.15, px, py, ez-0.15), '#bcbdac')
            else:
                esp_ref('REF ESP pin', box(0.64, 0.64, 6, px, py, ez - 8.5), '#bcbdac')
        for off in (-23, -20.46, 5, 7.54):
            if soldered:
                esp_ref('REF direct solder joint', cyl(0.75, p['esp_connector_depth'],
                    px, ey+off, ez-p['esp_connector_depth']), '#a5afb5')
            else:
                esp_ref('REF jumper housing', box(2.5, 2.5, 9, px, ey + off,
                     ez - p['esp_connector_depth']), '#21262d')
    for off in (-4, -9):
        esp_ref('REF ESP button', box(3.8, 3.2, 2.3, ex + 6, ey + off, ez + bt), '#b7bbbf')
    esp_ref('REF ESP RGB LED', box(3, 3, 1.8, ex - 5, ey - 13, ez + bt), '#e6d7a7')
    for s in support_pads:
        ref('REF insulating support pad', s, '#343638' if m50 else '#ed9762', 'pads')
    for side, x, y in clamps:
        ref('REF keeper toe pad - compressed', box(1, 5, p['keeper_gap'],
             bx + side * (bw / 2 - 0.5), y, bz + bt), '#343638' if m50 else '#ed9762', 'pads')
    ep = p['mounting_pad_thickness']
    elm_y = -l / 2 + p['elm_body_length_reference'] / 2
    for x in (-10,10) if inline else (-17,17):
        for y in p.get('mount_pad_y',[-36,4]):
            ref('REF mounting silicone pad', box(10, 16, ep, x, y, -ep), '#484b50', 'mount')
    ref('REF ELM shell - UNMEASURED', rounded(p['elm_body_width_reference'],
        p['elm_body_length_reference'], p['elm_body_height_reference'], 3.5,
        y=elm_y, z=-ep - p['elm_body_height_reference']), '#292c32', 'elm')
    ref('REF OBD plug - UNMEASURED', rounded(43, 21, 16, 3, y=-l / 2 - 9.5,
         z=-ep - p['elm_body_height_reference'] / 2 - 8), '#161b22', 'elm')
    for x, y in screw_xy:
        if inline:
            screw=cyl(1.5,25,x,y,0)+cyl(2.8,2,x,y,-2)
            socket=Polygon(*[(1.35*math.cos(a*math.pi/3),1.35*math.sin(a*math.pi/3))
                             for a in range(6)],align=None)
            screw-=Pos(x,y,-2.1)*extrude(socket,amount=1.2)
            ref('REF M3 x 25 underside lid screw',screw,p['hardware_color'],'base_hardware')
            continue
        head_z=h+p['lid_thickness']
        screw=cyl(1.5,10,x,y,head_z-10)+cyl(2.8,2,x,y,head_z)
        if p.get('vent_layout')=='side_banks':
            socket=Polygon(*[(1.35*math.cos(a*math.pi/3),1.35*math.sin(a*math.pi/3))
                             for a in range(6)],align=None)
            screw-=Pos(x,y,head_z+1)*extrude(socket,amount=1.2)
        ref('REF M3 x 10 screw',screw,p.get('hardware_color','#383a3b' if m50 else '#7c878c'),'lid_hardware')
    for _, x, y in clamps:
        sl = p.get('keeper_screw_length', 8)
        ref(f'REF M3 x {sl:g} screw', cyl(1.5, sl, x, y, kz + kt - sl)
            + cyl(2.8, 1.8, x, y, kz + kt), p.get('hardware_color','#7c878c'), 'keeper_hardware')
    # Reference strap loops follow the case grooves and taper to the ELM body.
    sx = p['strap_slot_x']-0.5 if inline else w/2-p['strap_groove_depth']
    sz = f-1 if inline else h+p['lid_thickness']-p['strap_groove_depth']
    eb = -ep - p['elm_body_height_reference']
    ehw = p['elm_body_width_reference'] / 2
    if inline:
        outer = Polygon((-sx-1,sz+1),(sx+1,sz+1),(sx+1,-0.3),
                        (ehw+1.2,-1.7),(ehw+1.2,eb-1),(-ehw-1.2,eb-1),
                        (-ehw-1.2,-1.7),(-sx-1,-0.3),align=None)
        inner = Polygon((-sx,sz),(sx,sz),(sx,-0.7),
                        (ehw+0.2,-2.1),(ehw+0.2,eb),(-ehw-0.2,eb),
                        (-ehw-0.2,-2.1),(-sx,-0.7),align=None)
    else:
        outer = Polygon((-sx-1, sz+1), (sx+1, sz+1), (sx+1, -0.4),
                        (ehw+0.6, eb-1), (-ehw-0.6, eb-1), (-sx-1, -0.4), align=None)
        inner = Polygon((-sx, sz), (sx, sz), (sx, 0),
                        (ehw, eb), (-ehw, eb), (-sx, 0), align=None)
    for y in p['strap_y']:
        strap = Pos(0, y+5, 0) * extrude(Plane.XZ * (outer-inner), amount=10,dir=(0,-1,0))
        ref('REF reusable 10 mm strap', strap, p.get('strap_color','#171e25'), 'straps')
    shield_top = ez + bt + 3.2
    tie_outer = Polygon((-17.4,-0.9), (17.4,-0.9), (17.4,ez+bt+0.2),
        (9.4,shield_top+0.8), (-9.4,shield_top+0.8), (-17.4,ez+bt+0.2), align=None)
    tie_inner = Polygon((-16.6,0), (16.6,0), (16.6,ez+bt-0.3),
        (9,shield_top), (-9,shield_top), (-16.6,ez+bt-0.3), align=None)
    esp_ref('REF ESP retaining nylon tie', Pos(ex,ey+p['esp_tie_y_offset']+1.25,0)
        * extrude(Plane.XZ * (tie_outer-tie_inner), amount=2.5,dir=(0,-1,0)), '#2c2e2d' if m50 else '#bd7746', 'esp_tie')

    # Explicit interference envelopes, kept out of the exported visual assembly.
    checks = [
        ('buck PCB', box(bw, bl, bt, bx, by, bz)),
        ('buck solder', box(bw - 4, bl - 4, p['buck_solder_allowance'], bx, by,
                           bz - p['buck_solder_allowance'])),
        ('buck component envelope', box(bw - 2.4, bl - 2,
                                         p['buck_top_allowance'], bx, by, bz + bt)),
        ('ESP PCB body', E(box(ew, body_l, bt, ex, esp_body_y, ez))),
        ('ESP component envelope', E(box(ew-4, body_l-2, p['esp_top_allowance'],
             ex, esp_body_y, ez+bt))),
    ]
    for x in (ex-6.1, ex+6.1):
        checks.append(('ESP USB mating plug envelope', E(box(14, 14, 7.5,
            x, ey-el/2-7, ez+bt+1.7-3.75))))
    for side in (-1, 1):
        checks.append(('ESP solder row' if soldered else 'ESP header and jumper row', E(box(2.9, 54.8,
            p['esp_connector_depth'], ex + side * p['esp_pin_row_spacing'] / 2,
            esp_body_y, ez - p['esp_connector_depth']))))
    for y in (by - bl / 2 - 6.2, by + bl / 2 + 6.2):
        checks.append(('buck terminal plug / wire turn', box(10.5, 12, 12,
            bx + 7, y, bz + bt + 1)))
    if inline:
        checks += [(name,shape) for name,shape,_,group in refs if group in ('straps','esp_tie')]
    return base, lid, keeper, keepers, gauge, refs, checks, screw_xy


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parameters', type=Path, default=HERE / 'parameters.json')
    ap.add_argument('--out', type=Path, default=HERE / 'exports')
    args = ap.parse_args()
    p = json.loads(args.parameters.read_text())
    if p.get('auto_height'):
        p['base_height'] = p['floor'] + max(
            p['buck_under_board']+p['pcb_thickness']+p['buck_top_allowance'],
            p['esp_under_board']+p['pcb_thickness']+p['esp_top_allowance'],
        ) + p['roof_clearance']
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    print('Building revision', p['revision'], flush=True)
    base, lid, keeper, keepers, gauge, refs, checks, screw_xy = design(p)
    print('Geometry constructed; verifying packaging...', flush=True)
    print_parts = {
        'base': base,
        'lid': Pos(0, 0, p['base_height'] + p['lid_thickness']) * Rot(X=180) * lid,
        'buck-keeper': keeper,
        'fit-gauge': gauge,
    }
    results = {}
    for name, part in print_parts.items():
        assert part.is_valid and len(part.solids()) == 1, (name, 'invalid or disconnected')
        bb = part.bounding_box()
        assert abs(bb.min.Z) < 1e-5, (name, 'not on print bed', bb.min.Z)
        results[name] = {'valid': part.is_valid, 'solids': len(part.solids()),
            'volume_mm3': round(part.volume, 3),
            'bbox_mm': [round(v, 3) for v in bb.size]}
        export_step(part, out / (name + '.step'))
        export_stl(part, out / (name + '.stl'), tolerance=0.035, angular_tolerance=0.12)
        print(name, results[name], flush=True)
    assembled_prints = [('base', base), ('lid', lid)] + [
        ('buck-keeper-' + str(i + 1), k) for i, k in enumerate(keepers)]
    clashes = []
    for i, (name, shape) in enumerate(assembled_prints):
        for other_name, other in assembled_prints[i + 1:]:
            v = volume(shape & other)
            if v > 0.001:
                clashes.append([name, other_name, round(v, 5)])
        for check_name, envelope in checks:
            v = volume(shape & envelope)
            if v > 0.001:
                clashes.append([name, check_name, round(v, 5)])
        for ref_name, ref_shape, _, group in refs:
            if group == 'electronics':
                v = volume(shape & ref_shape)
                if v > 0.001:
                    clashes.append([name, ref_name, round(v, 5)])
    if p.get('layout') == 'inline':
        for name, shape in checks:
            if name.startswith('buck'):
                for other_name, other in checks:
                    if other_name.startswith('ESP') and volume(shape & other)>0.001:
                        clashes.append([name,other_name,round(volume(shape & other),5)])
        for name, shape, _, group in refs:
            if group == 'straps':
                for other_name, other, _, other_group in refs:
                    if other_group in ('elm','mount') and volume(shape & other)>0.001:
                        clashes.append([name,other_name,round(volume(shape & other),5)])
    for name, shape, _, group in refs:
        if group == 'base_hardware':
            for other_name, other, _, other_group in refs:
                if other_group in ('mount','elm') and volume(shape & other)>0.001:
                    clashes.append([name,other_name,round(volume(shape & other),5)])
    results['interferences'] = clashes
    results['physical_fit_verified'] = False
    if p.get('exterior_style') == 'm50':
        results['exterior'] = {'style':'M50-inspired', 'lid_relief_depth_mm':p['lid_relief_depth'],
            'lid_minimum_skin_mm':p['lid_thickness']-(p['lid_relief_depth'] if p.get('layout')=='inline'
                else max(p['lid_relief_depth'],p['strap_groove_depth'])),
            'floor_minimum_skin_mm':p['floor']-(1 if p.get('layout')=='inline' else 0),
            'side_panel_depth_mm':p['side_panel_depth'], 'added_enclosure_height_mm':0,
            'vent_layout':p.get('vent_layout','lid_bank'), 'lid_caption':p.get('lid_caption','E36'),
            'silver_finish':'optional paint reference, excluded from all print meshes'}
    results['nominal_clearances_mm'] = {
        'buck_roof': p['base_height']-p['floor']-p['buck_under_board']
                      -p['pcb_thickness']-p['buck_top_allowance'],
        'esp_roof': p['base_height']-p['floor']-p['esp_under_board']
                      -p['pcb_thickness']-p['esp_top_allowance'],
        'esp_wire_turn': p['esp_under_board']-p['esp_connector_depth'],
        'buck_solder_to_floor': p['buck_under_board']-p['buck_solder_allowance'],
        'lid_per_side': p['lip_clearance'],
    }
    assert all(v>0 for v in results['nominal_clearances_mm'].values())
    results['notes'] = ['Nominal/photo-derived envelopes; not a scan of actual boards.',
        'Physical support contact areas, wire bends and USB plug fit still need checking.']
    (out / 'cad-validation.json').write_text(json.dumps(results, indent=2) + '\n')
    assert not clashes, ('Interferences found', clashes)

    children = []
    scene = []
    styled = p.get('exterior_style') == 'm50'
    for name, shape, color, group in (
        [('base', base, p.get('case_color','#141619' if styled else '#394650'), 'base'),
         ('lid', lid, p.get('case_color','#1b1d1f' if styled else '#52616c'), 'lid')]
        + [('buck keeper ' + str(i+1), k, p.get('case_color','#252728' if styled else '#ed9762'), 'keeper') for i, k in enumerate(keepers)]
        + refs
    ):
        shape.label = name
        shape.color = Color(color)
        children.append(shape)
        verts, triangles = shape.tessellate(0.18, 0.22)
        scene.append({'name': name, 'color': color, 'group': group,
                      'vertices': [[round(c, 4) for c in v] for v in verts],
                      'triangles': [list(t) for t in triangles]})
    assembly = Compound(children=children, label='ELM backpack '+p['revision'])
    export_step(assembly, out / 'assembly-with-references.step')
    (out / 'scene.json').write_text(json.dumps({'parameters': p, 'parts': scene}, separators=(',', ':')))
    (out / 'resolved-parameters.json').write_text(json.dumps(p, indent=2)+'\n')
    print('Exported CAD, assembly, scene and validation to', out, flush=True)


if __name__ == '__main__':
    main()
