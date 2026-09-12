"""Paquete de pedido para PCBWay: 1 muestra ensamblada (SMD + THT), partes compradas por PCBWay.

  python3 hardware/onboard/pcbway.py      # escribe fab/pcbway/ y fab/pcbway-sample-order.zip

Sale todo de gen_board.P y de los archivos de fab/ ya generados (gerbers, pos, dibujos). El BOM usa el
formato de columnas de PCBWay (Item, Designator, Qty, Manufacturer, Mfg Part #, Description/Value,
Package/Footprint, Type, Notes) con numero de fabricante real por linea y el codigo LCSC como pista.
"""
import csv, os, re, shutil, zipfile
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
FAB = os.path.join(HERE, "fab"); OUT = os.path.join(FAB, "pcbway"); os.makedirs(OUT, exist_ok=True)
src = open(os.path.join(HERE, "gen_board.py")).read()
ns = {}; exec(re.search(r"^P = \[.*?^\]", src, re.S | re.M).group(0), ns); P = ns["P"]

# ref -> (manufacturer, MPN, description, package, type, notes). Lo que no esta aca sale de P.
MFG = {
 "J1":  ("Macchina (or equivalent J1962 male right-angle PCB plug)", "CCBDM20", "OBD2 16-pin male right-angle PCB connector, 4.00 mm pin pitch, rows 3.00 mm apart", "TH-16P", "THT",
         "CRITICAL: verify footprint against connector before soldering (pitch 4.00 mm, rows 3.00 mm, rows at 2.25/5.25 mm from flange). Body overhangs board edge. Source: macchina.cc 5-pack, or customer-consigned."),
 "J4":  ("JST", "B3B-XH-A(LF)(SN)", "Wire-to-board header XH 2.5 mm 3P vertical", "XH 3P", "THT", "Optional pigtail header; assemble."),
 "J3":  ("Korean Hroparts Elec", "TYPE-C-31-M-12", "USB-C receptacle 16P, 5A", "SMD + 4 THT shell legs", "SMD", "Shell legs are through-hole: solder them too."),
 "U3":  ("Espressif", "ESP32-S3-WROOM-1-N16R8", "Wi-Fi/BLE module, 16 MB flash, 8 MB octal PSRAM", "WROOM-1 (18x25.5 mm)", "SMD", "Do NOT substitute N16 without R8 (octal PSRAM required). Antenna end at board edge; no fixture contact there."),
 "U1":  ("STMicroelectronics", "E-L9637D013TR", "ISO 9141 K-line transceiver", "SOIC-8", "SMD", "Pin 1 orientation critical."),
 "U2":  ("Diodes Incorporated", "AP63203WU-7", "Buck 3.3 V fixed, 2 A, 3.8-32 V in", "TSOT-26", "SMD", ""),
 "L1":  ("Sunlord", "SWPA6045S4R7MT", "Power inductor 4.7 uH 3.3 A shielded", "6.0x6.0x4.5 mm", "SMD", ""),
 "D1":  ("Littelfuse / Bourns / SMC (any)", "SMBJ24A", "TVS unidirectional 24 V standoff 600 W", "SMB (DO-214AA)", "SMD", "Cathode band = pad 1 = +12 V rail. Polarity critical."),
 "D2":  ("MDD", "SS34", "Schottky 3 A 40 V", "SMA (DO-214AC)", "SMD", "Cathode band = pad 1."),
 "D3":  ("MDD", "SS34", "Schottky 3 A 40 V", "SMA (DO-214AC)", "SMD", "Cathode band = pad 1."),
 "F1":  ("Nanjing Sart", "S1206-S-1.0A", "Fuse 1 A 32 V fast", "1206", "SMD", ""),
 "R1":  ("Ever Ohms (or any 2010 0.75 W)", "CR2010F510RE04Z", "Resistor 510 R 1% 0.75 W", "2010", "SMD", ""),
 "C10": ("Any (Samsung/Murata/Yageo)", "CC1210X7R50V106MN", "MLCC 10 uF 50 V X7R", "1210", "SMD", "50 V rating required."),
 "C11": ("Any (Samsung/Murata/Yageo)", "CC1210X7R50V106MN", "MLCC 10 uF 50 V X7R", "1210", "SMD", "50 V rating required."),
 "C14": ("Samsung", "CL21A226MAQNNNE", "MLCC 22 uF 25 V X5R", "0805", "SMD", ""),
 "C15": ("Samsung", "CL21A226MAQNNNE", "MLCC 22 uF 25 V X5R", "0805", "SMD", ""),
 "C5":  ("Samsung", "CL21A106KAYNNNE", "MLCC 10 uF 25 V X5R", "0805", "SMD", ""),
 "C7":  ("Samsung", "CL10A105KB8NNNC", "MLCC 1 uF 50 V X5R", "0603", "SMD", ""),
 "SW1": ("XKB", "TS-1187A-B-A-B", "Tactile switch 6x6 mm SMD", "6x6 mm 4-pad", "SMD", ""),
 "SW2": ("XKB", "TS-1187A-B-A-B", "Tactile switch 6x6 mm SMD", "6x6 mm 4-pad", "SMD", ""),
 "LED1": ("Hubei KENTO", "KT-0603W", "LED white", "0603", "SMD", "Cathode = pad 1 (green mark on silk)."),
 "LED2": ("Hubei KENTO", "KT-0603R", "LED red", "0603", "SMD", "Cathode = pad 1."),
}
CAP100N = ("Yageo", "CC0603KRX7R9BB104", "MLCC 100 nF 50 V X7R", "0603", "SMD", "")
RES = {"100k": "0603WAF1003T5E", "22k": "0603WAF2202T5E", "5k1": "0603WAF5101T5E", "10k": "0603WAF1002T5E", "2k2": "0603WAF2201T5E",
       "1k": "0603WAF1001T5E", "4k7": "0603WAF4701T5E", "36k": "0603WAF3602T5E", "3k74": "0603WAF3741T5E"}

