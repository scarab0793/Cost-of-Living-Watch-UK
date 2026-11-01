// Run: node tests/test_calc.js   (no dependencies)
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const C = require('../assets/calc.js');
const ds = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'dataset.json'), 'utf8'));

let n = 0;
const t = (name, fn) => { try { fn(); n++; console.log('ok  ', name); } catch (e) { console.error('FAIL', name, '\n   ', e.message); process.exitCode = 1; } };
const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg || ''} expected ${b} got ${a}`);

// --- Income tax / NI against hand calculation from the HMRC tables ---
t('2025-26 £40,000: income tax = 20% x (40,000-12,570)', () => {
  const r = C.rulesFor(ds, 2025); near(C.incomeTax(r, 40000).tax, 5486, 0.01);
});
t('2025-26 £40,000: NI = 8% x weekly earnings above £242, x52', () => {
  near(C.employeeNI(C.rulesFor(ds, 2025), 40000), 0.08 * (40000 / 52 - 242) * 52, 0.01);
});
t('2024-25 £50,000: tax £7,486, NI ~£2,993', () => {
  const th = C.takeHome(ds, 2024, 50000); near(th.incomeTax, 7486, 0.01); near(th.ni, 2993.28, 0.5);
});
t('1990-91 £10,000: tax 25% x (10,000-3,005)', () => {
  near(C.incomeTax(C.rulesFor(ds, 1990), 10000).tax, 0.25 * (10000 - 3005), 0.01);
});
t('1990-91 £10,000: NI = 2% of LEL + 9% above LEL (weekly), x52', () => {
  const w = 10000 / 52; near(C.employeeNI(C.rulesFor(ds, 1990), 10000), (0.02 * 46 + 0.09 * (w - 46)) * 52, 0.01);
});
t('1993-94 uses 20% lower rate on first £2,500 of taxable income', () => {
  const r = C.rulesFor(ds, 1993); // PA 3445; gross 10,000 -> taxable 6,555 = 2,500@20% + 4,055@25%
  near(C.incomeTax(r, 10000).tax, 2500 * 0.2 + 4055 * 0.25, 0.01);
});
t('2010-11: personal allowance tapers above £100,000', () => {
  const r = C.rulesFor(ds, 2010); assert.strictEqual(C.incomeTax(r, 112950).personalAllowance, 0);
  assert.strictEqual(C.incomeTax(r, 110000).personalAllowance, 6475 - 5000);
});
t('2010-11 additional rate 50% above £150,000 taxable', () => {
  const r = C.rulesFor(ds, 2010); const x = C.incomeTax(r, 200000);
  near(x.tax, 37400 * 0.2 + (150000 - 37400) * 0.4 + 50000 * 0.5, 0.01);
});
t('tax is monotonic in gross pay for every year', () => {
  for (let y = 1990; y <= 2026; y++) {
    const r = C.rulesFor(ds, y); assert.ok(r, 'rules ' + y); let prev = -1;
    for (let g = 0; g <= 250000; g += 2500) {
      const total = C.incomeTax(r, g).tax + C.employeeNI(r, g);
      assert.ok(total >= prev - 1e-6, `non-monotonic ${y} at ${g}`); prev = total;
    }
  }
});
t('no negative take-home and effective rate < 55% for all years at 1x-5x average earnings', () => {
  for (let y = 1990; y <= 2025; y++) for (const lvl of [0.5, 1, 2, 5]) {
    const we = C.weeklyEarnings(ds, y, {}); const th = C.takeHome(ds, y, we.v * 52 * lvl);
    assert.ok(th.net > 0 && th.effectiveRate < 0.55, `${y} x${lvl}: ${th.effectiveRate}`);
  }
});

// --- Mortgage maths ---
t('mortgage payment: £100,000, 5%, 25y = £584.59/month', () => near(C.monthlyPayment(100000, 5, 25), 584.59, 0.01));
t('mortgage payment: zero rate divides evenly', () => near(C.monthlyPayment(120000, 0, 10), 1000, 1e-9));

// --- Data accessors and honesty of statuses ---
t('observed vs missing vs carried', () => {
  assert.strictEqual(C.seriesValue(ds, 'price_butter', 2000).status, 'observed');
  assert.strictEqual(C.seriesValue(ds, 'price_butter', 2020).status, 'missing');
  const c = C.seriesValue(ds, 'price_butter', 2020, { carry: true });
  assert.strictEqual(c.status, 'carried'); assert.ok(/2012/.test(c.note));
});
t('2026 partial-year values are labelled partial', () => {
  const p = C.seriesValue(ds, 'cpi_index', 2026); assert.strictEqual(p.status, 'partial'); assert.ok(/months/.test(p.note));
});
t('pre-2000 earnings come from the BoE composite and are labelled', () => {
  const w = C.weeklyEarnings(ds, 1990, {}); assert.strictEqual(w.source, 'BoE composite'); near(w.v, 203.12, 0.01);
});
t('ONS AWE used from 2000', () => assert.strictEqual(C.weeklyEarnings(ds, 2005, {}).source, 'ONS AWE total pay'));
t('real conversion: £100 in 1990 -> 2025 money scales by CPI ratio', () => {
  const a = C.cpi(ds, 1990).v, b = C.cpi(ds, 2025).v; near(C.realise(ds, 100, 1990, 2025), 100 * b / a, 1e-9);
});
t('energy: official £ bill from 2010, labelled estimate before', () => {
  assert.strictEqual(C.energyAny(ds, 2015).status, 'observed');
  const e = C.energyAny(ds, 1995); assert.strictEqual(e.status, 'estimate'); assert.ok(/ESTIMATE/.test(e.note));
});
t('basket uses only items observed in both years', () => {
  const b = C.basketCompare(ds, 1990, 2024, {});
  assert.ok(b.used > 8 && b.used <= b.available);
  for (const r of b.rows) assert.strictEqual(r.included, r.a.v != null && r.b.v != null);
});
t('basket excludes eggs when comparing with 2024 without carry-forward (series ends 2021)', () => {
  const b = C.basketCompare(ds, 1990, 2024, {}); assert.strictEqual(b.rows.find(r => r.item.id === 'price_eggs_size4').included, false);
});

// --- Household scenario end to end ---
const base = { level: 1, earners: 1, region: 'united-kingdom', deposit: 10, termYears: 25, mortgageType: 'svr', hoursPerWeek: 37.5, miles: 7400, mpg: 40, carry: false };
t('household 1990 vs 2025: sensible magnitudes', () => {
  const a = C.household(ds, Object.assign({ year: 1990 }, base)), b = C.household(ds, Object.assign({ year: 2025 }, base));
  assert.ok(!a.error && !b.error);
  assert.ok(a.gross > 9000 && a.gross < 12000, 'gross 1990 ' + a.gross);   // 203 x 52 ≈ £10.6k
  assert.ok(b.gross > 36000 && b.gross < 40000, 'gross 2025 ' + b.gross);  // ≈ 728 x 52 ≈ £37.9k
  assert.ok(a.price.v > 50000 && a.price.v < 60000 && b.price.v > 250000);
  assert.ok(a.rate.v > 12 && b.rate.v < 8);
  assert.ok(a.mortgage > 0 && b.mortgage > 0);
});
t('two earners double gross and net', () => {
  const one = C.household(ds, Object.assign({ year: 2020 }, base)), two = C.household(ds, Object.assign({ year: 2020 }, base, { earners: 2 }));
  near(two.gross, 2 * one.gross, 1e-6); near(two.net, 2 * one.net, 1e-6);
});
t('regional prices: London > North East in every year observed', () => {
  for (let y = 1990; y <= 2025; y++) {
    const l = C.seriesValue(ds, 'house_price_london', y).v, ne = C.seriesValue(ds, 'house_price_north-east', y).v;
    assert.ok(l > ne, `${y}: ${l} vs ${ne}`);
  }
});

// --- Dataset integrity ---
t('every series has source metadata, unit, coverage and observations', () => {
  for (const [id, s] of Object.entries(ds.series)) {
    for (const k of ['label', 'publisher', 'unit', 'methodology', 'limitations', 'last_updated']) assert.ok(k in s, `${id} missing ${k}`);
    assert.ok(s.source_url || s.api_url, `${id} has no source url`);
    assert.ok(Object.keys(s.values).length >= 5, `${id} too few obs`);
    for (const v of Object.values(s.values)) assert.ok(Number.isFinite(v), `${id} non-finite value`);
  }
});
t('tax rules cover 1990-2026 with sources', () => {
  const r = ds.curated.uk_tax_rules; for (let y = 1990; y <= 2026; y++) assert.ok(r.years[y], 'missing ' + y);
  assert.ok(r.sources.a2.url.startsWith('https://assets.publishing.service.gov.uk/'));
});

console.log(`\n${n} tests passed${process.exitCode ? ' (with failures)' : ''}`);
