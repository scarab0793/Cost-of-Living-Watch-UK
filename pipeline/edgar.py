"""Company financials from SEC EDGAR XBRL 'companyfacts' (20-F filings, IFRS, group level).

Coverage is the XBRL era only (about 2017 onward). Earlier years need annual reports and are listed as a gap.
Values are statutory group figures as reported, in the company's reporting currency (no FX conversion),
in millions. Group results include overseas activity and are NOT UK-only results.
For each period the latest filing wins (so restatements flow through). A figure is only stored when the
filer tagged it; absent tags stay null rather than being derived.
"""
import json
from datetime import date, datetime

from . import fetch

SEC_UA = "UK-Living-Cost-Watch/3.0 (public statistics)"

COMPANIES = [
    # id, name, sector, cik, currency, revenue tags (preference order), note on revenue
    ("bp", "BP", "Oil and gas", "0000313807", "USD", ["Revenue"], "Total revenues and other income as tagged (Revenue)."),
    ("shell", "Shell", "Oil and gas", "0001306965", "USD", ["Revenue"], "Revenue as tagged."),
    ("barclays", "Barclays", "Bank", "0000312069", "GBP", [], "Barclays does not tag total income in the XBRL Revenue element, so none is shown."),
    ("hsbc", "HSBC", "Bank", "0001089113", "USD", [], "Bank revenue is not comparable with industrial revenue and tags are inconsistent across years, so none is shown."),
    ("natwest", "NatWest Group", "Bank", "0000844150", "GBP", [], "Bank revenue is not comparable with industrial revenue and tags are inconsistent across years, so none is shown."),
    ("lloyds", "Lloyds Banking Group", "Bank", "0001160106", "GBP", [], "Bank revenue is not comparable with industrial revenue and tags are inconsistent across years, so none is shown."),
]
METRICS = {
    "pbt": (["ProfitLossBeforeTax"], "Profit before tax"),
    "net_profit": (["ProfitLossAttributableToOwnersOfParent", "ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity", "ProfitLoss"], "Profit attributable to owners of the parent"),
    "tax_expense": (["IncomeTaxExpenseContinuingOperations"], "Income tax expense (all jurisdictions)"),
    "tax_paid": (["IncomeTaxesPaidClassifiedAsOperatingActivities", "IncomeTaxesPaidRefundClassifiedAsOperatingActivities"], "Income tax paid (cash, all jurisdictions)"),
    "dividends_paid": (["DividendsPaid", "DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities", "DividendsPaidOrdinaryShares"], "Dividends paid to shareholders (cash)"),
    "buybacks": (["PurchaseOfTreasuryShares"], "Purchase of treasury shares (share buybacks, as tagged)"),
}
OPERATING = {"bp": ["ProfitLossFromOperatingActivities"]}  # operating profit only where it is a meaningful concept and tagged


def _annual(facts, tags, currency):
    """{year: (value_in_millions, tag)} for full-year duration facts, latest filing wins."""
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        rows = node["units"].get(currency) or []
        best = {}
        for r in rows:
            if not r.get("form", "").startswith("20-F") or not r.get("start"):
                continue
            s, e = datetime.fromisoformat(r["start"]), datetime.fromisoformat(r["end"])
            if not 350 <= (e - s).days <= 380:
                continue
            key = r["end"]
            if key not in best or r["filed"] > best[key]["filed"]:
                best[key] = r
        if best:
            return {k[:4]: (round(v["val"] / 1e6, 1), tag, v["filed"], v.get("accn", "")) for k, v in best.items()}
    return {}


def build():
    out = []
    for cid, name, sector, cik, cur, rev_tags, rev_note in COMPANIES:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        facts = json.loads(fetch.http_get(url, timeout=90, ua=SEC_UA))["facts"]["ifrs-full"]
        years, tags_used = {}, {}
        def put(metric, data):
            for y, (v, tag, filed, accn) in data.items():
                years.setdefault(y, {})[metric] = v
                tags_used.setdefault(metric, set()).add(tag)
        put("revenue", _annual(facts, rev_tags, cur))
        if cid in OPERATING:
            put("operating_profit", _annual(facts, OPERATING[cid], cur))
        for m, (tags, _) in METRICS.items():
            put(m, _annual(facts, tags, cur))
        if len([y for y in years if "net_profit" in years[y]]) < 5:
            raise fetch.SourceError(f"{cid}: fewer than 5 years of net profit parsed")
        for y, d in years.items():  # buybacks/dividends are cash outflows reported positive
            for m in ("dividends_paid", "buybacks", "tax_paid"):
                if m in d:
                    d[m] = abs(d[m])
        out.append({
            "id": cid, "name": name, "sector": sector, "currency": cur, "unit": f"{cur} million",
            "cik": cik, "source_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=20-F",
            "api_url": url, "fiscal_year_end": "31 December", "revenue_note": rev_note,
            "tags": {k: sorted(v) for k, v in tags_used.items()},
            "years": dict(sorted(years.items())),
        })
    return {
        "id": "company_financials", "title": "Company financial results (group, IFRS statutory)",
        "publisher": "Companies' own SEC Form 20-F filings, via SEC EDGAR XBRL API", "updated": date.today().isoformat(),
        "note": ("Group-level statutory IFRS results as filed on Form 20-F, in each company's reporting currency "
                 "(USD for BP, Shell, HSBC; GBP for the others), millions. Not UK-only: group results include overseas "
                 "activity. Statutory, not adjusted or underlying, profit. Financial years end 31 December. "
                 "Coverage is the XBRL era (about 2017 onward). Higher profit does not by itself show price gouging."),
        "limitations": ("Tesco, Sainsbury's, Morrisons, Centrica, EDF and food manufacturers do not file 20-Fs, so are not included. "
                        "Tax paid and tax expense are group-wide, not UK Corporation Tax. A blank means the filer did not tag it."),
        "companies": out,
    }
