/* Pure calculation layer: no DOM. Works in browsers and in Node (tests/test_calc.js).
 * Every accessor returns {v, status, note} so the UI can label observed / partial / carried / missing values.
 * Nothing here estimates historical figures except where status === 'estimate' (index-scaled, labelled). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.UKCalc = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const WEEKS = 52;

  // ---------- data access ----------
  function seriesValue(ds, id, year, opts) {
    opts = opts || {};
    const s = ds.series[id];
    if (!s) return { v: null, status: 'missing', note: 'series not loaded' };
    const y = String(year);
    if (s.values[y] != null) return { v: s.values[y], status: 'observed', note: '' };
    const p = s.partial && s.partial[y];
    if (p && p.months >= 6) {
      return { v: p.mean, status: 'partial', note: `mean of ${p.months} months to ${p.last}` };
    }
    if (opts.carry) {
      const ys = Object.keys(s.values).map(Number).sort((a, b) => a - b);
      const last = ys[ys.length - 1];
      if (last != null && last < Number(year)) {
        return { v: s.values[String(last)], status: 'carried', note: `latest observation is ${last}` };
      }
    }
    return { v: null, status: 'missing', note: `no observation for ${year} (coverage ${s.coverage ? s.coverage.join('–') : 'n/a'})` };
  }

  // Average weekly earnings (all employees): ONS AWE from 2000, BoE composite series 1990-1999
  function weeklyEarnings(ds, year, opts) {
    const a = seriesValue(ds, 'awe_total_pay', year, opts);
    if (a.v != null) return Object.assign({ source: 'ONS AWE total pay' }, a);
    const b = seriesValue(ds, 'earnings_boe_composite', year, { carry: false });
    if (b.v != null) return { v: b.v, status: b.status, note: 'Bank of England composite series (pre-2000, different definition from ONS AWE)', source: 'BoE composite' };
    return Object.assign({ source: null }, a);
  }

  function cpi(ds, year, opts) { return seriesValue(ds, 'cpi_index', year, opts); }

  // Convert an amount from `fromYear` pounds to `toYear` pounds using ONS CPI.
  function realise(ds, amount, fromYear, toYear, opts) {
    const a = cpi(ds, fromYear, opts), b = cpi(ds, toYear, opts);
    if (a.v == null || b.v == null || amount == null) return null;
    return amount * b.v / a.v;
  }

  // ---------- tax ----------
  function rulesFor(ds, year) {
    const t = ds.curated && ds.curated.uk_tax_rules;
    return t && t.years[String(year)] ? t.years[String(year)] : null;
  }

  function incomeTax(rules, gross) {
    const it = rules.income_tax;
    let pa = it.personal_allowance;
    if (it.pa_taper_above && gross > it.pa_taper_above) pa = Math.max(0, pa - Math.floor((gross - it.pa_taper_above) / 2));
    const taxable = Math.max(0, gross - pa);
    let tax = 0, lower = 0;
    for (const [upper, rate] of it.bands) {
      const top = upper == null ? Infinity : upper;
      if (taxable > lower) tax += (Math.min(taxable, top) - lower) * rate / 100;
      lower = top;
      if (taxable <= top) break;
    }
    return { tax, taxable, personalAllowance: pa };
  }

  function employeeNI(rules, gross) {
    const w = gross / WEEKS;
    let annual = 0;
    for (const p of rules.ni.periods) {
      let wk = 0;
      if (rules.ni.regime === 'entry_fee') {
        if (w >= p.lel) wk = p.entry_fee / 100 * p.lel + p.main / 100 * (Math.min(w, p.uel) - p.lel);
      } else {
        wk = p.main / 100 * Math.max(0, Math.min(w, p.uel) - p.pt) + p.above_uel / 100 * Math.max(0, w - p.uel);
      }
      annual += wk * WEEKS * p.months / 12;
    }
    return annual;
  }

  function takeHome(ds, year, gross) {
    // tax years are keyed by start year; the selected calendar year uses the tax year starting in it
    const r = rulesFor(ds, year);
    if (!r) return null;
    const it = incomeTax(r, gross);
    const ni = employeeNI(r, gross);
    return { gross, incomeTax: it.tax, ni, net: gross - it.tax - ni, personalAllowance: it.personalAllowance,
      effectiveRate: gross > 0 ? (it.tax + ni) / gross : 0, taxYear: r.income_tax.label };
  }

  // ---------- housing ----------
  function mortgageRate(ds, year, type, opts) {
    if (type === 'fixed2') return Object.assign({ label: '2-year fixed, 75% LTV (BoE)' }, seriesValue(ds, 'mortgage_2y_fixed_75ltv', year, opts));
    const m = seriesValue(ds, 'mortgage_svr', year, opts);
    if (m.v != null) return Object.assign({ label: 'Standard variable rate (BoE)' }, m);
    const b = seriesValue(ds, 'mortgage_svr_bs_hist', year, { carry: false });
    if (b.v != null) return { v: b.v, status: b.status, note: "building societies' basic rate (pre-1995 bridge series)", label: 'Standard variable rate (building societies, pre-1995)' };
    return Object.assign({ label: 'Standard variable rate' }, m);
  }

  function monthlyPayment(principal, annualRatePct, years) {
    const n = years * 12, r = annualRatePct / 1200;
    if (principal <= 0) return 0;
    return r === 0 ? principal / n : principal * r / (1 - Math.pow(1 + r, -n));
  }

  // ---------- food basket ----------
  // Illustrative weekly shopping per person. Quantities are an ASSUMPTION (not ONS expenditure weights).
  const BASKET = [
    { id: 'price_milk', name: 'Milk', qty: 3.5, per: 'pint' },
    { id: 'price_bread_white_sliced', name: 'Bread (white sliced 800g)', qty: 1, per: 'loaf' },
    { id: 'price_eggs_size4', name: 'Eggs (size 4)', qty: 0.5, per: 'dozen' },
    { id: 'price_butter', name: 'Butter (250g)', qty: 0.5, per: 'pack' },
    { id: 'price_cheese', name: 'Cheddar cheese', qty: 0.2, per: 'kg' },
    { id: 'price_beef_mince', name: 'Beef mince', qty: 0.3, per: 'kg' },
    { id: 'price_chicken', name: 'Chicken', qty: 0.5, per: 'kg' },
    { id: 'price_pork_loin', name: 'Pork loin', qty: 0.2, per: 'kg' },
    { id: 'price_potatoes_old', name: 'Potatoes (old white)', qty: 1.0, per: 'kg' },
    { id: 'price_sugar', name: 'Sugar', qty: 0.3, per: 'kg' },
    { id: 'price_tea_bags', name: 'Tea bags (250g)', qty: 0.2, per: 'pack' },
    { id: 'price_coffee_instant', name: 'Instant coffee (100g)', qty: 0.5, per: 'jar' },
    { id: 'price_bananas', name: 'Bananas', qty: 0.5, per: 'kg' },
    { id: 'price_apples_dessert', name: 'Apples (dessert)', qty: 0.5, per: 'kg' },
    { id: 'price_carrots', name: 'Carrots', qty: 0.4, per: 'kg' },
    { id: 'price_tomatoes', name: 'Tomatoes', qty: 0.3, per: 'kg' },
  ];

  // Compare two years using only items observed in BOTH years (so totals are like-for-like).
  function basketCompare(ds, yearA, yearB, opts) {
    const rows = [];
    let totA = 0, totB = 0, used = 0;
    for (const it of BASKET) {
      const a = seriesValue(ds, it.id, yearA, opts), b = seriesValue(ds, it.id, yearB, opts);
      const ok = a.v != null && b.v != null;
      if (ok) { totA += a.v * it.qty; totB += b.v * it.qty; used++; }
      rows.push({ item: it, a, b, included: ok });
    }
    return { rows, totalA: totA, totalB: totB, used, available: BASKET.length };
  }

  // ---------- energy ----------
  function energyBill(ds, year, opts) {
    const e = seriesValue(ds, 'energy_elec_direct_debit', year, opts);
    const g = seriesValue(ds, 'energy_gas_direct_debit', year, opts);
    if (e.v != null && g.v != null) {
      const carried = e.status === 'carried' || g.status === 'carried';
      return { v: e.v + g.v, status: carried ? 'carried' : 'observed', note: carried ? (e.status === 'carried' ? e.note : g.note) : '', basis: 'DESNZ modelled bill: 3,600 kWh electricity + 13,600 kWh gas, direct debit', elec: e.v, gas: g.v };
    }
    return { v: null, status: 'missing', note: 'DESNZ £ bills start in 2010' };
  }

  // Index-scaled ESTIMATE for years without a published £ bill: anchor on 2010 bill, scale by CPI fuel index.
  function energyBillEstimate(ds, year) {
    const anchor = energyBill(ds, 2010), idxA = seriesValue(ds, 'cpi_electricity_gas', 2010), idxY = seriesValue(ds, 'cpi_electricity_gas', year);
    if (anchor.v == null || idxA.v == null || idxY.v == null) return { v: null, status: 'missing', note: 'cannot estimate' };
    return { v: anchor.v * idxY.v / idxA.v, status: 'estimate',
      note: 'ESTIMATE: 2010 DESNZ bill scaled by the ONS CPI electricity/gas/other-fuels index. Not an observed bill.' };
  }

  function energyAny(ds, year, opts) {
    const o = energyBill(ds, year, opts);
    return o.v != null ? o : energyBillEstimate(ds, year);
  }

  // ---------- fuel ----------
  function petrolAnnual(ds, year, miles, mpg, opts) {
    const p = seriesValue(ds, 'price_petrol', year, opts);
    if (p.v == null) return Object.assign({}, p);
    const litres = miles / mpg * 4.54609;
    return { v: litres * p.v, status: p.status, note: p.note || `${litres.toFixed(0)} litres at £${p.v.toFixed(2)}/litre` };
  }

  // ---------- tax content of everyday spending ----------
  /* Tax in a year's petrol spend: duty per litre + VAT included in the pump price (P*v/(1+v)). */
  function fuelTax(ds, year, miles, mpg, opts) {
    const p = seriesValue(ds, 'price_petrol', year, opts), d = seriesValue(ds, 'fuel_duty_petrol', year, { carry: false }), v = seriesValue(ds, 'vat_standard_rate', year, { carry: false });
    if (p.v == null || d.v == null || v.v == null) return { v: null, status: 'missing', note: 'no fuel tax data' };
    const litres = miles / mpg * 4.54609, vr = v.v / 100;
    const duty = litres * d.v / 100, vat = litres * p.v * vr / (1 + vr);
    return { v: duty + vat, duty, vat, status: p.status, note: p.note };
  }
  /* VAT contained in a gas+electricity bill at the domestic-fuel rate. */
  function energyVat(ds, year, bill) {
    const r = seriesValue(ds, 'vat_domestic_fuel_rate', year, { carry: false });
    if (bill == null || r.v == null) return null;
    return bill * (r.v / 100) / (1 + r.v / 100);
  }

  // ---------- household scenario ----------
  /* inputs: {year, level (multiple of avg earnings), earners (1|2), region slug, depositPct, termYears,
              mortgageType, hoursPerWeek, miles, mpg, carry, persons} */
  function household(ds, inp) {
    const o = { carry: !!inp.carry };
    const warn = [];
    const we = weeklyEarnings(ds, inp.year, o);
    if (we.v == null) return { year: inp.year, error: `No earnings data for ${inp.year}`, warn };
    const grossEach = we.v * WEEKS * inp.level;
    const th = takeHome(ds, inp.year, grossEach);
    if (!th) return { year: inp.year, error: `No HMRC tax rules for ${inp.year}`, warn };
    const gross = grossEach * inp.earners, net = th.net * inp.earners;
    const taxTotal = (th.incomeTax + th.ni) * inp.earners;
    const hourly = th.net / (inp.hoursPerWeek * WEEKS);

    const price = seriesValue(ds, `house_price_${inp.region}`, inp.year, o);
    const rate = mortgageRate(ds, inp.year, inp.mortgageType, o);
    let mortgage = null, deposit = null, loan = null;
    if (price.v != null && rate.v != null) {
      deposit = price.v * inp.deposit / 100;
      loan = price.v - deposit;
      mortgage = monthlyPayment(loan, rate.v, inp.termYears) * 12;
    }
    const food = { v: null };
    const energy = energyAny(ds, inp.year, o);
    const fuel = petrolAnnual(ds, inp.year, inp.miles, inp.mpg, o);
    const cpiY = cpi(ds, inp.year, o);
    return {
      year: inp.year, earnings: we, grossEach, gross, net, taxTotal, effectiveRate: th.effectiveRate, taxYear: th.taxYear,
      incomeTax: th.incomeTax * inp.earners, ni: th.ni * inp.earners, hourlyNet: hourly,
      price, rate, deposit, loan, mortgage, energy, fuel, cpi: cpiY, warn,
      priceToEarnings: price.v != null ? price.v / (we.v * WEEKS) : null,       // vs average earnings
      priceToIncome: price.v != null ? price.v / gross : null,                  // vs this household's gross
    };
  }

  // Hours of take-home work needed to buy an item priced `p` (GBP).
  function hoursToBuy(p, hourlyNet) { return p == null || !hourlyNet ? null : p / hourlyNet; }

  // Effective tax rate series for a given real income (constant "level" of average earnings), by year.
  function effectiveRateSeries(ds, level, from, to) {
    const out = [];
    for (let y = from; y <= to; y++) {
      const we = weeklyEarnings(ds, y, {});
      if (we.v == null) continue;
      const th = takeHome(ds, y, we.v * WEEKS * level);
      if (th) out.push({ year: y, rate: th.effectiveRate, it: th.incomeTax / th.gross, ni: th.ni / th.gross });
    }
    return out;
  }

  return { WEEKS, BASKET, seriesValue, weeklyEarnings, cpi, realise, rulesFor, incomeTax, employeeNI, takeHome,
    mortgageRate, monthlyPayment, basketCompare, energyBill, energyBillEstimate, energyAny, petrolAnnual,
    household, hoursToBuy, effectiveRateSeries, fuelTax, energyVat };
});
