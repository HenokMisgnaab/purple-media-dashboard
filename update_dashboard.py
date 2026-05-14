"""
update_dashboard.py — Fase 2
----------------------------
Bouwt `data.json` voor purple_media_dashboard.html.

Twee databronnen:
  --source=excel  : leest de omzetrapportage-export (xlsx). Default.
                    Voordeel: werkt direct, geen API-keys nodig.
  --source=api    : haalt facturen op via Simplicate v2 REST.
                    Vereist SIMPLICATE_SUBDOMAIN/API_KEY/API_SECRET env vars.

Categorisering (5 kolommen): MA / SLA / WB / OV / IK
  MA  Marketing abo  : alle (abonnement) services + Online Marketing + E-mail Marketing + SMA
  SLA SLA (Service)  : Service + Support  (recurring servicewerk)
  WB  Website        : Development        (project-werk)
  OV  Overig         : Algemeen + Creatie + Projectmanagement + Strategie + Onbekende omzetgroep
  IK  Inkoop         : Inkoop + Inkoop (abonnement)  (eigen categorie, pass-through kosten)

Gebruik:
  python3 update_dashboard.py                       # excel → data.json
  python3 update_dashboard.py --source=api          # api → data.json
  python3 update_dashboard.py --dry-run             # toon samenvatting, schrijf niet
  python3 update_dashboard.py --json=data.json      # custom output-pad
"""

from __future__ import annotations
import os
import sys
import json
import time
import argparse
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, date
from collections import defaultdict
from typing import Any


# ============================================================================
# CONFIGURATIE
# ============================================================================

SUBDOMAIN  = os.environ.get("SIMPLICATE_SUBDOMAIN", "")
API_KEY    = os.environ.get("SIMPLICATE_API_KEY",    "")
API_SECRET = os.environ.get("SIMPLICATE_API_SECRET", "")

PERIOD_START = date(2025, 1, 1)
PERIOD_END   = date(2026, 6, 30)

DEFAULT_EXCEL = "Export+van+omzetrapportage-124333.xlsx"
DEFAULT_JSON  = "data.json"

# Capaciteit-aannames (komen mee in data.json zodat de browser ze kent)
FTE              = 9.5
UUR_TARIEF_EUR   = 110
UUR_PER_FTE_MAAND = 120
MAX_CAPACITY     = round(FTE * UUR_PER_FTE_MAAND * UUR_TARIEF_EUR)  # 125400

# ============================================================================
# CATEGORIE-MAPPING (nieuwe definitie — bevestigd door gebruiker)
# ============================================================================

CAT_MA = {
    "All-in-One Marketing (abonnement)",
    "SEO (abonnement)",
    "SEA (abonnement)",
    "SMA",
    "SMA (abonnement)",
    "Social Media beheer (abonnement)",
    "WordPress-plugin PS in foodservice (abonnement)",
    "Online Marketing",
    "E-mail Marketing",
}
CAT_SLA = {"Service", "Support"}
CAT_WB  = {"Development"}
CAT_IK  = {"Inkoop", "Inkoop (abonnement)"}
# Alle overige -> OV
# (Algemeen, Creatie, Projectmanagement, Strategie, Onbekende omzetgroep, ...)

CATEGORIES_META = {
    "MA":  {"label": "Marketing abo",  "color": "#7c6ef7"},
    "SLA": {"label": "SLA (Service)",  "color": "#2dd4a7"},
    "WB":  {"label": "Website",         "color": "#3b82f6"},
    "OV":  {"label": "Overig",          "color": "#4b5563"},
    "IK":  {"label": "Inkoop",          "color": "#f5a623"},
}

KANAALPARTNERS = {"Marcommit B.V."}  # voor *-marker en cyclisch-label

def categorize(service_name: str) -> str:
    s = (service_name or "").strip()
    if s in CAT_MA:  return "MA"
    if s in CAT_SLA: return "SLA"
    if s in CAT_WB:  return "WB"
    if s in CAT_IK:  return "IK"
    return "OV"


