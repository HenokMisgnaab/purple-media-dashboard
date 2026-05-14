# Purple Media Dashboard

Interactief bedrijfsdashboard voor Purple Media-management. Toont
omzet, klanten en bezetting met flexibele periode-vergelijking,
filters, klant-drill-down en automatische insights.

## Architectuur

```
                     update_dashboard.py
   ┌───────────────────────┴───────────────────────┐
   │                                               │
   ▼                                               ▼
Excel-export                                Simplicate v2 API
(omzetrapportage)                           (/invoices/invoice)
   │                                               │
   └───────────────────────┬───────────────────────┘
                           ▼
                       data.json
                           │
                           ▼
            purple_media_dashboard.html
            (fetch → Chart.js → DOM)
```

- **`update_dashboard.py`** — leest een Excel-omzetrapportage óf trekt
  facturen via de Simplicate v2 API, categoriseert per service en schrijft
  `data.json`.
- **`data.json`** — bevat per maand: totale omzet, omzet per categorie
  (MA / SLA / WB / OV / IK), netto omzet, en per klant: maandelijkse omzet
  + service-mix. Plus meta (FTE, capaciteit, uurtarief).
- **`purple_media_dashboard.html`** — single-file frontend. Doet `fetch('data.json')`,
  rendert alle KPI's, charts (Chart.js v4), tabellen en insights uit die
  data. Bevat de hele interactie-laag (periode-selector, filters,
  vergelijkings-modus, drill-down).

## Features

| Tab | Inhoud |
|---|---|
| **Omzet** | Totale & netto omzet, maandelijkse stacked-bar per categorie, % per categorie over tijd, MoM-groei, donut, kwartaal-overzicht, abo-trend, forecast met R²-fit |
| **Klanten** | Top-15 balken (sorteerbaar per segment), omzetbanden-tabel, klantloyaliteit-buckets, HHI-concentratie-index met uitleg, drill-down panel per klant |
| **Capaciteit** | Bezetting per maand, netto vs. plafond, inkoop% per maand, productiviteitsanalyse |
| **Signalen** | Abo run rate, recurring%, kanaalpartners, groeiers/dalers, strategische samenvatting |

### Interactieve elementen

- **Periode-selector**: presets (laatste N maanden, YTD, kwartalen, hele
  periode) of custom range (from–to dropdowns)
- **Vergelijkings-modus** (Periode A vs B): voorgaande gelijke periode,
  zelfde periode vorig jaar, of custom; alle KPI's krijgen delta-badges
- **Categorie-filters** (5 pillen): MA / SLA / WB / OV / IK individueel
  in/uit te schakelen
- **Klant-segment-filter**: top-5/15/30, long-tail, of per omzetband
- **Klant-drill-down**: klik op een klant in top-15 → side-panel met
  kerncijfers, service-mix donut, maandelijkse omzet, vergelijking met
  Periode B (indien actief)

## Setup

### Eénmalig

```bash
# Python dependencies (alleen voor update_dashboard.py)
pip3 install requests openpyxl
```

### data.json genereren

**Vanuit Excel (default, snelste pad):**
```bash
python3 update_dashboard.py
```

Verwacht `Export+van+omzetrapportage-*.xlsx` in dezelfde map (of geef pad
mee met `--excel`).

**Vanuit Simplicate API** (live data, vereist credentials):
```bash
export SIMPLICATE_SUBDOMAIN="purplemedia"
export SIMPLICATE_API_KEY="..."
export SIMPLICATE_API_SECRET="..."
python3 update_dashboard.py --source=api
```

API-keys worden uitsluitend via environment variables gelezen — **nooit
in code committen**. Een nieuwe key maak je in Simplicate via
*Settings → General → API*.

**Dry-run** (zien wat er zou worden geschreven, zonder iets te wijzigen):
```bash
python3 update_dashboard.py --dry-run
```

### Dashboard openen

`fetch('data.json')` werkt niet via `file://` (CORS). Start een lokale
webserver in de projectmap:

```bash
python3 -m http.server 8080
```

Open daarna <http://localhost:8080/purple_media_dashboard.html>.

## Tests

Headless regressie-tests (jsdom) draaien in onder een seconde en dekken
zowel rendering als interactie:

```bash
cd tests
npm install
npm test
```

Zie [`tests/README.md`](tests/README.md) voor wat precies wordt getest.

Draai deze na elke aanpassing aan de HTML/JS — ze vangen 36 manieren waarop
de UI stuk kan gaan (missende DOM-elementen, vertaal-fouten in JS, broken
filters, lege KPI's, runtime-errors).

## Categorisering

De 5 categorieën worden bovenin `update_dashboard.py` bepaald op basis
van service-naam in Simplicate. Onbekende services vallen automatisch in
**Overig** en worden in dry-run output gelogd — daar kun je nieuwe
services aan de juiste categorie toevoegen.

| Categorie | Inhoud | Kleur |
|---|---|---|
| **MA** Marketing abo | Alle `(abonnement)`-services + Online/E-mail Marketing + SMA | `#7c6ef7` paars |
| **SLA** Service | Service + Support (recurring servicewerk) | `#2dd4a7` teal |
| **WB** Website | Development (project-werk) | `#3b82f6` blauw |
| **OV** Overig | Algemeen, Creatie, Projectmanagement, Strategie, onbekend | `#4b5563` grijs |
| **IK** Inkoop | Inkoop + `Inkoop (abonnement)` (pass-through kosten) | `#f5a623` amber |

## Capaciteits-aannames

Bovenin `update_dashboard.py`:
- `FTE = 9.5`
- `UUR_PER_FTE_PER_MAAND = 120`
- `UUR_TARIEF_EUR = 110`
- `MAX_CAPACITY` = 9,5 × 120 × €110 = €125.400 / maand

Worden naar `data.json` geschreven zodat de frontend ze kent. Pas aan
als het team groeit of het tarief wijzigt.

## Datagevoeligheid

`data.json` en de Excel-export bevatten **klantnamen + maandelijkse
omzet per klant**. Bij sharing of git-hosting:

- **Repository moet PRIVATE zijn** als de echte data wordt meegeleverd.
- **GitHub Pages op private repos** vereist GitHub Pro (€4/mnd) of
  Organization Team-tier.
- Alternatief: een geanonimiseerde variant van `data.json` checken in en
  de echte versie lokaal houden.

## Bestandsstructuur

```
.
├── purple_media_dashboard.html   # Single-file frontend
├── data.json                     # Genereerd door update_dashboard.py
├── update_dashboard.py           # Excel / API → data.json
├── Export+van+omzetrapportage-*.xlsx   # Brondata (excel-mode)
├── tests/
│   ├── smoke.js                  # 16 baseline checks
│   ├── interactive.js            # 20 interactie-checks
│   ├── package.json
│   └── README.md
├── .gitignore
└── README.md
```

## Roadmap

- [x] data-laag: Excel + API → data.json met 5 categorieën
- [x] dynamische rendering: alle charts en KPI's uit data.json
- [x] periode-selector + presets + custom range
- [x] vergelijkings-modus (Periode A vs B) met delta-badges
- [x] categorie- en segment-filters
- [x] klant-drill-down side panel
- [x] auto-insights (HHI, omzetbanden, capaciteit, strategisch, groeiers/dalers)
- [x] forecast: lineaire regressie met R²-fit en adaptive horizon
- [x] headless regressie-tests (36 checks)
- [ ] `/hours/hours` integratie voor uren-gebaseerde bezetting & inkoop%
- [ ] GitHub-deployment (private repo + Pages)
