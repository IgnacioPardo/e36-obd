"""Estimacion de precio JLCPCB (PCB + ensamblado economico) a partir del BOM real.

  python3 hardware/onboard/pricing.py           # escribe fab/pricing-jlcpcb.md

Precios de componentes: API publica de busqueda de partes de JLCPCB (la misma que usa jlcpcb.com/parts),
consultada por codigo LCSC. Tarifas de ensamblado: https://jlcpcb.com/help/article/pcb-assembly-price
(leido 2026-09-11). Precio de PCB: oferta publica de 2 capas <= 100x100 mm. Todo en USD.
No incluye envio ni impuestos de importacion.
"""
import csv, json, os, subprocess, sys, time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
BOM = os.path.join(HERE, "fab", "bom-jlcpcb.csv")
OUT = os.path.join(HERE, "fab", "pricing-jlcpcb.md")
API = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
HDR = ["-H", "Content-Type: application/json", "-H", "Accept: application/json",
       "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128 Safari/537.36",
       "-H", "Origin: https://jlcpcb.com", "-H", "Referer: https://jlcpcb.com/parts"]

# Tarifas JLCPCB "Economic PCBA" (help/article/pcb-assembly-price, 2026-09-11)
SETUP, STENCIL, JOINT, FEEDER_EXT = 8.18, 1.53, 0.0016, 3.07
HAND_LABOR, HAND_JOINT = 3.58, 0.0164          # soldadura manual (THT), por pedido + por junta
PCB_PRICE = {5: 2.00, 10: 5.00, 20: 9.00}        # 2 capas, 90x50, verde: 5 pcs es la oferta fija; 10/20 aproximados
SMT_JOINTS = 142                                 # pads SMD de los 36 componentes ensamblados (contado en la placa)
NOT_ASSEMBLED = {"J1": "ficha OBD2: sin stock en JLC (C9900166046), comprar aparte y soldar a mano",
                 "J2": "no se puebla",
                 "J4": "THT: soldarla uno mismo, o pedir soldadura manual (+%.2f por pedido, +%.4f x 3 juntas)" % (HAND_LABOR, HAND_JOINT)}

def query(code):
    body = json.dumps({"currentPage": 1, "pageSize": 5, "keyword": code, "firstSortName": "", "secondSortName": "",
                       "componentBrandList": [], "componentLibraryType": "", "stockFlag": False, "stockSort": "",
                       "componentSpecificationList": [], "preferredComponentFlag": False, "componentAttributeList": [],
                       "searchSource": "search"})
    out = subprocess.run(["curl", "-s", "-m", "25", "-X", "POST", API, *HDR, "--data", body], capture_output=True, text=True).stdout
    try:
        for c in json.loads(out)["data"]["componentPageInfo"]["list"]:
            if isinstance(c, dict) and c.get("componentCode") == code:
                return c
    except Exception:
        pass
    return None

def price_at(c, n):
    tiers = c.get("componentPrices") or []
    for t in tiers:
        if t["startNumber"] <= n and (t.get("endNumber") in (None, 0) or n <= t["endNumber"]):
            return t["productPrice"]
    return tiers[-1]["productPrice"] if tiers else 0.0

rows = list(csv.DictReader(open(BOM)))
lines, ext_types, notes = [], set(), []
parts_cost = {q: 0.0 for q in (2, 5, 10, 20)}
for r in rows:
    refs = [x.strip() for x in r["Designator"].split(",")]
    qty = len(refs)
    code = r["LCSC Part #"].split()[0] if r["LCSC Part #"].strip() else ""
    skip = [x for x in refs if x in NOT_ASSEMBLED]
    if skip:
        notes.append("%s: %s" % (",".join(skip), NOT_ASSEMBLED[skip[0]])); continue
    c = query(code) if code.startswith("C") else None
    time.sleep(0.25)
    if not c:
        lines.append((r["Comment"], ",".join(refs), code or "?", "?", 0, None, None, "SIN RESULTADO")); continue
    lib = c.get("componentLibraryType"); stock = c.get("stockCount") or 0
    if lib == "expand": ext_types.add(code)
    for q in parts_cost:
        parts_cost[q] += price_at(c, q * qty) * qty
    lines.append((r["Comment"], ",".join(refs), code, "basico" if lib == "base" else "extendido", stock,
                  price_at(c, qty * 5), price_at(c, qty * 10), (c.get("componentModelEn") or "")[:28]))