rows = []
for ref, lib, fpn, x, y, rot, val, mpn, lcsc, note in P:
    if ref.startswith("H") or ref == "J2": continue
    if ref in MFG: m = MFG[ref]
    elif val.startswith("100n"): m = CAP100N
    elif val in RES: m = ("UNI-ROYAL", RES[val], "Resistor %s 1%% 0.1 W" % val.replace("k", " k").replace("R", " R"), "0603", "SMD", "")
    else: m = ("", mpn, val, fpn, "SMD", note)
    code = lcsc.split()[0] if lcsc.strip().startswith("C") else ""
    rows.append(dict(ref=ref, val=val, mfg=m[0], mpn=m[1], desc=m[2], pkg=m[3], typ=m[4], notes=m[5], lcsc=code))

# agrupar por MPN
groups = {}
for r in rows:
    g = groups.setdefault((r["mpn"], r["val"]), dict(r, refs=[]))
    g["refs"].append(r["ref"])
with open(os.path.join(OUT, "bom-pcbway.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Item #", "Designator", "Qty", "Manufacturer", "Mfg Part #", "Description / Value", "Package/Footprint", "Type", "Your Instructions / Notes", "LCSC # (hint)"])
    for i, g in enumerate(groups.values(), 1):
        w.writerow([i, ", ".join(g["refs"]), len(g["refs"]), g["mfg"], g["mpn"], g["desc"], g["pkg"], g["typ"], g["notes"], g["lcsc"]])
# DNP
with open(os.path.join(OUT, "bom-pcbway.csv"), "a", newline="") as f:
    csv.writer(f).writerow([len(groups) + 1, "J2", 1, "", "DNP", "1x6 2.54 mm header - DO NOT POPULATE", "PinHeader 1x06", "THT", "DNP", ""])

# pick and place: del pos de KiCad (origen esquina inferior izquierda, Y hacia arriba), incluye THT
pos = list(csv.DictReader(open(os.path.join(FAB, "pos-kicad.csv"))))
fp_by_ref = {p[0]: p[2] for p in P}; val_by_ref = {p[0]: p[6] for p in P}
with open(os.path.join(OUT, "pnp-pcbway.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X (mm)", "Mid Y (mm)", "Layer", "Rotation", "Footprint", "Value", "Type"])
    for p in pos:
        ref = p["Ref"]
        if ref.startswith("H") or ref == "J2": continue
        typ = "THT" if ref in ("J1", "J4") else "SMD"
        w.writerow([ref, "%.3f" % float(p["PosX"]), "%.3f" % float(p["PosY"]), "Top" if p["Side"] == "top" else "Bottom", p["Rot"], fp_by_ref[ref], val_by_ref[ref], typ])

for src_name, dst_name in (("e36-kline-onboard-gerbers.zip", "e36-kline-onboard-gerbers.zip"), ("silk.pdf", "assembly-drawing-top.pdf"),
                           ("silk.png", "assembly-drawing-top.png"), ("render-top.png", "board-render-top.png"), ("schematic.png", "schematic.png"), ("top.png", "top-layer-plot.png")):
    p = os.path.join(FAB, src_name)
    if os.path.exists(p): shutil.copy(p, os.path.join(OUT, dst_name))
shutil.copy(os.path.join(HERE, "e36obd.pretty", "OBD2_Male_RightAngle_16P.kicad_mod"), os.path.join(OUT, "OBD2_footprint.kicad_mod"))

