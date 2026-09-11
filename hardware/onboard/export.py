"""Salidas de fabricacion para JLCPCB y vistas para revisar.

  PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
  $PY hardware/onboard/export.py

Genera en hardware/onboard/fab/:  gerbers/ (+ taladros), bom-jlcpcb.csv, cpl-jlcpcb.csv,
drc.json, top.pdf/png, bottom.pdf/png, render-top.png, render-iso.png.
"""
import csv, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_board import P, OUT, HERE, OX, OY, W, H

FAB = os.path.join(HERE, "fab")
GERB = os.path.join(FAB, "gerbers")
os.makedirs(GERB, exist_ok=True)
CLI = "kicad-cli"

def run(*args):
    r = subprocess.run([CLI, *args], capture_output=True, text=True)
    if r.returncode:
        print("FALLO:", " ".join(args), "\n", r.stdout[-800:], r.stderr[-800:])
    return r

# ----------------------------------------------------------------- DRC
r = run("pcb", "drc", "--severity-all", "--format", "json", "-o", os.path.join(FAB, "drc.json"), OUT)
drc = json.load(open(os.path.join(FAB, "drc.json")))
def count(kind):
    return sum(1 for v in drc.get(kind, []))
print("DRC: %d violaciones, %d desconectados, %d esquematico" % (count("violations"), count("unconnected_items"), count("schematic_parity")))
from collections import Counter
sev = Counter((v["type"], v["severity"]) for v in drc.get("violations", []))
for (t, s), n in sorted(sev.items()): print("   %-32s %-8s %d" % (t, s, n))
for v in drc.get("unconnected_items", [])[:10]: print("   sin conectar:", v["description"])

# ------------------------------------------------------------- gerbers
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
run("pcb", "export", "gerbers", "-o", GERB + "/", "--layers", LAYERS, "--subtract-soldermask", "--no-x2", OUT)
run("pcb", "export", "drill", "-o", GERB + "/", "--format", "excellon", "--excellon-units", "mm",
    "--drill-origin", "absolute", "--generate-map", "--map-format", "gerberx2", OUT)
import zipfile
with zipfile.ZipFile(os.path.join(FAB, "e36-kline-onboard-gerbers.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(os.listdir(GERB)): z.write(os.path.join(GERB, fn), fn)
print("gerbers:", len(os.listdir(GERB)), "archivos, zip listo")

# --------------------------------------------------------- BOM + CPL JLC
DNP = {"J2"}                       # no se puebla
THT = {"J1"}                       # el conector se suelda a mano (o TH de JLC)
groups = {}
for ref, lib, fpname, x, y, rot, val, mpn, lcsc, note in P:
    if ref.startswith("H") or ref in DNP: continue
    key = (val, fpname, lcsc)
    groups.setdefault(key, {"refs": [], "mpn": mpn, "note": note})["refs"].append(ref)
with open(os.path.join(FAB, "bom-jlcpcb.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Nota"])
    for (val, fpname, lcsc), g in groups.items():
        w.writerow([val, ",".join(g["refs"]), fpname, lcsc, g["mpn"], g["note"]])
print("BOM: %d lineas" % len(groups))

r = run("pcb", "export", "pos", "-o", os.path.join(FAB, "pos-kicad.csv"), "--format", "csv",
        "--units", "mm", "--side", "both", "--use-drill-file-origin", OUT)
with open(os.path.join(FAB, "pos-kicad.csv")) as f, open(os.path.join(FAB, "cpl-jlcpcb.csv"), "w", newline="") as g:
    rd = csv.DictReader(f); w = csv.writer(g)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    n = 0
    for row in rd:
        ref = row["Ref"]
        if ref.startswith("H") or ref in DNP: continue
        # origen de la placa = esquina superior izquierda; JLC usa Y hacia arriba
        x = float(row["PosX"]); y = float(row["PosY"])   # origen aux = esquina inferior izq, Y hacia arriba
        w.writerow([ref, "%.3fmm" % x, "%.3fmm" % y, "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
        n += 1
print("CPL: %d componentes" % n)

# --------------------------------------------------------------- vistas
for name, layers in (("top", "F.Cu,F.SilkS,F.Mask,Edge.Cuts,F.Fab"), ("bottom", "B.Cu,B.SilkS,Edge.Cuts"),
                     ("top-copper", "F.Cu,Edge.Cuts"), ("silk", "F.SilkS,Edge.Cuts,F.Fab")):
    pdf = os.path.join(FAB, name + ".pdf")
    run("pcb", "export", "pdf", "-o", pdf, "--layers", layers, "--include-border-title", OUT)
    subprocess.run(["pdftocairo", "-png", "-r", "220", "-singlefile", pdf, os.path.join(FAB, name)], check=False)
run("pcb", "render", "-o", os.path.join(FAB, "render-top.png"), "--side", "top", "-w", "2400", "-h", "1400",
    "--zoom", "1.1", "--quality", "basic", "--background", "opaque", OUT)
run("pcb", "render", "-o", os.path.join(FAB, "render-iso.png"), "--rotate", "-35,0,20", "--perspective",
    "-w", "2400", "-h", "1400", "--zoom", "1.0", "--quality", "basic", "--background", "opaque", OUT)
run("pcb", "render", "-o", os.path.join(FAB, "render-bottom.png"), "--side", "bottom", "-w", "2400", "-h", "1400",
    "--zoom", "1.1", "--quality", "basic", "--background", "opaque", OUT)
print("listo:", sorted(os.listdir(FAB)))