def total(q):
    fees = SETUP + STENCIL + FEEDER_EXT * len(ext_types)
    smt = JOINT * SMT_JOINTS * q
    pcb = PCB_PRICE.get(q, PCB_PRICE[5] if q < 5 else PCB_PRICE[20])
    parts = parts_cost[q] * q                      # parts_cost es por placa
    return fees, smt, parts, pcb, fees + smt + parts + pcb

md = ["# Precio JLCPCB — placa rev B, ensamblado economico (SMD)", "",
      "Generado por `pricing.py` el %s. Precios de partes desde la API de partes de JLCPCB por codigo LCSC; tarifas de" % date.today(),
      "ensamblado de [help/article/pcb-assembly-price](https://jlcpcb.com/help/article/pcb-assembly-price); PCB 2 capas 90 × 50 mm verde.",
      "USD, sin envio ni impuestos. Las partes las compra JLC al momento del pedido: stock y precio cambian.", "",
      "## Totales", "", "| Placas ensambladas | Fijos (setup + stencil + %d partes extendidas × %.2f) | SMT (%d juntas × %.4f) | Partes (todas las placas) | PCB (5 pcs min.) | **Total** | **Por placa** |" % (len(ext_types), FEEDER_EXT, SMT_JOINTS, JOINT),
      "|---|---|---|---|---|---|---|"]
for q in (2, 5, 10, 20):
    fees, smt, parts, pcb, tot = total(q)
    md.append("| %d | %.2f | %.2f | %.2f | %.2f | **%.2f** | **%.2f** |" % (q, fees, smt, parts, pcb, tot, tot / q))
md += ["", "Los fijos pesan: con 2 placas cada una sale mas del doble que con 10. La PCB se pide de a 5 (oferta de 2 USD); 10 y 20 son estimados.", "",
       "## Partes (lo que JLC monta)", "", "| Valor | Refs | LCSC | Libreria | Stock | USD c/u (5 placas) | USD c/u (10 placas) | Parte |", "|---|---|---|---|---|---|---|---|"]
for v, refs, code, lib, stock, p5, p10, model in lines:
    md.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (v, refs, code, lib, stock, "%.4f" % p5 if p5 is not None else "?", "%.4f" % p10 if p10 is not None else "?", model))
md += ["", "Partes extendidas (cobran %.2f USD de carga de alimentador cada una, por pedido): %s." % (FEEDER_EXT, ", ".join(sorted(ext_types))), "",
       "## No incluido", ""] + ["- " + n for n in notes] + [
       "- Envio a Argentina: JLC Global Standard Direct Line ~10–15 USD (2–4 semanas) o DHL/FedEx ~25–40 USD (~1 semana) para un paquete de 300 g.",
       "- Impuestos de importacion: dependen del regimen courier vigente (verificar).",
       "- Ensamblado estandar en vez de economico: setup 25.56 + stencil 8.21 + 1.53 por cada tipo de parte (basica o extendida); no conviene a esta escala.", "",
       "## Riesgos de stock", "",
       "- E-L9637D013TR (C153038): %s unidades. Es la parte critica y con menos stock; si se agota, JLC ofrece \"global sourcing\" o se compra en Mouser/LCSC y se suelda a mano." % next((str(l[4]) for l in lines if l[2] == "C153038"), "?"),
       "- La ficha OBD2 de JLC (C9900166046) figura sin stock: la placa se pide sin J1 y la ficha va aparte (Macchina 5 × 19.50 USD, o generica 90° de AliExpress).", "",
       "## Reproducir", "", "```", "python3 hardware/onboard/pricing.py", "```",
       "La consulta por codigo es un POST a `%s` con `{\"keyword\": \"C2913202\", ...}`; devuelve `componentPrices` (tramos), `componentLibraryType` (base/expand) y `stockCount`." % API]
open(OUT, "w").write("\n".join(md) + "\n")
print("\n".join(md[:14]))
print("...", OUT)
