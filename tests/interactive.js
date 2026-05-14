#!/usr/bin/env node
// Interactieve smoke-test: simuleert gebruiker die periode wisselt,
// filter toggled, vergelijkings-modus aanzet en klant aanklikt.

const { JSDOM, VirtualConsole } = require('jsdom');
const fs   = require('fs');
const path = require('path');

const PROJ = path.resolve(__dirname, '..');
const htmlText = fs.readFileSync(path.join(PROJ, 'purple_media_dashboard.html'), 'utf8');
const dataObj  = JSON.parse(fs.readFileSync(path.join(PROJ, 'data.json'), 'utf8'));

const htmlNoCDN = htmlText.replace(/<script src="https:\/\/cdnjs[^"]+"[^>]*><\/script>/, '');

const errors = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errors.push(e.message || String(e)));
vc.on('error', (...a) => errors.push(a.join(' ')));

const dom = new JSDOM(htmlNoCDN, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(win) {
    function Chart() { return { destroy() {}, update() {}, data: {}, options: {} }; }
    Chart.defaults = { color: '', borderColor: '', font: {} };
    win.Chart = Chart;
    win.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(dataObj) });
    win.HTMLCanvasElement.prototype.getContext = function () {
      return new Proxy({}, { get: () => () => ({ width: 0 }) });
    };
  },
});

const win = dom.window;
const doc = win.document;
const tick = () => new Promise(r => setTimeout(r, 50));

function fire(el, type) {
  el.dispatchEvent(new win.Event(type, { bubbles: true }));
}

function click(el) {
  el.dispatchEvent(new win.MouseEvent('click', { bubbles: true, cancelable: true }));
}

const results = [];
function check(label, ok, detail) {
  results.push({ label, ok, detail: String(detail).slice(0, 100) });
}