n_smd = sum(1 for r in rows if r["typ"] == "SMD"); n_tht = sum(1 for r in rows if r["typ"] == "THT")
notes = f"""# PCBWay — pedido de 1 muestra ensamblada (borrador, {date.today()})

Placa: **E36 K-line reader rev B**, `hardware/onboard`. Subir `e36-kline-onboard-gerbers.zip` en el
formulario de PCB y, en el paso de ensamblado, `bom-pcbway.csv`, `pnp-pcbway.csv` y
`assembly-drawing-top.pdf`. Todo en este directorio (y en `pcbway-sample-order.zip`).

## Formulario PCB (pcbway.com/QuickOrderOnline.aspx)

| Campo | Valor |
|---|---|
| Board type | Single pieces |
| Size | 90 × 50 mm |
| Quantity | 5 (mínimo práctico; se ensambla 1) |
| Layers | 2 |
| Material | FR-4, TG 150 |
| Thickness | 1.6 mm |
| Min track / spacing | 6/6 mil (la placa usa 0,15 mm mínimos) |
| Min hole size | 0.3 mm |
| Solder mask | Green |
| Silkscreen | White |
| Surface finish | HASL lead-free (ENIG si se quiere mejor plano para el módulo) |
| Via process | Tenting vias |
| Finished copper | 1 oz |
| Remove product No. | Yes |
| Impedance control | No |

## Formulario de ensamblado

| Campo | Valor |
|---|---|
| Assembly quantity | **1** (o 2 para tener repuesto: el setup es igual) |
| Assembly side | Top only |
| Unique parts | {len(groups)} |
| SMD parts | {n_smd} |
| THT parts | {n_tht} (J1 conector OBD2, J4 JST XH) |
| BGA/QFN | 0 |
| Parts sourcing | Turnkey: PCBWay compra todo. Alternativa: J1 consignado (ver notas) |
| Sensitive components | Sí: módulo Wi-Fi U3 (no tocar la antena con fixtures) |
| Function test | No; solo inspección visual/AOI |
| Conformal coating | No |

## Notas para "Your instructions" (copiar y pegar)

```
Single assembled sample of a 2-layer automotive diagnostics reader. All SMD on top; two THT parts (J1, J4).
1. J1 is a J1962 OBD2 male right-angle PCB plug (Macchina CCBDM20 or equivalent): 16 pins, 4.00 mm pitch,
   two rows 3.00 mm apart, rows at 2.25 mm and 5.25 mm behind the flange, body overhangs the board edge.
   PLEASE check your connector against the footprint (holes 1.3 mm) before soldering; if it does not match,
   contact us before proceeding. Alternatively we can consign the connector.
2. U3 (ESP32-S3-WROOM-1-N16R8): must be the N16R8 variant (octal PSRAM). Keep the antenna end free of fixture contact.
3. Polarised parts: D1 (TVS) cathode band to pad 1 (+12 V rail); D2/D3 cathode to pad 1; LED1/LED2 cathode pad 1;
   U1 and U2 pin 1 as per silkscreen dot.
4. J2 (1x6 header) is DNP. Mounting holes H1-H4 stay empty.
5. Use the pick-and-place file coordinates (origin bottom-left, mm); rotations are KiCad convention, please
   confirm orientation from the assembly drawing for U1, U2, U3, D1-D3 and LEDs.
6. Lead-free process. No wash residue on the USB-C receptacle.
```

## Precio oficial (motor de cotización de PCBWay, ver `quote-official.md`)

PCB 5 pcs **6,50 USD** · ensamblado 1 placa **88,00 USD** (tarifa plana, igual para 2 o 5) · envío a Argentina
FedEx 48,87 / DHL 72,73 USD. Los componentes los cotizan a mano tras revisar el BOM: estimar 15–25 USD para una
muestra. Total esperado ≈ 160–170 USD con FedEx.

## Archivos

- `e36-kline-onboard-gerbers.zip` — gerbers + taladros (KiCad 10, extensiones Protel).
- `bom-pcbway.csv` — BOM en columnas PCBWay, con fabricante y MPN por línea y el código LCSC como pista.
- `pnp-pcbway.csv` — centroides, origen esquina inferior izquierda, mm, incluye J1/J4.
- `assembly-drawing-top.pdf/.png` — referencias y contornos (F.Fab + serigrafía).
- `board-render-top.png`, `schematic.png`, `top-layer-plot.png` — para el revisor.
- `OBD2_footprint.kicad_mod` — el footprint de J1, por si necesitan las cotas.
"""
open(os.path.join(OUT, "ORDER-NOTES.md"), "w").write(notes)
zpath = os.path.join(FAB, "pcbway-sample-order.zip")
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for name in sorted(os.listdir(OUT)):
        z.write(os.path.join(OUT, name), name)
print("BOM: %d lineas (+J2 DNP), SMD %d, THT %d; paquete: %s" % (len(groups), n_smd, n_tht, zpath))