# ============================================================================
# MAANDEN-HULPFUNCTIES
# ============================================================================

def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"

def all_month_keys() -> list[str]:
    keys = []
    y, m = PERIOD_START.year, PERIOD_START.month
    while (y, m) <= (PERIOD_END.year, PERIOD_END.month):
        keys.append(f"{y:04d}-{m:02d}")
        m = m + 1
        if m == 13:
            m = 1; y += 1
    return keys


# ============================================================================
# BRON 1 — EXCEL (omzetrapportage-export)
# ============================================================================

# De export is een service-georiënteerde rapportage: rijen zijn ofwel een
# servicegroep-header (kolom A = naam van categorie zoals "Service", "SEO
# (abonnement)", ...) of een klant-regel direct daaronder ("Klant - werkzaamh.").
# Bedragen per maand staan in kolom B..P (15 maanden). Eerste data-rij (row 2)
# is het maandtotaal van het hele rapport.

EXCEL_MONTH_COLS = ["B","C","D","E","F","G","H","I","J","K","L","M","N","O","P"]
EXCEL_PERIOD = [
    "2025-01","2025-02","2025-03","2025-04","2025-05","2025-06",
    "2025-07","2025-08","2025-09","2025-10","2025-11","2025-12",
    "2026-01","2026-02","2026-03",
]

# De namen in kolom A van de categorie-headers die in de Excel voorkomen
KNOWN_CATEGORY_NAMES = (
    CAT_MA | CAT_SLA | CAT_WB | CAT_IK |
    {"Algemeen", "Creatie", "Projectmanagement", "Strategie", "Onbekende omzetgroep"}
)

def _col_letter(ref: str) -> str:
    s = ""
    for c in ref:
        if c.isalpha(): s += c
        else: break
    return s