(async () => {
  // Wachten op fetch+render
  await tick(); await tick(); await tick();

  // ===== Baseline =====
  const baseTotal = doc.getElementById('kpiTotal2025')?.textContent;
  check('baseline: kpi totale omzet ingevuld', /€[\d.,]+/.test(baseTotal || ''), baseTotal);
  const baseClients = doc.querySelectorAll('#cBars .cb-item').length;
  check('baseline: 15 top-klanten', baseClients === 15, baseClients);

  // ===== TEST 1: Periode-preset wisselen naar Q1 2026 =====
  const presetSel = doc.getElementById('periodPreset');
  const q1Options = [...presetSel.options].filter(o => /Q1\s*2026/.test(o.textContent));
  check('TEST 1: Q1 2026 preset bestaat', q1Options.length === 1, q1Options.map(o=>o.textContent).join(','));
  if (q1Options.length) {
    presetSel.value = q1Options[0].value;
    fire(presetSel, 'change');
    await tick(); await tick();
    const newTotal = doc.getElementById('kpiTotal2025')?.textContent;
    const newMeta = doc.getElementById('periodMeta')?.textContent;
    check('TEST 1: KPI totale omzet veranderde na preset-wissel',
      newTotal !== baseTotal && /€[\d.,]+/.test(newTotal || ''),
      `${baseTotal} → ${newTotal}`);
    check('TEST 1: meta toont 3 maanden',
      /3 maanden/.test(newMeta || ''),
      newMeta);
    const q1Bez = doc.querySelectorAll('#bezRows .bez-row').length;
    check('TEST 1: bezetting-rijen = 3 (Q1)', q1Bez === 3, q1Bez);
  }

  // Reset naar hele periode voor volgende tests
  const allOpt = [...presetSel.options].find(o => o.value === 'all');
  if (allOpt) { presetSel.value = allOpt.value; fire(presetSel, 'change'); await tick(); await tick(); }

  // ===== TEST 2: Filter — categorie IK uitschakelen =====
  const ikPill = doc.querySelector('.fb-pill[data-cat="IK"]');
  check('TEST 2: IK-filter-pill bestaat', !!ikPill, !!ikPill);
  if (ikPill) {
    const beforeIK = doc.getElementById('kpiTotal2025')?.textContent;
    click(ikPill);
    await tick(); await tick();
    const afterIK = doc.getElementById('kpiTotal2025')?.textContent;
    check('TEST 2: omzet wijzigt na IK uitschakelen',
      beforeIK !== afterIK, `${beforeIK} → ${afterIK}`);
    check('TEST 2: pill heeft .on verloren',
      !ikPill.classList.contains('on'), [...ikPill.classList].join(','));
    // Aanzetten weer
    click(ikPill);
    await tick();
  }

  // ===== TEST 3: Klant-segment filter — top5 =====
  const segSel = doc.getElementById('filterSegment');
  check('TEST 3: segment-select bestaat', !!segSel, !!segSel);
  if (segSel) {
    const hasTop5 = [...segSel.options].some(o => o.value === 'top5');
    check('TEST 3: top5 optie bestaat', hasTop5, [...segSel.options].map(o=>o.value).join(','));
    if (hasTop5) {
      segSel.value = 'top5';
      fire(segSel, 'change');
      await tick(); await tick();
      const n = doc.querySelectorAll('#cBars .cb-item').length;
      check('TEST 3: na top5-filter ≤5 klanten in lijst', n <= 5 && n >= 1, n);
      // Reset
      segSel.value = 'all';
      fire(segSel, 'change');
      await tick();
    }
  }

  // ===== TEST 4: Vergelijkings-modus aanzetten =====
  const compareBtn = doc.getElementById('compareToggle');
  check('TEST 4: compare-toggle bestaat', !!compareBtn, !!compareBtn);
  if (compareBtn) {
    // Eerst: kies een korte periode (Q1 26) zodat er ruimte is voor periode B
    const q1Opt = [...presetSel.options].find(o => /Q1\s*2026/.test(o.textContent));
    if (q1Opt) { presetSel.value = q1Opt.value; fire(presetSel, 'change'); await tick(); }
    click(compareBtn);
    await tick(); await tick();
    const compareBar = doc.getElementById('compareBar');
    check('TEST 4: compare-bar zichtbaar',
      compareBar && compareBar.style.display !== 'none',
      compareBar?.style.display);
    const compareMeta = doc.getElementById('compareMeta')?.textContent;
    check('TEST 4: compare-meta gevuld',
      compareMeta && /maand/.test(compareMeta), compareMeta);
    // Reset
    click(compareBtn);
    await tick();
    if (allOpt) { presetSel.value = allOpt.value; fire(presetSel, 'change'); await tick(); }
  }

  // ===== TEST 5: Custom range via from/to =====
  const fromSel = doc.getElementById('periodFrom');
  const toSel = doc.getElementById('periodTo');
  if (fromSel && toSel && fromSel.options.length >= 6) {
    fromSel.value = '0';
    toSel.value = '5';
    fire(fromSel, 'change');
    await tick(); await tick();
    const n = doc.querySelectorAll('#bezRows .bez-row').length;
    check('TEST 5: custom range 0-5 toont 6 maanden', n === 6, n);
    if (allOpt) { presetSel.value = allOpt.value; fire(presetSel, 'change'); await tick(); }
  }

  // ===== TEST 6: Klant aanklikken → drill-down =====
  const firstClient = doc.querySelector('#cBars .cb-item');
  check('TEST 6: eerste top-klant bestaat', !!firstClient, !!firstClient);
  if (firstClient) {
    click(firstClient);
    await tick(); await tick();
    // Detect drill-down door specifieke elementen die JS vult
    const cdStats = doc.getElementById('cdStats');
    check('TEST 6: drill-down stats element bestaat', !!cdStats, !!cdStats);
    check('TEST 6: drill-down heeft inhoud',
      cdStats && cdStats.children.length > 0,
      cdStats ? cdStats.children.length + ' children' : 'n/a');
  }

  // ===== JS Errors =====
  check('GEEN runtime errors gedurende interactie', errors.length === 0,
    errors.length ? errors.slice(0,3).join(' | ') : 'clean');

  // ===== Rapport =====
  console.log('Interactieve smoke-test:\n');
  let pass = 0, fail = 0;
  for (const r of results) {
    console.log(`  ${r.ok ? '✓' : '✗'} ${r.label}  →  ${r.detail}`);
    r.ok ? pass++ : fail++;
  }
  console.log(`\nTotaal: ${pass}/${pass+fail} ok`);
  if (errors.length) {
    console.log('\nErrors:');
    errors.slice(0, 5).forEach(e => console.log('  -', e.slice(0, 200)));
  }
  process.exit(fail || errors.length ? 1 : 0);
})().catch(e => {
  console.error('test crash:', e.stack || e);
  process.exit(2);
});
