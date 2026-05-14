# Purple Media Dashboard – Simplicate API Koppeling (Fase 1)

Dit script haalt facturatie-data op uit Simplicate en update automatisch
de cijfers in `purple_media_dashboard.html`.

## Wat het script doet (Fase 1)

Vervangt automatisch:

- **T** – totale omzet per maand
- **MA** – Marketing abo per maand
- **SL** – SLA per maand
- **WB** – Website per maand
- **OV** – Overig per maand
- **clients** – top-15 klanten + percentages
- Donut totalen (cDonut)
- Kwartaal totalen (cKwartaal)
- Klant-loyalty buckets (cLoyalty)

## Wat het script (nog) NIET doet

Voor Fase 2:

- `BZ` (bezetting %), `IK` (inkoop-uren), `IP` (inkoop-%) – komen uit `/hours/hours`
- Groeiers/dalers (`gr` en `da` arrays) – vereist periode-vergelijking
- Insight-teksten (de gekleurde balkjes met inzichten) – die zijn nog handmatig

## Installatie

### 1. Python installeren

Mac: Python 3.10+ is meestal al aanwezig. Check met:
```bash
python3 --version
```
Anders: <https://www.python.org/downloads/>

### 2. Dependencies installeren

In Terminal, in de map waar dit script staat:
```bash
pip3 install requests
```

### 3. API key aanmaken in Simplicate

1. Log in op Simplicate.
2. Ga naar **Settings → General → API**.
3. Klik **Nieuwe API key**.
4. Geef de key een naam (bv. "Dashboard sync") en kies een gebruiker met
   voldoende rechten (in elk geval lezen van facturen en organisaties).
5. Kopieer **API Key** en **API Secret** – die zie je maar één keer.

### 4. Credentials instellen

**Optie A – Bovenin `update_dashboard.py` invullen:**

```python
SUBDOMAIN  = "JOUW_SUBDOMEIN"   # bv. "purplemedia" als je URL purplemedia.simplicate.nl is
API_KEY    = "JOUW_API_KEY"
API_SECRET = "JOUW_API_SECRET"
```

**Optie B – Environment variables (veiliger, vooral als je dit deelt):**

Mac/Linux Terminal:
```bash
export SIMPLICATE_SUBDOMAIN="purplemedia"
export SIMPLICATE_API_KEY="..."
export SIMPLICATE_API_SECRET="..."
```

Voor permanent op je Mac: voeg deze regels toe aan `~/.zshrc`.

## Gebruik

Zet `update_dashboard.py` in dezelfde map als `purple_media_dashboard.html`.

### Stap 1: Dry-run (zonder HTML te wijzigen)

```bash
python3 update_dashboard.py --dry-run
```

Dit toont een tabel met alle maandbedragen per categorie en de top-15 klanten,
zónder iets in de HTML te veranderen. **Vergelijk deze cijfers met je huidige
dashboard** voordat je verder gaat. Let vooral op:

- Klopt het maandtotaal (laatste regel "TOTAAL") ongeveer met wat je verwacht?
- Staan de juiste klanten in de top-15?
- Onderaan staat een lijstje "Services in categorie 'Overig'" – check of
  daar geen service in staat die eigenlijk in MA/SLA/WB hoort.

### Stap 2: Categorisering controleren

Als je in de output ziet dat bijvoorbeeld een nieuwe service `"Nieuwsbrief
(abonnement)"` onder Overig valt terwijl je hem onder Marketing abo wilt:
open `update_dashboard.py` en voeg de naam toe aan `CAT_MARKETING_ABO`:

```python
CAT_MARKETING_ABO = {
    "All-in-One Marketing (abonnement)",
    "SEO (abonnement)",
    ...
    "Nieuwsbrief (abonnement)",   # ← nieuw
}
```

### Stap 3: HTML daadwerkelijk updaten

```bash
python3 update_dashboard.py
```

Er wordt eerst een backup gemaakt: `purple_media_dashboard.html.bak`.
Open daarna `purple_media_dashboard.html` in je browser om te zien
of alles klopt. Als het mis is, herstel met:

```bash
cp purple_media_dashboard.html.bak purple_media_dashboard.html
```

## Periode aanpassen

In `update_dashboard.py` bovenaan:

```python
PERIOD_START = date(2025, 1, 1)
PERIOD_END   = date(2026, 3, 31)
```

Pas aan voor een andere periode. Let op: de HTML toont 15 maanden in
labels (`Jan 25` t/m `Mrt 26`). Als je periode langer/korter wordt,
moet je ook de `M` array in de HTML aanpassen, anders krijg je
mismatchende labels.

## Wat als de cijfers niet kloppen?

Meest waarschijnlijke oorzaken, in volgorde:

1. **Service-namen wijken af** – check de "Overig"-lijst in dry-run output
   en pas de categorie-sets aan.
2. **Datum in Simplicate vs. in CSV** – Simplicate API geeft `invoice_date`;
   de CSV-rapportage gebruikt mogelijk een andere datumdefinitie
   (factuurdatum vs. levermaand). Verschil tussen maanden is dan normaal,
   jaartotaal moet wél kloppen.
3. **BTW** – het script werkt met regelbedragen ex BTW. Als jouw CSV
   inclusief BTW was, krijg je 21% lagere cijfers.
4. **Concept-facturen** – `/invoices/invoice` levert standaard alle statussen.
   Wil je alleen definitieve? Voeg een filter toe: `q[status]=invoiced` of
   filter in `aggregate()` op `inv.get("status")`.

## Automatisch laten draaien

Als handmatig draaien gaat werken en je wilt het later automatiseren
(elke nacht/week): macOS heeft `launchd`, Windows heeft Task Scheduler.
Niet nodig voor Fase 1.