def _parse_xlsx(path: str) -> list[dict]:
    """Geeft een lijst rijen [{col_letter: value}, ...] uit sheet1."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        with z.open("xl/sharedStrings.xml") as f:
            strings = [el.text or "" for el in ET.parse(f).getroot().findall(f".//{ns}t")]
        with z.open("xl/worksheets/sheet1.xml") as f:
            root = ET.parse(f).getroot()
    rows: list[dict] = []
    max_r = 0
    for row in root.findall(f".//{ns}row"):
        r = int(row.attrib["r"])
        max_r = max(max_r, r)
        cells: dict[str, Any] = {"_row": r}
        for c in row.findall(f"{ns}c"):
            ref = c.attrib.get("r", "")
            t   = c.attrib.get("t")
            v   = c.find(f"{ns}v")
            if v is None:
                continue
            val: Any = v.text
            if t == "s":
                val = strings[int(val)]
            else:
                try: val = float(val)
                except (TypeError, ValueError): pass
            cells[_col_letter(ref)] = val
        rows.append(cells)
    rows.sort(key=lambda r: r["_row"])
    return rows

def _num(x: Any) -> float:
    return float(x) if isinstance(x, (int, float)) else 0.0

def load_from_excel(path: str) -> dict:
    """
    Leest de omzetrapportage. Output-structuur:
    {
      "months": [...15...],
      "cat_per_month": {"MA":[...], "SLA":[...], "WB":[...], "OV":[...], "IK":[...]},
      "total_per_month": [...],       # grand total (alle categorieën, incl IK)
      "net_per_month":   [...],       # excl IK (= MA+SLA+WB+OV)
      "ik_per_month":    [...],
      "clients": [
        {"name", "total", "monthly":[...15...], "by_category": {...}}
      ],
      "unknown_groups": {...}         # voor debugging
    }
    """
    rows = _parse_xlsx(path)
    cat_per_month: dict[str, list[float]] = {c: [0.0]*15 for c in CATEGORIES_META}
    # client_data["Klantnaam"] -> {"monthly":[..15..], "by_category":{..5..}, "total":float}
    client_data: dict[str, dict] = {}
    unknown_groups: dict[str, float] = defaultdict(float)

    current_cat: str | None = None   # huidige sectie (MA/SLA/WB/OV/IK)
    current_group_name: str = ""

    for row in rows:
        r = row["_row"]
        a = row.get("A")
        if r in (1, 2):  # header rij + grand total rij — overslaan
            continue
        if not isinstance(a, str) or not a.strip():
            continue

        if a in KNOWN_CATEGORY_NAMES:
            # Categorie-header rij — zelf telt mee als groep-subtotaal in Excel,
            # maar wij willen alleen klantregels optellen om dubbeltelling te
            # voorkomen. We registreren wel welke categorie de volgende rijen
            # zullen hebben.
            current_cat = categorize(a)
            current_group_name = a
            # Toch optellen op categorie-niveau (de Excel-headerregel ZELF bevat
            # soms een bedrag dat niet onder een client staat — bv. "Algemeen"
            # zonder onderverdeling). We tellen die optellingen apart NIET op,
            # behalve als er onder deze header geen klantregels verschijnen
            # met dezelfde subtotalen. Veiliger: alleen klantregels.
            continue

        # Geen header → klantregel onder de huidige categorie
        if current_cat is None:
            unknown_groups["(geen categorie-context)"] += sum(_num(row.get(c)) for c in EXCEL_MONTH_COLS)
            continue

        # Klantnaam = alles vóór ' - Werkzaamheden' / ' - Marketing werkzaamh.' / etc.
        line_label = a.strip()
        client_name = line_label.split(" - ", 1)[0].strip() if " - " in line_label else line_label

        monthly_vals = [_num(row.get(c)) for c in EXCEL_MONTH_COLS]
        if not any(monthly_vals):
            continue

        # cat_per_month optellen
        for i, v in enumerate(monthly_vals):
            cat_per_month[current_cat][i] += v

        # client_data bijwerken
        if client_name not in client_data:
            client_data[client_name] = {
                "name": client_name,
                "monthly": [0.0]*15,
                "by_category": {c: 0.0 for c in CATEGORIES_META},
                "total": 0.0,
            }
        for i, v in enumerate(monthly_vals):
            client_data[client_name]["monthly"][i] += v
            client_data[client_name]["total"] += v
        client_data[client_name]["by_category"][current_cat] += sum(monthly_vals)

    # Hertelconsistentie: corrigeer "Algemeen"-achtige headers zonder klantregel
    # door categorie-totalen te kruisvergelijken met de grand-total in row 2.
    grand_row = next((r for r in rows if r["_row"] == 2), None)
    excel_grand = [_num(grand_row.get(c)) for c in EXCEL_MONTH_COLS] if grand_row else [0.0]*15
    computed = [sum(cat_per_month[c][i] for c in CATEGORIES_META) for i in range(15)]

    # Verschil = bedragen die in een categorie-headerrij stonden zonder klantonderverdeling
    # (bv. row 3 "Algemeen" Jan-25 had 31286.54 zonder klantregels). Voeg toe aan OV.
    for i in range(15):
        diff = excel_grand[i] - computed[i]
        if abs(diff) > 0.5:
            cat_per_month["OV"][i] += diff
            # Voeg ook toe aan een synthetic 'Diversen/Algemeen' klant zodat het
            # bedrag ergens terechtkomt en niet uit de top-15 lekt.
            name = "Algemeen / niet-toegewezen"
            if name not in client_data:
                client_data[name] = {"name": name, "monthly": [0.0]*15,
                                     "by_category": {c: 0.0 for c in CATEGORIES_META}, "total": 0.0}
            client_data[name]["monthly"][i] += diff
            client_data[name]["total"] += diff
            client_data[name]["by_category"]["OV"] += diff

    total_per_month = [sum(cat_per_month[c][i] for c in CATEGORIES_META) for i in range(15)]
    ik_per_month    = list(cat_per_month["IK"])
    net_per_month   = [total_per_month[i] - ik_per_month[i] for i in range(15)]

    clients = sorted(client_data.values(), key=lambda c: -c["total"])
    return {
        "months": EXCEL_PERIOD,
        "cat_per_month": cat_per_month,
        "total_per_month": total_per_month,
        "net_per_month": net_per_month,
        "ik_per_month": ik_per_month,
        "clients": clients,
        "unknown_groups": dict(unknown_groups),
    }


# ============================================================================
# BRON 2 — SIMPLICATE API
# ============================================================================

import requests

BASE_URL = f"https://{SUBDOMAIN}.simplicate.nl/api/v2"

def api_get(path: str, params: dict | None = None) -> list[dict]:
    if not (API_KEY and API_SECRET and SUBDOMAIN):
        sys.exit(
            "FOUT: SIMPLICATE_API_KEY en SIMPLICATE_API_SECRET zijn niet gezet.\n"
            "Zet ze als environment variable, bv:\n"
            "    export SIMPLICATE_SUBDOMAIN=\"purplemedia\"\n"
            "    export SIMPLICATE_API_KEY=\"...\"\n"
            "    export SIMPLICATE_API_SECRET=\"...\"\n"
            "Permanent: voeg deze regels toe aan ~/.zshrc."
        )
    headers = {"Authentication-Key": API_KEY, "Authentication-Secret": API_SECRET,
               "Content-Type": "application/json"}
    params = dict(params or {})
    results: list[dict] = []
    offset = 0
    limit = 100
    while True:
        params["offset"] = offset
        params["limit"]  = limit
        r = requests.get(f"{BASE_URL}{path}", headers=headers, params=params, timeout=60)
        if r.status_code != 200:
            sys.exit(f"FOUT: API call faalt ({r.status_code}) {path}\n{r.text[:500]}")
        batch = r.json().get("data", [])
        results.extend(batch)
        if len(batch) < limit: break
        offset += limit
        time.sleep(0.1)
    return results

def _parse_invoice_date(inv: dict) -> date | None:
    raw = inv.get("date") or inv.get("invoice_date")
    if not raw: return None
    try: return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError: return None

def load_hours_from_api() -> dict | None:
    """
    Haalt uren-registratie op uit /hours/hours en aggregeert per maand.
    Returnt None als endpoint niet beschikbaar/uitgezet (HOURS_SKIP=1).

    Aannames over veldnamen (Simplicate v2; aanpassen na verificatie):
      - record["start_date"] of record["date"]  : YYYY-MM-DD (of met tijd)
      - record["hours"]                          : decimal aantal uren
      - record["tariff"]                         : euro/uur (>0 ⇒ declarabel)
      - record["service"]["name"]                : service-naam voor categorisering
      - record["employee"]["name"]               : medewerker
    Als velden ontbreken: probeer fallbacks; sla record over zonder te crashen.

    Output:
      {
        "declarable_per_month": [hours per maand met tariff>0],
        "total_per_month":      [hours per maand totaal],
        "inkoop_uren_per_month":[hours per maand voor services in CAT_IK],
        "wb_uren_per_month":    [hours per maand voor services in CAT_WB],
      }
    """
    if os.environ.get("HOURS_SKIP") == "1":
        print("  → Uren-fetch overgeslagen (HOURS_SKIP=1).")
        return None
    months = all_month_keys()
    midx = {m: i for i, m in enumerate(months)}
    n = len(months)
    decl  = [0.0] * n
    total = [0.0] * n
    ik_u  = [0.0] * n
    wb_u  = [0.0] * n

    print(f"  → Uren ophalen via /hours/hours ({PERIOD_START} t/m {PERIOD_END})...")
    try:
        records = api_get("/hours/hours", {
            "q[start_date][ge]": PERIOD_START.isoformat(),
            "q[start_date][le]": PERIOD_END.isoformat(),
            "sort": "start_date",
        })
    except SystemExit:
        # Endpoint kan een andere parameter-naam vereisen — probeer 'date'
        print("  → Eerste poging faalt, retry met q[date][ge]/[le]...")
        try:
            records = api_get("/hours/hours", {
                "q[date][ge]": PERIOD_START.isoformat(),
                "q[date][le]": PERIOD_END.isoformat(),
                "sort": "date",
            })
        except SystemExit:
            print("  ⚠ /hours/hours endpoint niet bereikbaar — sla uren over.")
            return None

    print(f"  → {len(records)} uur-records opgehaald.")
    skipped = 0
    for rec in records:
        # Datum extractie
        raw_date = rec.get("start_date") or rec.get("date") or rec.get("date_time")
        if not raw_date:
            skipped += 1
            continue
        try:
            d = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            skipped += 1
            continue
        if not (PERIOD_START <= d <= PERIOD_END):
            continue
        mk = month_key(d); i = midx.get(mk)
        if i is None:
            continue

        # Aantal uren
        h = rec.get("hours")
        if h is None:
            h = rec.get("amount") or rec.get("quantity") or 0
        try: h = float(h or 0)
        except (TypeError, ValueError): h = 0.0
        if h == 0:
            continue

        # Declarabel: gebruik `billable` boolean als primaire bron
        # (record kan tariff hebben maar toch niet-declarabel zijn — interne uren).
        billable_field = rec.get("billable")
        if billable_field is None:
            billable_field = rec.get("is_billable")
        if billable_field is not None:
            is_billable = bool(billable_field)
        else:
            # Geen explicit billable flag → val terug op tariff > 0
            tariff = rec.get("tariff")
            try: tariff = float(tariff or 0)
            except (TypeError, ValueError): tariff = 0.0
            is_billable = tariff > 0

        # Categorisering via type.label ("Development", "Service", "Support",
        # "Inkoop", …) — matcht onze CAT_* sets.
        sname = ""
        typ = rec.get("type")
        if isinstance(typ, dict):
            sname = typ.get("label") or ""
        if not sname:
            svc = rec.get("service")
            if isinstance(svc, dict):
                sname = svc.get("name") or ""
        cat = categorize(sname)

        total[i] += h
        if is_billable:
            decl[i] += h
        if cat == "IK":
            ik_u[i] += h
        elif cat == "WB":
            wb_u[i] += h

    if skipped:
        print(f"  ⚠ {skipped} records overgeslagen (datum ontbreekt/onparseerbaar).")
    return {
        "declarable_per_month":   [round(v, 2) for v in decl],
        "total_per_month":        [round(v, 2) for v in total],
        "inkoop_uren_per_month":  [round(v, 2) for v in ik_u],
        "wb_uren_per_month":      [round(v, 2) for v in wb_u],
    }


def load_from_api() -> dict:
    print(f"  → Facturen ophalen ({PERIOD_START} t/m {PERIOD_END})...")
    invoices = api_get("/invoices/invoice", {
        "q[date][ge]": PERIOD_START.isoformat(),
        "q[date][le]": PERIOD_END.isoformat(),
        "sort": "date",
    })
    print(f"  → {len(invoices)} facturen opgehaald.")

    months = all_month_keys()
    midx = {m: i for i, m in enumerate(months)}
    cat_per_month: dict[str, list[float]] = {c: [0.0]*len(months) for c in CATEGORIES_META}
    client_data: dict[str, dict] = {}

    for inv in invoices:
        d = _parse_invoice_date(inv)
        if not d or not (PERIOD_START <= d <= PERIOD_END): continue
        mk = month_key(d); i = midx.get(mk)
        if i is None: continue

        org = inv.get("organization") or {}
        person = inv.get("person") or {}
        client_name = (org.get("name") if org else None) \
                   or (person.get("full_name") if person else None) \
                   or "Onbekend"

        for line in inv.get("invoice_lines", []) or []:
            # Bedrag per regel = amount × price (amount is aantal uren/eenheden,
            # price is €/eenheid). Dit is de echte regel-omzet excl. BTW.
            try:
                amount = float(line.get("amount") or 0)
                price  = float(line.get("price")  or 0)
                amt = amount * price
            except (TypeError, ValueError):
                amt = 0.0
            if amt == 0: continue

            # Categorisering via revenue_group.label (komt overeen met
            # de groep-headers uit de omzetrapportage-Excel).
            sname = ""
            rg = line.get("revenue_group")
            if isinstance(rg, dict):
                sname = rg.get("label") or ""
            if not sname:
                sname = line.get("description") or ""

            cat = categorize(sname)
            cat_per_month[cat][i] += amt

            if client_name not in client_data:
                client_data[client_name] = {"name": client_name,
                                             "monthly": [0.0]*len(months),
                                             "by_category": {c: 0.0 for c in CATEGORIES_META},
                                             "total": 0.0}
            client_data[client_name]["monthly"][i] += amt
            client_data[client_name]["total"] += amt
            client_data[client_name]["by_category"][cat] += amt

    total_per_month = [sum(cat_per_month[c][i] for c in CATEGORIES_META) for i in range(len(months))]
    ik_per_month    = list(cat_per_month["IK"])
    net_per_month   = [total_per_month[i] - ik_per_month[i] for i in range(len(months))]
    clients = sorted(client_data.values(), key=lambda c: -c["total"])

    # Fase 2: uren ophalen voor bezetting + inkoop% (optioneel; faalt graceful)
    hours = load_hours_from_api()

    return {
        "months": months, "cat_per_month": cat_per_month,
        "total_per_month": total_per_month, "net_per_month": net_per_month,
        "ik_per_month": ik_per_month, "clients": clients, "unknown_groups": {},
        "hours": hours,
    }


# ============================================================================
# DATASET → DATA.JSON
# ============================================================================

def build_payload(agg: dict, source: str) -> dict:
    months = agg["months"]
    categories = {}
    for code, meta in CATEGORIES_META.items():
        monthly = [round(v, 2) for v in agg["cat_per_month"][code]]
        categories[code] = {
            "label": meta["label"],
            "color": meta["color"],
            "monthly": monthly,
            "total": round(sum(monthly), 2),
        }

    clients_out = []
    for c in agg["clients"]:
        clients_out.append({
            "name": c["name"],
            "is_partner": c["name"] in KANAALPARTNERS,
            "total": round(c["total"], 2),
            "monthly": [round(v, 2) for v in c["monthly"]],
            "by_category": {k: round(v, 2) for k, v in c["by_category"].items()},
        })

    payload = {
        "meta": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "period_start": months[0],
            "period_end":   months[-1],
            "fte": FTE,
            "uur_tarief_eur": UUR_TARIEF_EUR,
            "uur_per_fte_per_maand": UUR_PER_FTE_MAAND,
            "max_capacity_per_maand": MAX_CAPACITY,
            "prices_excl_btw": True,
            "category_order": ["MA", "SLA", "WB", "OV", "IK"],
        },
        "months": months,
        "categories": categories,
        "total_per_month": [round(v, 2) for v in agg["total_per_month"]],
        "net_per_month":   [round(v, 2) for v in agg["net_per_month"]],
        "ik_per_month":    [round(v, 2) for v in agg["ik_per_month"]],
        "clients": clients_out,
    }
    # Optionele uren-data (alleen bij --source=api als endpoint reageerde)
    if agg.get("hours"):
        h = agg["hours"]
        capacity_per_month = round(FTE * UUR_PER_FTE_MAAND)  # uren beschikbaar
        bezetting_per_month = [
            round(h["declarable_per_month"][i] / capacity_per_month * 100, 1)
            for i in range(len(months))
        ]
        # Inkoop-uren als % van WB-uren (mirror van huidige IP-definitie)
        inkoop_pct_per_month = [
            round(h["inkoop_uren_per_month"][i] / h["wb_uren_per_month"][i] * 100, 1)
            if h["wb_uren_per_month"][i] > 0 else 0
            for i in range(len(months))
        ]
        payload["hours"] = {
            "declarable_per_month": h["declarable_per_month"],
            "total_per_month":      h["total_per_month"],
            "inkoop_uren_per_month": h["inkoop_uren_per_month"],
            "wb_uren_per_month":     h["wb_uren_per_month"],
            "capacity_per_month":    capacity_per_month,
            "bezetting_per_month":   bezetting_per_month,
            "inkoop_pct_per_month":  inkoop_pct_per_month,
        }
    return payload


# ============================================================================
# CLI / REPORTING
# ============================================================================

def print_summary(agg: dict) -> None:
    months = agg["months"]
    print("\n  Maandoverzicht (afgerond op €1):")
    hdr = f"    {'Maand':<10}" + "".join(f"{c:>10}" for c in ("MA","SLA","WB","OV","IK","TOT")) + f"{'NET':>10}"
    print(hdr)
    for i, m in enumerate(months):
        ma  = round(agg["cat_per_month"]["MA"][i])
        sla = round(agg["cat_per_month"]["SLA"][i])
        wb  = round(agg["cat_per_month"]["WB"][i])
        ov  = round(agg["cat_per_month"]["OV"][i])
        ik  = round(agg["cat_per_month"]["IK"][i])
        tot = round(agg["total_per_month"][i])
        net = round(agg["net_per_month"][i])
        print(f"    {m:<10}{ma:>10}{sla:>10}{wb:>10}{ov:>10}{ik:>10}{tot:>10}{net:>10}")
    # Totalen
    tots = {k: round(sum(agg["cat_per_month"][k])) for k in CATEGORIES_META}
    grand = round(sum(agg["total_per_month"]))
    netg  = round(sum(agg["net_per_month"]))
    print(f"    {'TOTAAL':<10}{tots['MA']:>10}{tots['SLA']:>10}{tots['WB']:>10}{tots['OV']:>10}{tots['IK']:>10}{grand:>10}{netg:>10}")

    print("\n  Top 15 klanten:")
    for i, c in enumerate(agg["clients"][:15], 1):
        print(f"    {i:>2}. {c['name'][:55]:<55} €{round(c['total']):>10,}")

    if agg.get("unknown_groups"):
        print("\n  Onbekende posten (controle):")
        for n, v in sorted(agg["unknown_groups"].items(), key=lambda x:-x[1])[:10]:
            print(f"    €{round(v):>10,}  {n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["excel","api"], default="excel",
                    help="databron (default: excel)")
    ap.add_argument("--excel", default=DEFAULT_EXCEL,
                    help=f"pad naar omzetrapportage xlsx (default: {DEFAULT_EXCEL})")
    ap.add_argument("--json",  dest="json_path", default=DEFAULT_JSON,
                    help=f"output JSON-pad (default: {DEFAULT_JSON})")
    ap.add_argument("--dry-run", action="store_true",
                    help="alleen samenvatting tonen, geen JSON wegschrijven")
    args = ap.parse_args()

    print("=" * 70)
    print("Purple Media Dashboard — data.json builder")
    print("=" * 70)
    print(f"Bron     : {args.source}")
    if args.source == "excel":
        print(f"Excel    : {args.excel}")
    print(f"Output   : {args.json_path} ({'dry-run' if args.dry_run else 'wegschrijven'})")
    print()

    if args.source == "excel":
        if not os.path.exists(args.excel):
            sys.exit(f"FOUT: Excel niet gevonden: {args.excel}")
        agg = load_from_excel(args.excel)
    else:
        agg = load_from_api()

    print_summary(agg)
    payload = build_payload(agg, source=args.source)

    if args.dry_run:
        print(f"\n  → DRY RUN: {args.json_path} niet weggeschreven.")
    else:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size = os.path.getsize(args.json_path)
        print(f"\n  → Geschreven: {args.json_path} ({size:,} bytes)")
    print("\nKlaar.")


if __name__ == "__main__":
    main()
