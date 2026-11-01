/* UI layer. All numbers come from UKCalc (tested) and data/dataset.json (built by update.py). */
(function () {
  'use strict';
  const C = window.UKCalc, $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const gbp = (v, d) => v == null ? 'n/a' : new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP', maximumFractionDigits: d == null ? 0 : d, minimumFractionDigits: d == null ? 0 : d }).format(v);
  const num = (v, d) => v == null ? 'n/a' : new Intl.NumberFormat('en-GB', { maximumFractionDigits: d == null ? 1 : d, minimumFractionDigits: d == null ? 1 : d }).format(v);
  const pct = (v, d) => v == null ? 'n/a' : num(v, d == null ? 1 : d) + '%';
  const NOW = new Date().getFullYear();
  const REGIONS = [['united-kingdom', 'United Kingdom'], ['england', 'England'], ['wales', 'Wales'], ['scotland', 'Scotland'], ['northern-ireland', 'Northern Ireland'],
    ['north-east', 'North East'], ['north-west', 'North West'], ['yorkshire-and-the-humber', 'Yorkshire & Humber'], ['east-midlands', 'East Midlands'],
    ['west-midlands', 'West Midlands'], ['east-of-england', 'East of England'], ['london', 'London'], ['south-east', 'South East'], ['south-west', 'South West']];
  let DS = null, STATUS = null;

  Promise.all([
    fetch('data/dataset.json', { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error('dataset.json HTTP ' + r.status); return r.json(); }),
    fetch('data/status.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).catch(() => null),
    fetch('data/stories.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : []).catch(() => []),
  ]).then(([ds, st, stories]) => { DS = ds; STATUS = st; addDerived(); init(stories); })
    .catch(e => { const b = $('loaderror'); b.hidden = false; b.textContent = 'Could not load the data files: ' + e.message + '. If you are opening this file directly from disk, serve it over http (python3 -m http.server).'; });

  // ---- derived (spliced) series, clearly labelled ----
  function addDerived() {
    const S = DS.series, v = {};
    if (S.earnings_boe_composite && S.awe_total_pay) {
      Object.assign(v, S.earnings_boe_composite.values);
      Object.keys(S.awe_total_pay.values).forEach(y => { v[y] = S.awe_total_pay.values[y]; });
      const part = {};
      Object.keys(S.awe_total_pay.partial || {}).forEach(y => { part[y] = S.awe_total_pay.partial[y]; });
      S.earnings_spliced = { id: 'earnings_spliced', derived: true, group: 'earnings', label: 'Average weekly earnings, spliced (£/week)', publisher: 'Derived: BoE composite (1990–99) + ONS AWE (2000 onward)', unit: 'GBP/week',
        values: sortObj(v), partial: part, coverage: ['1990', String(Math.max.apply(null, Object.keys(v).map(Number)))], adjustment: 'Nominal', source_url: '', last_updated: S.awe_total_pay.last_updated,
        methodology: 'Two different official earnings series joined at 2000.', limitations: 'Series break at 2000: definitions differ; they overlap 2000–2016 within a few percent.', warnings: [] };
    }
    if (S.mortgage_svr && S.mortgage_svr_bs_hist) {
      const r = {}; Object.keys(S.mortgage_svr_bs_hist.values).forEach(y => { if (+y < 1995) r[y] = S.mortgage_svr_bs_hist.values[y]; });
      Object.assign(r, S.mortgage_svr.values);
      S.mortgage_svr_spliced = { id: 'mortgage_svr_spliced', derived: true, group: 'housing', label: 'Standard variable mortgage rate, spliced (%)', publisher: 'Derived: building societies (1990–94) + Bank of England (1995 onward)', unit: '%',
        values: sortObj(r), partial: S.mortgage_svr.partial || {}, coverage: ['1990', String(Math.max.apply(null, Object.keys(r).map(Number)))], adjustment: 'Nominal', source_url: '', last_updated: S.mortgage_svr.last_updated,
        methodology: 'Joined at 1995; the two series differ by about 0.02 percentage points in 1995.', limitations: 'Different lender mix before 1995.', warnings: [] };
    }
    const g = S.gdp_nominal;
    if (S.house_price_united_kingdom || S['house_price_united-kingdom']) { /* ratio computed on demand */ }
    if (g) {
      ['rcpt_vat', 'rcpt_fuel_duty', 'rcpt_paye_income_tax', 'rcpt_social_contributions', 'rcpt_council_tax', 'tme'].forEach(id => {
        if (!S[id]) return;
        const out = {}; Object.keys(S[id].values).forEach(y => { if (g.values[y]) out[y] = S[id].values[y] / g.values[y] * 100; });
        DS.share = DS.share || {}; DS.share[id] = out;
      });
    }
  }
  function sortObj(o) { return Object.keys(o).sort((a, b) => a - b).reduce((r, k) => (r[k] = o[k], r), {}); }

  // ---- helpers ----
  function sv(id, y, carry) { return C.seriesValue(DS, id, y, { carry: !!carry }); }
  function pts(id, from, to) {
    const s = DS.series[id]; if (!s) return [];
    return Object.keys(s.values).map(Number).filter(y => y >= (from || 0) && y <= (to || 9999)).sort((a, b) => a - b).map(y => [y, s.values[y]]);
  }
  function partialPts(id) {
    const s = DS.series[id]; if (!s || !s.partial) return [];
    return Object.keys(s.partial).filter(y => s.partial[y].months >= 6 && s.values[y] == null).map(y => [+y, s.partial[y].mean]);
  }
  function badge(r) {
    if (!r) return '';
    if (r.status === 'partial') return `<span class="badge warn" title="${esc(r.note)}">part-year</span>`;
    if (r.status === 'carried') return `<span class="badge warn" title="${esc(r.note)}">${esc(r.note.replace('latest observation is ', 'latest: '))}</span>`;
    if (r.status === 'estimate') return `<span class="badge warn" title="${esc(r.note)}">estimate</span>`;
    if (r.status === 'missing') return `<span class="badge na" title="${esc(r.note)}">no data</span>`;
    return '';
  }
  const seriesLabel = id => DS.series[id] ? DS.series[id].label : id;
  const yearOpts = (sel, from, to, selected) => { sel.innerHTML = ''; for (let y = from; y <= to; y++) sel.add(new Option(y, y, false, y === selected)); };

  // =====================================================================================
  function init(stories) {
    const last = lastYear();
    yearOpts($('yearA'), 1990, last, 1990); yearOpts($('yearB'), 1990, last, last);
    REGIONS.forEach(([k, n]) => $('region').add(new Option(n, k)));
    ['yearA', 'yearB', 'earners', 'level', 'region', 'view', 'deposit', 'term', 'mtype', 'hours', 'miles', 'mpg', 'carry'].forEach(id => $(id).addEventListener('input', renderCompare));
    document.querySelectorAll('a[href="#compare"]').forEach(l => l.addEventListener('click', () => { $('compareDetails').open = true; }));
    $('genStamp').textContent = ' Data build: ' + DS.generated + '.';
    renderCompare();
    initQuick();
    initTrends(); initTax(); initHousing(); initFood(); initEnergy(); initTransport(); initGovernment(); initCorporate(); initData(stories);
  }
  function lastYear() { const s = DS.series.cpi_index; const p = Object.keys(s.partial || {}).filter(y => s.partial[y].months >= 6).map(Number); return Math.max(Math.max.apply(null, Object.keys(s.values).map(Number)), p.length ? Math.max.apply(null, p) : 0); }

  // =====================================================================================
  // COMPARE
  function inputs() {
    return { level: +$('level').value, earners: +$('earners').value, region: $('region').value, deposit: +$('deposit').value, termYears: +$('term').value,
      mortgageType: $('mtype').value, hoursPerWeek: +$('hours').value || 37.5, miles: +$('miles').value, mpg: +$('mpg').value || 40, carry: $('carry').checked };
  }
  function renderCompare() {
    const A = +$('yearA').value, B = +$('yearB').value, base = inputs(), view = $('view').value, o = { carry: base.carry };
    const a = C.household(DS, Object.assign({ year: A }, base)), b = C.household(DS, Object.assign({ year: B }, base));
    const nots = $('compareNotices'); nots.innerHTML = '';
    if (a.error || b.error) { nots.innerHTML = `<div class="notice bad">${esc(a.error || b.error)}</div>`; $('kpis').innerHTML = ''; $('balance').innerHTML = ''; $('hours').innerHTML = ''; return; }
    const adj = (v, y) => v == null ? null : (view === 'real' && y !== B ? C.realise(DS, v, y, B, o) : v);
    const people = base.earners;
    const bk = C.basketCompare(DS, A, B, o);
    const foodA = bk.totalA * 52 * people, foodB = bk.totalB * 52 * people;
    const info = [];
    if (A < 2000 || B < 2000) info.push('Earnings before 2000 come from the Bank of England composite series, which has a different definition from the ONS AWE series used from 2000.');
    if (A < 2000 || B < 2000) info.push('Mortgage interest tax relief (MIRAS, available until April 2000) is NOT modelled, so mortgage costs before 2000 are overstated relative to what many borrowers paid. Many pre-2000 borrowers also had interest-only or endowment loans; this model uses a repayment mortgage throughout.');
    [[a, A], [b, B]].forEach(([h, y]) => { [h.earnings, h.price, h.rate, h.fuel, h.energy].forEach(r => { if (r && (r.status === 'partial' || r.status === 'carried' || r.status === 'estimate')) { const m = `${y}: ${r.note}`; if (info.indexOf(m) < 0) info.push(m); } }); });
    if (bk.used < bk.available) info.push(`Food basket: ${bk.used} of ${bk.available} items have prices in both years; the rest are excluded from both years' totals.`);
    if (view === 'real') info.push(`Amounts for ${A} are converted to ${B} prices using the ONS CPI index.`);
    info.push('Tax years: a calendar year here uses the tax year that starts in it (e.g. 2025 = 2025–26).');
    nots.innerHTML = '<div class="notice info"><b>Read this with the numbers:</b><ul style="margin:6px 0 0 18px;padding:0">' + info.map(t => `<li>${esc(t)}</li>`).join('') + '</ul></div>';

    // ---- balance rows
    const row = (label, va, vb, opt) => ({ label, va, vb, neg: opt && opt.neg, cls: opt && opt.cls, note: opt && opt.note, ra: opt && opt.ra, rb: opt && opt.rb });
    const rows = [];
    rows.push(row('Gross pay', a.gross, b.gross, { note: 'average earnings × pay level × earners' }));
    rows.push(row('Income Tax', a.incomeTax, b.incomeTax, { neg: true }));
    rows.push(row('Employee National Insurance', a.ni, b.ni, { neg: true }));
    rows.push(row('Take-home pay', a.net, b.net, { cls: 'total' }));
    rows.push(row('Mortgage payments (average home)', a.mortgage, b.mortgage, { neg: true, ra: a.price, rb: b.price, note: `${base.deposit}% deposit, ${base.termYears}-year term` }));
    rows.push(row('Food (weekly basket × 52)', bk.used ? foodA : null, bk.used ? foodB : null, { neg: true, note: `${bk.used} like-for-like items` }));
    rows.push(row('Gas + electricity', a.energy.v, b.energy.v, { neg: true, ra: a.energy, rb: b.energy }));
    rows.push(row('Petrol for the car', a.fuel.v, b.fuel.v, { neg: true, ra: a.fuel, rb: b.fuel, note: `${base.miles.toLocaleString('en-GB')} miles at ${base.mpg} mpg` }));
    const left = (h, food) => { const comps = [h.mortgage, food, h.energy.v, h.fuel.v]; return h.net - comps.reduce((s, x) => s + (x == null ? 0 : x), 0); };
    const missA = [a.mortgage, bk.used ? foodA : null, a.energy.v, a.fuel.v].some(x => x == null), missB = [b.mortgage, bk.used ? foodB : null, b.energy.v, b.fuel.v].some(x => x == null);
    rows.push(row('Left after these costs', left(a, bk.used ? foodA : null), left(b, bk.used ? foodB : null), { cls: 'total' }));
    const tb = $('balance');
    const colA = `${A}${view === 'real' ? ' in ' + B + ' £' : ''}`;
    let html = `<thead><tr><th></th><th>${A} (${view === 'real' ? 'in ' + B + ' prices' : 'nominal'})</th><th>% of take-home</th><th>${B}</th><th>% of take-home</th><th>Real change</th></tr></thead><tbody>`;
    rows.forEach(r => {
      const isCost = r.neg, aNom = r.va, bNom = r.vb;
      const aShow = adj(aNom, A), bShow = bNom;
      const pa = r.cls === 'total' || r.label === 'Gross pay' ? (r.label === 'Gross pay' ? null : null) : (aNom != null ? aNom / a.net * 100 : null);
      const pb = r.cls === 'total' || r.label === 'Gross pay' ? null : (bNom != null ? bNom / b.net * 100 : null);
      const pctA = r.label === 'Left after these costs' ? (aNom / a.net * 100) : (r.label === 'Take-home pay' ? (aNom / a.gross * 100) : pa);
      const pctB = r.label === 'Left after these costs' ? (bNom / b.net * 100) : (r.label === 'Take-home pay' ? (bNom / b.gross * 100) : pb);
      const chg = (aShow != null && bShow != null && aShow > 0 && bShow > 0) ? (bShow / aShow - 1) * 100 : null;
      const lbl = esc(r.label) + (r.note ? `<br><span class="small">${esc(r.note)}</span>` : '');
      const bdg = (r.ra && r.ra.status ? badge(r.ra) : '') , bdgB = (r.rb && r.rb.status ? badge(r.rb) : '');
      html += `<tr class="${r.cls || ''}"><td>${lbl}</td><td>${r.neg && aNom != null ? '−' : ''}${gbp(aShow)}${bdg}</td><td>${pctA == null ? '' : pct(pctA)}${r.label === 'Take-home pay' ? ' <span class="small">of gross</span>' : ''}</td><td>${r.neg && bNom != null ? '−' : ''}${gbp(bShow)}${bdgB}</td><td>${pctB == null ? '' : pct(pctB)}${r.label === 'Take-home pay' ? ' <span class="small">of gross</span>' : ''}</td><td class="${chg == null ? 'flat' : (r.neg ? (chg > 0 ? 'up' : 'down') : (chg > 0 ? 'down' : 'up'))}">${chg == null ? 'n/a' : (chg > 0 ? '+' : '') + num(chg, 0) + '%'}</td></tr>`;
    });
    tb.innerHTML = html + '</tbody>';
    const excl = []; if (missA || missB) excl.push('a cost line is missing for one of the years, so the remainder excludes it');
    $('balanceNote').innerHTML = `“Left after these costs” is <b>not</b> total disposable income: it excludes Council Tax, water, broadband, insurance, car purchase and running costs other than petrol, clothing, childcare, rent and everything else not yet integrated (see <a href="#data">Data &amp; gaps</a>). Costs shown only where data exist${excl.length ? '; ' + excl.join('; ') : ''}. Tax and NI: ${esc(a.taxYear)} vs ${esc(b.taxYear)}.`;

    // ---- KPI cards
    const k = [];
    const card = (title, va, vb, deltaHtml, foot) => `<div class="kpi"><h3>${title}</h3><div class="pair"><div><div class="yr">${A}</div><div class="val">${va}</div></div><div style="text-align:right"><div class="yr">${B}</div><div class="val">${vb}</div></div></div><div class="delta">${deltaHtml || ''}</div>${foot ? `<div class="small">${foot}</div>` : ''}</div>`;
    const chgTxt = (x, goodUp) => x == null ? '' : `<span class="${(x > 0) === !!goodUp ? 'down' : 'up'}">${x > 0 ? '+' : ''}${num(x, 0)}%</span>`;
    const realTake = adj(a.net, A), realGross = adj(a.gross, A);
    k.push(card('Gross pay per year', gbp(a.gross), gbp(b.gross), `Real change: ${chgTxt(realGross ? (b.gross / realGross - 1) * 100 : null, true)}`, `${gbp(a.earnings.v, 0)} → ${gbp(b.earnings.v, 0)} average weekly earnings`));
    k.push(card('Take-home pay per year', gbp(a.net), gbp(b.net), `Real change: ${chgTxt(realTake ? (b.net / realTake - 1) * 100 : null, true)}`, `${gbp(a.net / 12)} → ${gbp(b.net / 12)} per month`));
    k.push(card('Tax taken (Income Tax + NI)', pct(a.effectiveRate * 100), pct(b.effectiveRate * 100), `${gbp(a.taxTotal)} → ${gbp(b.taxTotal)} a year`, 'share of gross pay; excludes VAT, fuel duty etc.'));
    k.push(card('Average home price', gbp(a.price.v) + badge(a.price), gbp(b.price.v) + badge(b.price), `${num(a.priceToEarnings, 1)}× → ${num(b.priceToEarnings, 1)}× average annual earnings`, esc((REGIONS.find(r => r[0] === base.region) || [0, ''])[1]) + ' · Land Registry UK HPI'));
    const mA = a.mortgage != null ? a.mortgage / 12 : null, mB = b.mortgage != null ? b.mortgage / 12 : null;
    k.push(card('Monthly mortgage payment', gbp(mA), gbp(mB), `${pct(mA != null ? mA * 12 / a.net * 100 : null, 0)} → ${pct(mB != null ? mB * 12 / b.net * 100 : null, 0)} of take-home`, `rate ${pct(a.rate.v, 1)} → ${pct(b.rate.v, 1)}`));
    k.push(card('Weekly food shop (like-for-like)', gbp(bk.used ? bk.totalA * people : null, 2), gbp(bk.used ? bk.totalB * people : null, 2), `${pct(bk.used ? foodA / a.net * 100 : null, 0)} → ${pct(bk.used ? foodB / b.net * 100 : null, 0)} of take-home`, `${bk.used} items · illustrative quantities`));
    k.push(card('Gas + electricity per year', gbp(a.energy.v) + badge(a.energy), gbp(b.energy.v) + badge(b.energy), `${pct(a.energy.v != null ? a.energy.v / a.net * 100 : null, 1)} → ${pct(b.energy.v != null ? b.energy.v / b.net * 100 : null, 1)} of take-home`, 'DESNZ typical bill; index-scaled estimate before 2010'));
    k.push(card('Petrol per year', gbp(a.fuel.v) + badge(a.fuel), gbp(b.fuel.v) + badge(b.fuel), `${pct(a.fuel.v != null ? a.fuel.v / a.net * 100 : null, 1)} → ${pct(b.fuel.v != null ? b.fuel.v / b.net * 100 : null, 1)} of take-home`, `${gbp(sv('price_petrol', A, base.carry).v, 2)} → ${gbp(sv('price_petrol', B, base.carry).v, 2)} per litre`));
    $('kpis').innerHTML = k.join('');

    // ---- hours table
    const items = [
      ['A pint of milk', 'price_milk', 1], ['A loaf of white sliced bread', 'price_bread_white_sliced', 1], ['A dozen eggs (size 4)', 'price_eggs_size4', 1],
      ['1 kg of chicken', 'price_chicken', 1], ['1 kg of cheddar', 'price_cheese', 1], ['A litre of petrol', 'price_petrol', 1],
    ];
    const hrs = (p, h) => p == null ? null : p / h;
    const fmtH = h => h == null ? 'n/a' : (h < 1 ? Math.round(h * 60) + ' min' : num(h, 1) + ' h');
    let th = `<thead><tr><th>Item</th><th>Price ${A}</th><th>Work ${A}</th><th>Price ${B}</th><th>Work ${B}</th><th>Change in work time</th></tr></thead><tbody>`;
    items.forEach(([n, id, q]) => {
      const pa = sv(id, A, base.carry), pb = sv(id, B, base.carry), ha = hrs(pa.v, a.hourlyNet), hb = hrs(pb.v, b.hourlyNet);
      const ch = ha && hb ? (hb / ha - 1) * 100 : null;
      th += `<tr><td>${n}</td><td>${gbp(pa.v, 2)}${badge(pa)}</td><td>${fmtH(ha)}</td><td>${gbp(pb.v, 2)}${badge(pb)}</td><td>${fmtH(hb)}</td><td class="${ch == null ? 'flat' : ch > 0 ? 'up' : 'down'}">${ch == null ? 'n/a' : (ch > 0 ? '+' : '') + num(ch, 0) + '%'}</td></tr>`;
    });
    const big = [['Weekly food shop (per household)', bk.used ? bk.totalA * people : null, bk.used ? bk.totalB * people : null, null, null], ['A month of mortgage payments', mA, mB, a.price, b.price], ['A year of gas + electricity', a.energy.v, b.energy.v, a.energy, b.energy]];
    big.forEach(([n, pa, pb, ra, rb]) => {
      const ha = hrs(pa, a.hourlyNet), hb = hrs(pb, b.hourlyNet), ch = ha && hb ? (hb / ha - 1) * 100 : null;
      th += `<tr><td>${n}</td><td>${gbp(pa, 0)}</td><td>${fmtH(ha)}</td><td>${gbp(pb, 0)}</td><td>${fmtH(hb)}</td><td class="${ch == null ? 'flat' : ch > 0 ? 'up' : 'down'}">${ch == null ? 'n/a' : (ch > 0 ? '+' : '') + num(ch, 0) + '%'}</td></tr>`;
    });
    $('hours').innerHTML = th + '</tbody>';
    $('hours').insertAdjacentHTML('beforeend', `<tfoot><tr><td colspan="6" class="small">Take-home hourly pay: ${gbp(a.hourlyNet, 2)} (${A}) and ${gbp(b.hourlyNet, 2)} (${B}), based on a ${base.hoursPerWeek}-hour week. Hours are per earner for a single earner; for two earners the same per-person pay applies.</td></tr></tfoot>`);

    // keep basket section in step
    if (typeof renderBasket === 'function') renderBasket();
  }


  // =====================================================================================
  // QUICK ANSWER (plain-language summary; reuses the tested calc layer)
  function initQuick() {
    const last = lastYear(), qs = new URLSearchParams(location.search);
    yearOpts($('qFrom'), 1990, last, 2000); yearOpts($('qTo'), 1990, last, last);
    REGIONS.forEach(([k, n]) => $('qRegion').add(new Option(n, k)));
    $('qRegion').value = 'united-kingdom';
    const set = (id, v) => { if (v != null && [...$(id).options].some(o => o.value === v)) $(id).value = v; };
    if (qs.get('s')) $('qSalary').value = Math.max(5000, Math.min(500000, +qs.get('s') || 35000));
    set('qFrom', qs.get('a')); set('qTo', qs.get('b')); set('qEarners', qs.get('e')); set('qRegion', qs.get('r'));
    ['qSalary', 'qFrom', 'qTo', 'qEarners', 'qRegion'].forEach(id => $(id).addEventListener('input', renderQuick));
    $('qCopy').addEventListener('click', () => {
      const u = location.origin + location.pathname + '?' + quickParams() + '#quick';
      const done = ok => { $('qCopied').textContent = ok ? 'Link copied.' : u; };
      try { navigator.clipboard.writeText(u).then(() => done(true), () => done(false)); } catch (e) { done(false); }
    });
    renderQuick();
  }
  function quickParams() {
    return new URLSearchParams({ s: $('qSalary').value, a: $('qFrom').value, b: $('qTo').value, e: $('qEarners').value, r: $('qRegion').value }).toString();
  }
  function plainNote(m) {
    return m.replace(/(\d{4}): mean of (\d+) months to \d{4}-\d\d/, '$1: only the first $2 months of the year are published so far; their average is used')
      .replace(/(\d{4}): latest observation is (\d{4})/, '$1: this source has nothing newer than $2 yet, so the $2 figure is used')
      .replace(/(\d{4}): ESTIMATE: 2010 DESNZ bill scaled by.*/, '$1: official energy bills only start in 2010; earlier energy costs are an estimate scaled from the official fuel price index');
  }
  function renderQuick() {
    const S = +$('qSalary').value, A = +$('qFrom').value, B = +$('qTo').value, people = +$('qEarners').value, region = $('qRegion').value;
    const out = $('qHeadline'), cards = $('qCards'), notes = $('qNotes'); notes.innerHTML = '';
    try { history.replaceState(null, '', '?' + quickParams() + location.hash); } catch (e) { /* ignore */ }
    if (!(S >= 1000) || A >= B) { out.innerHTML = '<p>Please enter a salary and choose an earlier year on the left than the year on the right.</p>'; cards.innerHTML = ''; return; }
    const o = { carry: true }, weB = C.weeklyEarnings(DS, B, o);
    if (weB.v == null) { out.innerHTML = '<p>No earnings data for ' + B + '.</p>'; cards.innerHTML = ''; return; }
    const level = S / (weB.v * 52);
    const base = { level, earners: people, region, deposit: 10, termYears: 25, mortgageType: 'svr', hoursPerWeek: 37.5, miles: 7400, mpg: 40, carry: true };
    const a = C.household(DS, Object.assign({ year: A }, base)), b = C.household(DS, Object.assign({ year: B }, base));
    if (a.error || b.error) { out.innerHTML = '<p>' + esc(a.error || b.error) + '</p>'; cards.innerHTML = ''; return; }
    const real = v => v == null ? null : C.realise(DS, v, A, B, o);
    const ch = (x, y) => (x != null && y != null && x > 0 && y > 0) ? (y / x - 1) * 100 : null;
    const word = (c, up, down) => c == null ? 'n/a' : (Math.abs(c) < 0.5 ? 'about the same' : (c > 0 ? num(c, 0) + '% ' + up : num(-c, 0) + '% ' + down));
    const bk = C.basketCompare(DS, A, B, o), foodA = bk.used ? bk.totalA * 52 * people : null, foodB = bk.used ? bk.totalB * 52 * people : null;
    const sum = (...xs) => xs.some(x => x == null) ? null : xs.reduce((s, x) => s + x, 0);
    const evA = sum(foodA, a.energy.v, a.fuel.v), evB = sum(foodB, b.energy.v, b.fuel.v);
    const taxRealCh = ch(real(a.taxTotal), b.taxTotal), netRealCh = ch(real(a.net), b.net), grossRealCh = ch(real(a.gross), b.gross);
    const evRealCh = ch(real(evA), evB), mortRealCh = ch(real(a.mortgage), b.mortgage);
    const cpiRatio = C.realise(DS, 1, A, B, o);
    const nation = region === 'wales' ? 'wales_' : region === 'scotland' ? 'scotland_' : region === 'northern-ireland' ? null : '';
    const ctA = nation == null ? null : sv('council_tax_' + nation + 'band_d', A, false), ctB = nation == null ? null : sv('council_tax_' + nation + 'band_d', B, false);
    const ctRealCh = ctA && ctB ? ch(real(ctA.v), ctB.v) : null;
    const cls = (c, goodDown) => c == null ? 'flat' : ((c > 0) === !goodDown ? 'down' : 'up');
    const L = [];
    L.push(`<b>Tax.</b> On ${gbp(b.gross)} in ${B} you pay about <b>${gbp(b.taxTotal)}</b> in Income Tax and National Insurance (${pct(b.effectiveRate * 100, 0)} of pay). Someone in the same position relative to average pay in ${A} paid ${gbp(a.taxTotal)} at the time (${pct(a.effectiveRate * 100, 0)} of pay), or ${gbp(real(a.taxTotal))} in ${B} money. In real terms that is <b>${word(taxRealCh, 'more', 'less')}</b> tax, and the share of pay taken is ${b.effectiveRate > a.effectiveRate + 0.002 ? 'higher' : b.effectiveRate < a.effectiveRate - 0.002 ? 'lower' : 'about the same'}.`);
    L.push(`<b>Pay.</b> Their gross pay in ${A} was ${gbp(real(a.gross))} in ${B} money, so pay is ${word(grossRealCh, 'higher', 'lower')} in real terms now. Take-home pay is ${word(netRealCh, 'higher', 'lower')} (${gbp(a.net / 12)} → ${gbp(b.net / 12)} a month in cash terms).`);
    if (evA != null && evB != null) L.push(`<b>Everyday costs</b> (food, gas and electricity, petrol): ${gbp(evA)} → ${gbp(evB)} a year. In real terms that is <b>${word(evRealCh, 'more', 'less')}</b>, and ${pct(evA / a.net * 100, 0)} → ${pct(evB / b.net * 100, 0)} of take-home pay. Consumer prices overall are ${num(cpiRatio, 2)}× higher than in ${A}.`);
    else L.push(`<b>Everyday costs:</b> not shown as a total because at least one of food, energy or petrol has no data for ${A} or ${B}.`);
    if (a.mortgage != null && b.mortgage != null) L.push(`<b>Housing</b> (mortgage on the average home in this region): ${gbp(a.mortgage / 12)} → ${gbp(b.mortgage / 12)} a month, ${word(mortRealCh, 'more', 'less')} in real terms, and ${pct(a.mortgage / a.net * 100, 0)} → ${pct(b.mortgage / b.net * 100, 0)} of take-home pay.`);
    // ---- the two-line answer
    const dirw = (c, up, down) => c == null ? '' : (Math.abs(c) < 0.5 ? 'about the same' : (c > 0 ? up : down));
    const cb = (c, goodDown, txt) => `<b class="${c == null ? '' : ((c > 0) === !goodDown ? 'down' : 'up')}">${txt}</b>`;
    const big = [];
    big.push(`<div class="line">${taxRealCh == null ? 'Tax comparison not available.' : `Compared with someone in the same position in <b>${A}</b>, you pay ${cb(taxRealCh, true, word(taxRealCh, 'more', 'less'))} Income Tax and National Insurance in real terms (${pct(a.effectiveRate * 100, 0)} → ${pct(b.effectiveRate * 100, 0)} of pay).`}</div>`);
    if (evRealCh != null) big.push(`<div class="line">Everyday costs (food, energy, petrol) are ${cb(evRealCh, true, word(evRealCh, 'higher', 'lower'))}, while take-home pay is ${cb(netRealCh, false, word(netRealCh, 'higher', 'lower'))}${netRealCh != null && evRealCh != null ? (netRealCh > evRealCh ? ': pay has grown faster than these costs' : netRealCh < evRealCh ? ': these costs have grown faster than pay' : '') : ''}.</div>`);
    else big.push('<div class="line">Everyday costs cannot be totalled because food, energy or petrol data is missing for one of the years.</div>');
    if (a.mortgage != null && b.mortgage != null) {
      const shareB = b.mortgage / b.net * 100;
      big.push(`<div class="line">Housing: a mortgage on the average home takes ${pct(a.mortgage / a.net * 100, 0)} → ${pct(shareB, 0)} of take-home pay.${shareB > 60 ? ' Repayments this high are more than lenders usually allow on one income: this shows how costly the average home is, not what a typical buyer pays.' : ''}</div>`);
    }
    big.push('<div class="sub2">In real terms = adjusted for inflation to ' + B + ' prices. Tax here is Income Tax and National Insurance only; VAT, fuel duty and Council Tax are not included.</div>');
    $('qBig').innerHTML = big.join('');
    // ---- bars: same person then and now, all in B money
    $('qBarsYear').textContent = B;
    const bars = [['Gross pay', real(a.gross), b.gross], ['Income Tax + NI', real(a.taxTotal), b.taxTotal], ['Take-home pay', real(a.net), b.net], ['Everyday costs', real(evA), evB], ['Mortgage (average home)', real(a.mortgage), b.mortgage]];
    const mx = Math.max.apply(null, bars.flatMap(r => [r[1], r[2]]).filter(x => x != null));
    $('qBars').className = 'bars';
    $('qBars').innerHTML = bars.map(([n, x, y]) => { const w = v => v == null ? 0 : Math.max(1, v / mx * 100); return `<div class="brow"><div class="blabel">${n}</div><div class="bl"><span class="y">${A}</span><div class="bar a" style="width:${w(x)}%"></div><span class="bv">${x == null ? 'no data' : gbp(x)}</span></div><div class="bl"><span class="y">${B}</span><div class="bar b" style="width:${w(y)}%"></div><span class="bv">${y == null ? 'no data' : gbp(y)}</span></div></div>`; }).join('');
    out.innerHTML = '<ul style="margin:0;padding-left:18px;line-height:1.7">' + L.map(t => `<li style="margin:6px 0">${t}</li>`).join('') + '</ul>';

    const card = (title, va, vb, delta, cl, foot) => `<div class="kpi"><h3>${title}</h3><div class="pair"><div><div class="yr">${A}</div><div class="val">${va}</div></div><div style="text-align:right"><div class="yr">${B}</div><div class="val">${vb}</div></div></div><div class="delta ${cl || ''}">${delta}</div>${foot ? `<div class="small">${foot}</div>` : ''}</div>`;
    const dtxt = (c, suffix) => c == null ? 'n/a' : (c > 0 ? '+' : '') + num(c, 0) + '% ' + suffix;
    const cardsH = [
      card('Income Tax + NI', gbp(a.taxTotal), gbp(b.taxTotal), dtxt(taxRealCh, 'in real terms'), cls(taxRealCh, true), `Share of pay ${pct(a.effectiveRate * 100, 1)} → ${pct(b.effectiveRate * 100, 1)}`),
      card('Take-home pay', gbp(a.net), gbp(b.net), dtxt(netRealCh, 'in real terms'), cls(netRealCh, false), 'per year, after Income Tax and NI'),
      card('Everyday costs', evA == null ? 'n/a' : gbp(evA), evB == null ? 'n/a' : gbp(evB), dtxt(evRealCh, 'in real terms'), cls(evRealCh, true), 'food + gas/electricity + petrol, per year'),
      card('Mortgage (average home)', a.mortgage == null ? 'n/a' : gbp(a.mortgage), b.mortgage == null ? 'n/a' : gbp(b.mortgage), dtxt(mortRealCh, 'in real terms'), cls(mortRealCh, true), 'per year; home price ' + gbp(a.price.v) + ' → ' + gbp(b.price.v)),
    ];
    if (nation == null) cardsH.push(`<div class="kpi"><h3>Council Tax</h3><div class="small">Northern Ireland has no Council Tax: homes pay domestic rates on their capital value, and no comparable official average is integrated here.</div></div>`);
    else cardsH.push(card('Council Tax (Band D)', ctA && ctA.v != null ? gbp(ctA.v) : 'no data', ctB && ctB.v != null ? gbp(ctB.v) : 'no data', ctRealCh == null ? (ctA && ctA.v == null ? 'No Council Tax data for ' + A + ' (England starts 2002)' : 'n/a') : dtxt(ctRealCh, 'in real terms'), cls(ctRealCh, true), 'average Band D, not included in the totals above'));
    cards.innerHTML = cardsH.join('');

    const info = [];
    [[a, A], [b, B]].forEach(([h, y]) => [h.earnings, h.price, h.rate, h.fuel, h.energy].forEach(r => { if (r && (r.status === 'partial' || r.status === 'carried' || r.status === 'estimate')) { const m = `${y}: ${r.note}`; if (info.indexOf(m) < 0) info.push(plainNote(m)); } }));
    if (A < 2000) info.push('Before April 2000 many borrowers got mortgage interest tax relief (MIRAS), which is not modelled, so the earlier mortgage cost is overstated.');
    if (A < 2000) info.push('Earnings before 2000 use a Bank of England composite series with a slightly different definition from later ONS figures.');
    if (bk.used < bk.available) info.push(`Food: ${bk.used} of ${bk.available} items are priced in both years and used for both.`);
    info.push('Single-earner tax rules for England, Wales and Northern Ireland; Scottish Income Tax rates are not modelled. No pensions, student loans or benefits. Rent, water, broadband, insurance and car purchase are not included (see Data & gaps).');
    notes.innerHTML = '<div class="notice info"><b>Good to know</b><ul style="margin:6px 0 0 18px;padding:0">' + info.map(t => `<li>${esc(t)}</li>`).join('') + '</ul></div>';
  }

  // =====================================================================================
  // TREND EXPLORER
  const PRESETS = {
    'Pay vs prices vs housing': ['earnings_spliced', 'cpi_index', 'house_price_united-kingdom', 'price_bread_white_sliced', 'price_petrol'],
    'Housing': ['house_price_united-kingdom', 'house_price_london', 'house_price_north-east', 'house_price_wales'],
    'Food prices': ['price_milk', 'price_bread_white_sliced', 'price_cheese', 'price_chicken', 'price_sugar', 'price_bananas'],
    'Fuel and energy': ['price_petrol', 'price_diesel', 'cpi_electricity_gas'],
    'Interest rates': ['mortgage_svr_spliced', 'mortgage_2y_fixed_75ltv', 'bank_rate'],
  };
  let selected = [];
  function initTrends() {
    const from = $('tfrom'); yearOpts(from, 1990, 2020, 1990);
    from.addEventListener('input', drawTrends); $('tmode').addEventListener('input', drawTrends);
    const pre = $('presets');
    Object.keys(PRESETS).forEach((n, i) => { const b = document.createElement('button'); b.textContent = n; b.setAttribute('aria-pressed', 'false'); b.addEventListener('click', () => { selected = PRESETS[n].filter(id => DS.series[id]); if (n === 'Interest rates') $('tmode').value = 'raw'; else if ($('tmode').value === 'raw') $('tmode').value = 'index'; syncPicker(); [...pre.children].forEach(x => x.setAttribute('aria-pressed', x === b)); drawTrends(); }); pre.appendChild(b); });
    const groups = {}; Object.values(DS.series).forEach(s => { (groups[s.group || 'other'] = groups[s.group || 'other'] || []).push(s); });
    const names = { earnings: 'Earnings', prices: 'Prices and inflation', housing: 'Housing and rates', food: 'Food prices', energy: 'Energy', transport: 'Transport', government: 'Government finances' };
    let html = '';
    Object.keys(names).forEach(g => { if (!groups[g]) return; html += `<h4>${names[g]}</h4>` + groups[g].sort((a, b) => a.label.localeCompare(b.label)).map(s => `<label><input type="checkbox" value="${esc(s.id)}"> ${esc(s.label)}</label>`).join(''); });
    $('picker').innerHTML = html;
    $('picker').addEventListener('input', e => { if (e.target.type !== 'checkbox') return; selected = [...$('picker').querySelectorAll('input:checked')].map(i => i.value).slice(0, 6); syncPicker(); [...pre.children].forEach(x => x.setAttribute('aria-pressed', 'false')); drawTrends(); });
    pre.children[0].click();
  }
  function syncPicker() { [...$('picker').querySelectorAll('input')].forEach(i => { i.checked = selected.indexOf(i.value) >= 0; }); }
  function drawTrends() {
    const mode = $('tmode').value, from = +$('tfrom').value, notes = [], latest = lastYear() - 1;
    const cpi = DS.series.cpi_index.values;
    let series = selected.map(id => DS.series[id]).filter(Boolean).map(s => ({ s, p: pts(s.id, from), pp: partialPts(s.id).filter(q => q[0] >= from) }));
    const isGBP = s => /^GBP\b/.test(s.unit) && !/million/i.test(s.unit);
    if (mode === 'real') {
      series = series.filter(x => { if (isGBP(x.s)) return true; notes.push(`${x.s.label} is not a £ series, so it is left out of real-terms view.`); return false; });
      series.forEach(x => { const f = y => cpi[latest] / cpi[y]; x.p = x.p.filter(q => cpi[q[0]]).map(q => [q[0], q[1] * f(q[0])]); x.pp = []; });
      notes.push(`£ values converted to ${latest} prices with the ONS CPI index.`);
    } else if (mode === 'index') {
      const starts = series.map(x => x.p.length ? x.p[0][0] : null).filter(v => v != null);
      const base = starts.length ? Math.max.apply(null, starts) : null;
      series = series.map(x => { const b = x.p.find(q => q[0] === base); if (!b) return Object.assign(x, { p: [], pp: [] }); const f = 100 / b[1]; return Object.assign(x, { p: x.p.filter(q => q[0] >= base).map(q => [q[0], q[1] * f]), pp: x.pp.filter(q => q[0] >= base).map(q => [q[0], q[1] * f]) }); });
      if (base) notes.push(`Every series is set to 100 in ${base}, the first year all selected series share.`);
    } else {
      const units = new Set(series.map(x => x.s.unit)); if (units.size > 1) notes.push('Warning: the selected series use different units. Switch to index mode to compare them fairly.');
    }
    series.forEach(x => { if (x.s.limitations && /break/i.test(x.s.limitations)) notes.push(`${x.s.label}: ${x.s.limitations}`); if (x.p.length && x.s.coverage) { const e = x.s.coverage[1]; if (+e < latest) notes.push(`${x.s.label} ends in ${e} (no later observation).`); } });
    const fmt = mode === 'index' ? v => num(v, 0) : (series[0] && /%/.test(series[0].s.unit)) ? v => num(v, 1) + '%' : (series[0] && isGBP(series[0].s)) ? v => gbp(v, v < 20 ? 2 : 0) : v => num(v, 1);
    Charts.line($('trendChart'), { series: series.map(x => ({ name: x.s.label, points: x.p, partial: mode === 'real' ? [] : x.pp })), yFormat: fmt, title: 'Trend chart' });
    $('trendNote').innerHTML = notes.map(n => `<div>• ${esc(n)}</div>`).join('') + '<div>Hollow markers are part-year averages (six or more months). Lines break where data are missing; gaps are never joined.</div>';
  }

  // =====================================================================================
  // TAX
  function initTax() {
    $('taxLevel').addEventListener('input', drawTax); $('taxSalary').addEventListener('input', drawTax); drawTax();
    const t = DS.curated.uk_tax_rules; if (!t) return;
    let h = '<thead><tr><th>Tax year</th><th>Personal allowance</th><th>Income Tax bands (taxable income)</th><th>Employee NI (weekly)</th></tr></thead><tbody>';
    Object.keys(t.years).sort((a, b) => b - a).forEach(y => {
      const r = t.years[y], it = r.income_tax; let lo = 0;
      const bands = it.bands.map(([up, rate]) => { const s = up == null ? `${rate}% above ${gbp(lo)}` : `${rate}% up to ${gbp(up)}`; lo = up; return s; }).join('; ');
      const p = r.ni.periods, p0 = p[p.length - 1];
      const ni = r.ni.regime === 'entry_fee' ? `${p0.entry_fee}% of LEL + ${p0.main}% from ${gbp(p0.lel)} to ${gbp(p0.uel)}` : `${p.length > 1 ? 'varies in year: ' : ''}${p.map(q => q.main + '%').filter((v, i, a) => a.indexOf(v) === i).join(' / ')} from ${gbp(p0.pt)} to ${gbp(p0.uel)}; ${p0.above_uel}% above`;
      h += `<tr><td>${esc(it.label)}</td><td>${gbp(it.personal_allowance)}${it.pa_taper_above ? '<span class="small"> *</span>' : ''}</td><td style="white-space:normal;text-align:left">${esc(bands)}</td><td style="white-space:normal;text-align:left">${esc(ni)}</td></tr>`;
    });
    $('taxRules').innerHTML = h + '</tbody>';
    $('taxScope').innerHTML = `Source: HMRC statistics Tables A.1, A.2, A.4 and A.4A (<a href="${esc(t.sources.a2.page)}">Rates of Income Tax</a>). Scope: ${esc(t.scope)}. ${esc(t.limitations)} * Personal allowance is withdrawn at £1 per £2 of income above £100,000 (from 2010-11).`;
  }
  function drawTax() {
    const lvl = +$('taxLevel').value, s = C.effectiveRateSeries(DS, lvl, 1990, lastYear());
    Charts.line($('taxChart'), { title: 'Tax take', yFormat: v => num(v, 0) + '%', zeroBase: true, series: [
      { name: 'Income Tax + NI', points: s.map(p => [p.year, p.rate * 100]) }, { name: 'Income Tax', points: s.map(p => [p.year, p.it * 100]) }, { name: 'Employee NI', points: s.map(p => [p.year, p.ni * 100]) }] });
    const sal = +$('taxSalary').value || 0, rows = [];
    for (let y = 1990; y <= lastYear(); y++) { const th = C.takeHome(DS, y, sal); if (th) rows.push([y, th]); }
    Charts.line($('taxFixed'), { title: 'Tax on a fixed salary', yFormat: v => gbp(v), zeroBase: true, series: [
      { name: 'Income Tax (£)', points: rows.map(([y, t]) => [y, t.incomeTax]) }, { name: 'Employee NI (£)', points: rows.map(([y, t]) => [y, t.ni]) }, { name: 'Take-home (£)', points: rows.map(([y, t]) => [y, t.net]) }] });
  }

  // =====================================================================================
  // HOUSING
  function initHousing() {
    const e = [], r = [];
    for (let y = 1990; y <= lastYear(); y++) { const w = C.weeklyEarnings(DS, y, {}), p = sv('house_price_united-kingdom', y); if (w.v != null && p.v != null) e.push([y, p.v / (w.v * 52)]); }
    Charts.line($('p2eChart'), { title: 'House price to earnings', yFormat: v => num(v, 1) + '×', series: [{ name: 'UK average price ÷ average annual earnings', points: e }] });
    Charts.line($('rateChart'), { title: 'Mortgage rates', yFormat: v => num(v, 0) + '%', zeroBase: true, series: [
      { name: 'Standard variable rate', points: pts('mortgage_svr_spliced'), partial: partialPts('mortgage_svr') }, { name: '2-year fixed (75% LTV)', points: pts('mortgage_2y_fixed_75ltv'), partial: partialPts('mortgage_2y_fixed_75ltv') }, { name: 'Bank Rate', points: pts('bank_rate'), partial: partialPts('bank_rate'), dash: '5 3' }] });
    const regs = ['united-kingdom', 'london', 'south-east', 'north-east', 'wales', 'scotland'];
    Charts.line($('regionChart'), { title: 'Regional house prices', yFormat: v => gbp(v / 1000) + 'k', zeroBase: true, series: regs.map(k => ({ name: (REGIONS.find(x => x[0] === k) || [0, k])[1], points: pts('house_price_' + k), partial: partialPts('house_price_' + k) })) });
    const drawCT = () => { const nat = $('ctNation').value, bs = $('ctBands').value === 'all' ? (nat === 'wales_' ? 'abcdefghi' : 'abcdefgh') : 'adh'; Charts.line($('ctChart'), { title: 'Council Tax by band', yFormat: v => gbp(v, 0), zeroBase: true, series: bs.split('').map(b => ({ name: 'Band ' + b.toUpperCase(), points: pts('council_tax_' + nat + 'band_' + b) })) }); };
    $('ctNation').addEventListener('change', drawCT); $('ctBands').addEventListener('change', drawCT); drawCT();
    Charts.line($('rentChart'), { title: 'CPI actual rents index', yFormat: v => num(v, 0), series: [{ name: 'CPI actual rents (2015=100)', points: pts('cpi_actual_rents'), partial: partialPts('cpi_actual_rents') }] });
    Charts.line($('medianChart'), { title: 'Mean and median weekly pay', yFormat: v => gbp(v, 0), zeroBase: true, series: [
      { name: 'Mean, all employees (AWE; BoE composite before 2000)', points: pts('earnings_spliced') },
      { name: 'Median, full-time, UK (ASHE)', points: pts('earnings_median_ft') },
      { name: 'Median, full-time, GB (NES)', points: pts('earnings_median_ft_nes') }] });
  }
  function pts2(id) { return pts(id); }

  // =====================================================================================
  // FOOD
  window.renderBasket = renderBasket;
  function renderBasket() {
    if (!DS) return;
    const A = +$('yearA').value, B = +$('yearB').value, carry = $('carry').checked, view = $('view').value, o = { carry };
    const bk = C.basketCompare(DS, A, B, o);
    let h = `<thead><tr><th>Item (weekly quantity per person)</th><th>Price ${A}</th><th>Price ${B}</th><th>Price change</th><th>Real change</th><th>Cost/week ${A}</th><th>Cost/week ${B}</th></tr></thead><tbody>`;
    bk.rows.forEach(r => {
      const q = r.item.qty, f = C.realise(DS, 1, A, B, o);
      const ch = r.included ? (r.b.v / r.a.v - 1) * 100 : null, rc = r.included && f ? (r.b.v / (r.a.v * f) - 1) * 100 : null;
      h += `<tr${r.included ? '' : ' style="opacity:.6"'}><td>${esc(r.item.name)} <span class="small">${q} ${esc(r.item.per)}</span></td><td>${gbp(r.a.v, 2)}${badge(r.a)}</td><td>${gbp(r.b.v, 2)}${badge(r.b)}</td><td>${ch == null ? 'n/a' : (ch > 0 ? '+' : '') + num(ch, 0) + '%'}</td><td class="${rc == null ? 'flat' : rc > 0 ? 'up' : 'down'}">${rc == null ? 'n/a' : (rc > 0 ? '+' : '') + num(rc, 0) + '%'}</td><td>${r.included ? gbp(r.a.v * q, 2) : 'excluded'}</td><td>${r.included ? gbp(r.b.v * q, 2) : 'excluded'}</td></tr>`;
    });
    const f = C.realise(DS, 1, A, B, o);
    h += `<tr class="total"><td>Like-for-like weekly basket (${bk.used} of ${bk.available} items)</td><td></td><td></td><td>${bk.used ? (bk.totalB / bk.totalA - 1 >= 0 ? '+' : '') + num((bk.totalB / bk.totalA - 1) * 100, 0) + '%' : 'n/a'}</td><td>${bk.used && f ? num((bk.totalB / (bk.totalA * f) - 1) * 100, 0) + '%' : 'n/a'}</td><td>${gbp(bk.totalA, 2)}</td><td>${gbp(bk.totalB, 2)}</td></tr></tbody>`;
    $('basket').innerHTML = h;
    $('basketNote').innerHTML = 'Years follow the Year A / Year B selectors above. Rice, pasta and some other staples have no continuous official average-price series and are not shown. “Real change” compares the price change with CPI inflation between the two years (negative = cheaper relative to prices generally).';
  }
  function initFood() {
    const sel = $('foodItem'); Object.values(DS.series).filter(s => s.group === 'food').sort((a, b) => a.label.localeCompare(b.label)).forEach(s => sel.add(new Option(s.label, s.id)));
    sel.addEventListener('input', drawFood); drawFood(); renderBasket();
  }
  function drawFood() {
    const id = $('foodItem').value, s = DS.series[id]; if (!s) return;
    Charts.line($('foodChart'), { title: s.label, yFormat: v => gbp(v, 2), zeroBase: true, series: [{ name: s.label + ' (' + s.unit.replace('GBP/', '£ per ') + ')', points: pts(id), partial: partialPts(id) }] });
  }

  // =====================================================================================
  // ENERGY / TRANSPORT / GOVERNMENT
  function initEnergy() {
    const e = pts('energy_elec_direct_debit'), g = pts('energy_gas_direct_debit'), t = e.map(([y, v]) => { const gv = DS.series.energy_gas_direct_debit.values[y]; return gv == null ? null : [y, v + gv]; }).filter(Boolean);
    Charts.line($('energyBills'), { title: 'Annual energy bills', yFormat: v => gbp(v), zeroBase: true, series: [{ name: 'Electricity', points: e }, { name: 'Gas', points: g }, { name: 'Electricity + gas', points: t, dash: '5 3' }] });
    Charts.line($('energyIndex'), { title: 'Fuel price index', yFormat: v => num(v, 0), series: [{ name: 'CPI electricity, gas & other fuels (2015=100)', points: pts('cpi_electricity_gas'), partial: partialPts('cpi_electricity_gas') }] });
  }
  function initTransport() {
    Charts.line($('fuelChart'), { title: 'Pump prices', yFormat: v => gbp(v, 2), zeroBase: true, series: [{ name: 'Petrol', points: pts('price_petrol') }, { name: 'Diesel', points: pts('price_diesel') }] });
    Charts.line($('transIndex'), { title: 'CPI components', yFormat: v => num(v, 0), series: [{ name: 'New cars', points: pts('cpi_new_cars') }, { name: 'Rail fares', points: pts('cpi_rail_fares') }, { name: 'Motor insurance', points: pts('cpi_motor_insurance') }] });
  }
  function initGovernment() {
    const sh = DS.share || {}, mk = (id, name) => ({ name, points: Object.keys(sh[id] || {}).map(Number).sort((a, b) => a - b).map(y => [y, sh[id][y]]) });
    Charts.line($('rcptChart'), { title: 'Receipts % GDP', yFormat: v => num(v, 0) + '%', zeroBase: true, series: [mk('rcpt_vat', 'VAT'), mk('rcpt_paye_income_tax', 'PAYE income tax (from 1993)'), mk('rcpt_social_contributions', 'Social contributions (incl. NICs)'), mk('rcpt_fuel_duty', 'Fuel duty (from 1997)'), mk('rcpt_council_tax', 'Council tax')] });
    Charts.line($('debtChart'), { title: 'Spending and debt % GDP', yFormat: v => num(v, 0) + '%', zeroBase: true, series: [mk('tme', 'Total managed expenditure (from 1998)'), { name: 'Public sector net debt ex banks', points: pts('psnd_pct_gdp'), partial: partialPts('psnd_pct_gdp') }] });
    let h = '<thead><tr><th>Latest annual figure</th><th>Year</th><th>£ million</th><th>% of GDP</th><th>First year</th></tr></thead><tbody>';
    ['rcpt_vat', 'rcpt_paye_income_tax', 'rcpt_social_contributions', 'rcpt_fuel_duty', 'rcpt_council_tax', 'tme'].forEach(id => { const s = DS.series[id]; if (!s) return; const ys = Object.keys(s.values).map(Number).sort((a, b) => a - b), y = ys[ys.length - 1]; h += `<tr><td><a href="${esc(s.source_url)}">${esc(s.label)}</a></td><td>${y}</td><td>${num(s.values[y], 0)}</td><td>${sh[id] && sh[id][y] != null ? pct(sh[id][y]) : 'n/a'}</td><td>${ys[0]}</td></tr>`; });
    $('rcptTable').innerHTML = h + '</tbody>';
  }

  // =====================================================================================
  // CORPORATE
  function initCorporate() {
    const c = DS.curated.company_financials;
    if (c && c.companies && c.companies.length) { renderCompanies(c); return; }
    $('corpBody').innerHTML = `<div class="notice warn"><b>Not yet integrated.</b> No company financial statements are loaded, so no profit figures are shown. Nothing has been estimated. See <a href="#data">Data &amp; gaps</a>.</div>
      <p class="lead">Official reports for the companies in scope. Group results include overseas activity and must not be read as UK results; statutory and adjusted profit are different measures; financial years are not calendar years; and higher profit does not by itself show price gouging.</p>
      <div class="tablewrap"><table><thead><tr><th>Company</th><th>Annual reports</th><th>Caution</th></tr></thead><tbody>
      <tr><td>Tesco</td><td><a href="https://www.tescoplc.com/investors/reports-results-and-presentations/">Reports</a></td><td>Separate UK &amp; ROI retail from group totals</td></tr>
      <tr><td>J Sainsbury</td><td><a href="https://www.about.sainsburys.co.uk/investors/reports">Reports</a></td><td>Retail vs financial services</td></tr>
      <tr><td>BP</td><td><a href="https://www.bp.com/en/global/corporate/investors/results-reporting-and-presentations/annual-report.html">Reports</a></td><td>Global operations; underlying replacement-cost profit differs from IFRS</td></tr>
      <tr><td>Shell</td><td><a href="https://www.shell.com/investors/results-and-reporting/annual-report.html">Reports</a></td><td>Global operations; adjusted earnings differ from net income</td></tr>
      <tr><td>Barclays</td><td><a href="https://home.barclays/investor-relations/reports-and-events/annual-reports/">Reports</a></td><td>UK vs international segments</td></tr>
      <tr><td>Lloyds Banking Group</td><td><a href="https://www.lloydsbankinggroup.com/investors/financial-downloads.html">Reports</a></td><td>Statutory vs underlying profit</td></tr>
      <tr><td>Companies House filings</td><td><a href="https://find-and-update.company-information.service.gov.uk/">Search</a></td><td>UK entities only</td></tr></tbody></table></div>`;
  }
  function renderCompanies(c) {
    const M = [['revenue', 'Revenue'], ['operating_profit', 'Operating profit'], ['pbt', 'Profit before tax'], ['net_profit', 'Profit to owners'], ['tax_expense', 'Tax expense'], ['tax_paid', 'Tax paid (cash)'], ['dividends_paid', 'Dividends paid'], ['buybacks', 'Buybacks']];
    let h = `<p class="lead">${esc(c.note || '')}</p><div class="notice warn">${esc(c.limitations || '')}</div>
      <div class="controls"><label>Company<select id="coSel">${c.companies.map(x => `<option value="${esc(x.id)}">${esc(x.name)} (${esc(x.sector)})</option>`).join('')}</select></label>
      <label>Measure<select id="coMeasure">${M.map(m => `<option value="${m[0]}"${m[0] === 'pbt' ? ' selected' : ''}>${m[1]}</option>`).join('')}</select></label></div>
      <div id="coChart"></div><div class="tablewrap" style="margin-top:10px"><table id="coTable"></table></div><p class="small" id="coNote"></p>`;
    $('corpBody').innerHTML = h;
    const draw = () => {
      const co = c.companies.find(x => x.id === $('coSel').value), me = $('coMeasure').value;
      const ys = Object.keys(co.years).sort();
      const pts = ys.filter(y => co.years[y][me] != null).map(y => [+y, co.years[y][me]]);
      const lab = (M.find(m => m[0] === me) || [])[1];
      Charts.line($('coChart'), { title: co.name + ' ' + lab, zeroBase: true, yFormat: v => num(v, 0), series: [{ name: lab + ' (' + co.unit + ')', points: pts }] });
      const f = v => v == null ? '<span class="small">not tagged</span>' : num(v, 0);
      $('coTable').innerHTML = '<thead><tr><th>Year</th>' + M.map(m => `<th>${m[1]}</th>`).join('') + '</tr></thead><tbody>' +
        ys.slice().reverse().map(y => `<tr><td>${y}</td>${M.map(m => `<td>${f(co.years[y][m[0]])}</td>`).join('')}</tr>`).join('') + '</tbody>';
      $('coNote').textContent = co.unit + ', calendar financial year ending ' + co.fiscal_year_end + '. ' + co.revenue_note + ' Source: ' + c.publisher + '.';
    };
    $('coSel').addEventListener('change', draw); $('coMeasure').addEventListener('change', draw); draw();
  }

  // =====================================================================================
  // DATA, STATUS, GAPS
  function initData(stories) {
    const s = STATUS;
    $('statusBox').innerHTML = s ? `<b>Last automated check:</b> ${esc(s.checked)} · <span class="${s.series_failed ? 'status-bad' : 'status-ok'}">${s.series_ok} of ${s.series_ok + s.series_failed} series refreshed successfully</span>${s.series_failed ? ' · failed (last good data kept): ' + esc(s.failed_ids.join(', ')) : ''}<div class="small">Scheduled refresh runs three times a day on GitHub Actions. If a source fails, the previous values are kept and no replacement is invented.</div>` : 'Status file not available.';
    const gaps = DS.gaps || [], order = { open: 0, documented: 1 };
    $('gaps').innerHTML = '<div class="tablewrap"><table><thead><tr><th>Area</th><th>Item</th><th>Status</th><th style="text-align:left">Detail</th></tr></thead><tbody>' + gaps.slice().sort((a, b) => (order[a.status] || 0) - (order[b.status] || 0)).map(g => `<tr><td>${esc(g.area)}</td><td style="white-space:normal;text-align:left">${esc(g.title)}</td><td><span class="badge ${g.status === 'open' ? 'warn' : ''}">${esc(g.status)}</span></td><td style="white-space:normal;text-align:left">${esc(g.detail)}</td></tr>`).join('') + '</tbody></table></div>';
    const cat = $('catalogue');
    const all = Object.values(DS.series).sort((a, b) => (a.group || '').localeCompare(b.group || '') || a.label.localeCompare(b.label));
    const tax = DS.curated.uk_tax_rules;
    const draw = q => {
      const f = all.filter(x => !q || (x.label + ' ' + x.publisher + ' ' + x.group).toLowerCase().indexOf(q.toLowerCase()) >= 0);
      let h = '<thead><tr><th>Dataset</th><th>Publisher</th><th>Unit</th><th>Coverage</th><th>Updated</th><th>Source ID</th><th style="text-align:left">Method and limitations</th></tr></thead><tbody>';
      f.forEach(x => { h += `<tr><td style="white-space:normal">${x.source_url ? `<a href="${esc(x.source_url)}">${esc(x.label)}</a>` : esc(x.label)}${x.derived ? ' <span class="badge">derived</span>' : ''}</td><td style="white-space:normal;text-align:left">${esc(x.publisher)}</td><td>${esc(x.unit)}</td><td>${esc((x.coverage || []).join('–'))}</td><td>${esc(x.last_updated)}</td><td>${esc(x.source_id || '')}</td><td style="white-space:normal;text-align:left"><span class="small">${esc(x.adjustment || '')}. ${esc(x.methodology || '')} ${esc(x.limitations || '')}</span></td></tr>`; });
      if (tax && (!q || /tax|hmrc/i.test(q))) h += `<tr><td style="white-space:normal"><a href="${esc(tax.sources.a2.page)}">${esc(tax.title)}</a></td><td style="white-space:normal;text-align:left">${esc(tax.publisher)}</td><td>rules</td><td>1990–2026</td><td></td><td>A.1, A.2, A.4, A.4A</td><td style="white-space:normal;text-align:left"><span class="small">${esc(tax.scope)}. ${esc(tax.limitations)}</span></td></tr>`;
      cat.innerHTML = h + '</tbody>';
    };
    draw(''); $('catFilter').addEventListener('input', e => draw(e.target.value));
    $('method').innerHTML = `<ul style="margin:0;padding-left:18px">
      <li><b>Never invented.</b> Every figure is an official observation, an arithmetic result of observations (for example price ÷ earnings), or is labelled <em>estimate</em>. Missing years are shown as “no data”.</li>
      <li><b>Real values</b> use the ONS CPI all-items index (2015=100) as deflator. CPI excludes owner-occupier housing costs; CPIH and RPI are also in the catalogue.</li>
      <li><b>Year and tax year.</b> Price and earnings series are calendar-year figures. Tax rules are keyed by the tax year starting in that year (2025 = 2025–26). The latest year may be a part-year average (six or more months), marked “part-year”.</li>
      <li><b>Household model.</b> Each earner is a full-time employee earning the chosen multiple of average earnings (mean weekly earnings × 52), taxed on HMRC rules for England, Wales and Northern Ireland, ignoring pensions, student loans, benefits and tax credits. Housing cost is a repayment mortgage on the average price for the chosen region at the chosen deposit, term and rate. Food is an illustrative basket priced with ONS average prices. Energy is the DESNZ modelled typical bill. Fuel assumes the stated mileage and mpg.</li>
      <li><b>Mean, not median.</b> Average earnings here are means. Median earnings are not yet integrated, so “pay level” is a multiple of the mean.</li>
      <li><b>Taxes in prices</b> (VAT, fuel duty) are already inside the prices shown and are not added again. Receipts categories overlap and must not be summed.</li>
      <li><b>Automation.</b> <code>update.py</code> runs on GitHub Actions three times a day, checks each series' published title, rejects implausible or shrinking data, keeps the last good file on failure, and records everything in <code>data/status.json</code> and <code>data/changes.json</code>. No AI service is used.</li></ul>`;
    $('news').innerHTML = (stories || []).slice(0, 12).map(x => `<li><a href="${esc(x.url)}">${esc(x.title)}</a> <span class="small">· ${esc(x.source)} · ${esc((x.date || '').slice(0, 10))}</span></li>`).join('') || '<li class="small">No items.</li>';
  }
})();
