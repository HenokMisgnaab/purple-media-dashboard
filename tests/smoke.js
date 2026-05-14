#!/usr/bin/env node
// Headless smoke-test voor Purple Media Dashboard.
// Mockt Chart + canvas, levert data.json via gemockte fetch, runt JS,
// en leest de gerenderde DOM af.

const { JSDOM, VirtualConsole } = require('jsdom');
const fs   = require('fs');
const path = require('path');

const PROJ = path.resolve(__dirname, '..');
const htmlText = fs.readFileSync(path.join(PROJ, 'purple_media_dashboard.html'), 'utf8');
const dataObj  = JSON.parse(fs.readFileSync(path.join(PROJ, 'data.json'), 'utf8'));

// Strip de Chart.js CDN script — we mocken Chart zelf
const htmlNoCDN = htmlText.replace(
  /<script src="https:\/\/cdnjs[^"]+"[^>]*><\/script>/,
  ''
);

const errors = [];
const warnings = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push('jsdomError: ' + (e.message || e)));
vc.on('error', (...a) => errors.push('console.error: ' + a.join(' ')));
vc.on('warn',  (...a) => warnings.push('console.warn: ' + a.join(' ')));

const dom = new JSDOM(htmlNoCDN, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(win) {
    // Mock Chart constructor & defaults
    function Chart() { return { destroy() {}, update() {}, data: {}, options: {} }; }
    Chart.defaults = { color: '', borderColor: '', font: {} };
    win.Chart = Chart;

    // Mock fetch — geef data.json terug
    win.fetch = () => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(dataObj),
    });

    // Mock canvas.getContext zodat eventuele directe canvas-calls niet crashen
    win.HTMLCanvasElement.prototype.getContext = function () {
      return { fillRect() {}, clearRect() {}, getImageData() { return { data: [] }; },
               putImageData() {}, createImageData() { return []; }, setTransform() {},
               drawImage() {}, save() {}, fillText() {}, restore() {}, beginPath() {},
               moveTo() {}, lineTo() {}, closePath() {}, stroke() {}, translate() {},
               scale() {}, rotate() {}, arc() {}, fill() {}, measureText() { return { width: 0 }; },
               transform() {}, rect() {}, clip() {} };
    };
  },
});

// Wachten op fetch + render (microtasks + macrotasks)
async function waitRender() {
  await new Promise(r => setTimeout(r, 100));
  // 2 keer omdat fetch een microtask is en setTimeout(0) een macrotask
  await new Promise(r => setTimeout(r, 100));
}

(async () => {
  await waitRender();
  const doc = dom.window.document;

  // ====== Assertions ======
  const checks = [];
  const expect = (label, actual, predicate, hint) => {
    const ok = predicate(actual);
    checks.push({ label, ok, actual: String(actual).slice(0, 80), hint: ok ? '' : hint });
  };

  // KPI's gevuld
  expect('kpi: totale omzet selectie',
    doc.getElementById('kpiTotal2025')?.textContent,
    v => /€[\d.,]+/.test(v || ''),
    'verwacht een €-bedrag, geen em-dash');
  expect('kpi: run rate',
    doc.getElementById('kpiRunRate2026')?.textContent,
    v => /€[\d.,]+/.test(v || ''),
    'verwacht een €-bedrag');
  expect('kpi: HHI',
    doc.getElementById('kpiHHI')?.textContent,
    v => /^\d+$/.test((v || '').trim()),
    'verwacht een geheel getal');
  expect('kpi: actieve klanten',
    doc.getElementById('kpiActieveKlanten')?.textContent,
    v => /^\d+$/.test((v || '').trim()),
    'verwacht aantal klanten als getal');
  expect('kpi: bezetting 2025',
    doc.getElementById('bez2025kpi')?.textContent,
    v => /\d+%/.test(v || ''),
    'verwacht percentage');

  // Top-klanten lijst gerenderd
  const cbItems = doc.querySelectorAll('#cBars .cb-item');
  expect('top-15 klanten balken',
    cbItems.length, n => n >= 10 && n <= 15,
    'verwacht 10–15 items');

  // Omzetbanden tabel gevuld
  const banden = doc.querySelectorAll('#omzetBanden tr');
  expect('omzetbanden tabel-rijen',
    banden.length, n => n === 5,
    'verwacht 5 banden (€0-1K, €1-5K, €5-15K, €15-50K, €50K+)');

  // Bezettingsrijen
  const bezRows = doc.querySelectorAll('#bezRows .bez-row');
  expect('bezetting-rijen',
    bezRows.length, n => n === dataObj.months.length,
    `verwacht ${dataObj.months.length} maanden, niet ${bezRows.length}`);

  // Insights gerenderd
  const banden_ins = doc.querySelectorAll('#insightsBanden .insight');
  const hhi_ins    = doc.querySelectorAll('#insightsHHI .insight');
  const cap_ins    = doc.querySelectorAll('#insightsCapaciteit .insight');
  const strat_ins  = doc.querySelectorAll('#insightsStrategic .insight');
  expect('insights — omzetbanden', banden_ins.length, n => n >= 1, 'verwacht ≥1 insight');
  expect('insights — HHI',          hhi_ins.length,    n => n >= 3, 'verwacht ≥3 insights');
  expect('insights — capaciteit',   cap_ins.length,    n => n >= 3, 'verwacht ≥3 insights');
  expect('insights — strategisch',  strat_ins.length,  n => n >= 4, 'verwacht ≥4 insights');

  // Periode-bar zichtbaar (hidden weggehaald) en meta gevuld
  const periodBar = doc.getElementById('periodBar');
  const periodMeta = doc.getElementById('periodMeta');
  expect('periode-bar zichtbaar',
    periodBar && !periodBar.hasAttribute('hidden'),
    v => v === true,
    'periodBar moet zichtbaar zijn na render');
  expect('periode-meta gevuld',
    periodMeta?.textContent,
    v => v && /maand/.test(v),
    'verwacht text als "X maanden · ..."');

  // Filter-pills gerenderd
  const pills = doc.querySelectorAll('.fb-pill[data-cat]');
  expect('filter-pills aanwezig',
    pills.length, n => n === 5,
    'verwacht 5 categorie-pills');

  // Console errors
  expect('JS — geen runtime errors', errors.length, n => n === 0,
    'errors: ' + errors.join(' | '));

  // ====== Rapport ======
  console.log('\nSmoke-test resultaat:');
  let pass = 0, fail = 0;
  for (const c of checks) {
    const sym = c.ok ? '✓' : '✗';
    console.log(`  ${sym} ${c.label}  →  ${c.actual}`);
    if (!c.ok) console.log(`     ↳ ${c.hint}`);
    c.ok ? pass++ : fail++;
  }
  console.log(`\nTotaal: ${pass}/${pass+fail} ok${warnings.length?` · ${warnings.length} warnings`:''}`);
  if (errors.length) {
    console.log('\nJS-errors gevangen:');
    errors.forEach(e => console.log('  -', e.slice(0, 200)));
  }
  process.exit(fail > 0 || errors.length > 0 ? 1 : 0);
})().catch(e => {
  console.error('test crash:', e.stack || e);
  process.exit(2);
});
