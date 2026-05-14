# Tests

Headless regressie-tests die de dashboard-JS volledig uitvoeren met een gemockt
`Chart`-object en gemockte `fetch`. Doel: voorkomen dat een edit aan
`purple_media_dashboard.html` de KPI's, charts, filters of drill-down stuk
maakt zonder dat het direct in de browser zichtbaar is.

## Eenmalige setup

```bash
cd tests
npm install
```

## Draaien

```bash
# Beide tests
npm test

# Alleen baseline (KPI's, charts, insights gerenderd)
npm run smoke

# Alleen interactie (periode-wissel, filters, vergelijking, drill-down)
npm run interactive
```

## Wat is gedekt

**`smoke.js`** — laadt de HTML + `data.json`, runt de inline JS, checkt 16
assertions:
- KPI's zijn met €-bedragen / getallen gevuld (geen `—`)
- Top-15 klanten balken gerenderd (15 items)
- Omzetbanden-tabel heeft 5 rijen
- Bezetting-rijen = aantal maanden in `data.json`
- Insights gerenderd (omzetbanden, HHI, capaciteit, strategisch)
- Periode-bar zichtbaar na initialisatie
- Filter-pills aanwezig (5 categorieën)
- Geen JS runtime-errors

**`interactive.js`** — simuleert gebruikersinteracties, 20 assertions:
- Periode-preset wisselen (bv. Q1 2026) → KPI's, meta en bezettingsrijen
  veranderen mee
- Categorie-filter (IK uitschakelen) → totaalomzet daalt
- Klant-segment filter (top5) → klant-lijst beperkt zich
- Vergelijkings-modus aanzetten → tweede periode wordt gevuld
- Custom range via from/to-selectors → juist aantal maanden
- Klant aanklikken → drill-down-panel met stats wordt zichtbaar
- Geen JS runtime-errors gedurende de hele flow

## Wat is NIET gedekt

- Visuele aspecten: layout, kleur, font, spacing, hover-states, animaties.
  Daarvoor: open `http://localhost:8080/purple_media_dashboard.html` in een
  browser.
- Chart.js teken-output zelf (mocked). De testen verifiëren dat `new Chart()`
  zonder errors wordt aangeroepen met geldige data, niet hoe de chart pixels
  eruitzien.
- Server-side gedrag van `update_dashboard.py`. Validatie van die output zit
  impliciet in deze tests omdat ze `data.json` lezen.
