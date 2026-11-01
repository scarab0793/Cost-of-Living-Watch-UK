"""Non-catalogue refresh jobs: World Bank context indicators, GOV.UK news, one-off archives."""
import io
import json
import sys
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

from . import fetch

WB_INDICATORS = {
    "cpi": ("FP.CPI.TOTL", "Consumer price index (2010=100)", "index"),
    "inflation": ("FP.CPI.TOTL.ZG", "Consumer price inflation (annual %)", "%"),
    "gdp_per_capita": ("NY.GDP.PCAP.CD", "GDP per capita (current US$)", "US$"),
    "unemployment": ("SL.UEM.TOTL.ZS", "Unemployment (% of labour force, modelled ILO estimate)", "%"),
    "gdp_per_capita_ppp": ("NY.GDP.PCAP.PP.KD", "GDP per capita (constant 2021 international $ PPP)", "2021 international $"),
    "household_consumption_share": ("NE.CON.PRVT.ZS", "Household consumption expenditure (% of GDP)", "%"),
    "renewable_electricity_share": ("EG.ELC.RNEW.ZS", "Renewable electricity output (% of total electricity output)", "%"),
    "energy_use": ("EG.USE.PCAP.KG.OE", "Energy use (kg of oil equivalent per capita)", "kg oil eq."),
    "income_share_lowest": ("SI.DST.FRST.20", "Income share held by lowest 20%", "%"),
    "income_share_highest": ("SI.DST.05TH.20", "Income share held by highest 20%", "%"),
    "gini": ("SI.POV.GINI", "Gini index (income inequality)", "index"),
    "life_expectancy": ("SP.DYN.LE00.IN", "Life expectancy at birth (years)", "years"),
    "government_expenditure_share": ("NE.CON.GOVT.ZS", "General government final consumption expenditure (% of GDP)", "%"),
    "tax_share": ("GC.TAX.TOTL.GD.ZS", "Tax revenue (% of GDP; central government)", "%"),
    "household_consumption": ("NE.CON.PRVT.PC.KD", "Household final consumption expenditure per capita (constant 2015 US$)", "2015 US$"),
}


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def worldbank_context(data):
    """World Bank context indicators (supplementary; UK-specific sources take priority elsewhere)."""
    path = data / "economic.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {"series": {}}
    series = dict(previous.get("series", {}))
    # Remove entries the earlier pipeline mislabelled or that are now served by data/series/*.json
    for stale in ("ons_cpi_index", "ons_cpi_inflation", "ons_cpih_inflation", "ons_earnings_weekly",
                  "ons_earnings_regular", "ons_house_price", "electricity_access", "fuel_imports_share",
                  "government_revenue_share"):
        series.pop(stale, None)
    ok = 0
    for key, (code, label, unit) in WB_INDICATORS.items():
        try:
            r = fetch.worldbank(code)
            if len(r["annual"]) < 5:
                raise fetch.SourceError("too few observations")
            series[key] = {"label": label, "unit": unit, "indicator": code, "publisher": "World Bank",
                           "source_url": f"https://data.worldbank.org/indicator/{code}?locations=GB",
                           "values": r["annual"]}
            ok += 1
        except Exception as exc:
            print("WB   FAIL", key, exc, "-> kept previous" if key in series else "")
    out = {"country": "United Kingdom", "provider": "World Bank Open Data",
           "provider_url": "https://data.worldbank.org/country/united-kingdom", "series": series}
    if ok >= 3 and _write(path, out):
        print(f"WB   economic.json updated ({ok} indicators refreshed)")


def news(data):
    feeds = {
        "HM Treasury": "https://www.gov.uk/government/organisations/hm-treasury.atom",
        "HMRC": "https://www.gov.uk/government/organisations/hm-revenue-customs.atom",
        "Energy Security & Net Zero": "https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero.atom",
    }
    items, ns = [], {"a": "http://www.w3.org/2005/Atom"}
    for source, url in feeds.items():
        try:
            root = ET.fromstring(fetch.http_get(url, timeout=30))
            for entry in root.findall("a:entry", ns)[:20]:
                title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                when = entry.findtext("a:updated", default="", namespaces=ns)
                link = next((x.get("href") for x in entry.findall("a:link", ns)
                             if x.get("rel", "alternate") == "alternate"), "")
                if title and link.startswith("https://www.gov.uk/"):
                    items.append({"title": title, "date": when, "url": link, "source": source})
        except Exception as exc:
            print("NEWS FAIL", source, exc)
    if items:
        items = sorted({x["url"]: x for x in items}.values(), key=lambda x: x["date"], reverse=True)[:45]
        if _write(data / "stories.json", items):
            print("NEWS stories.json updated")
    else:
        print("NEWS none fetched; previous stories preserved")


def millennium(data, force=False):
    """Bank of England 'A millennium of macroeconomic data' v3.1 — composite average weekly earnings
    (sheet A47, GBP). Static historical archive ending 2016; used only to cover 1990-1999 before the
    ONS AWE series begins. Not re-downloaded unless forced."""
    out = data / "series" / "earnings_boe_composite.json"
    if out.exists() and not force:
        return
    try:
        import openpyxl  # optional dependency, only needed for this one-off
    except ImportError:
        print("MILL skipped: openpyxl not installed (pip install openpyxl)")
        return
    url = ("https://www.bankofengland.co.uk/-/media/boe/files/statistics/research-datasets/"
           "a-millennium-of-macroeconomic-data-for-the-uk.xlsx")
    try:
        blob = fetch.http_get(url, timeout=300)
        wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
        ws = wb["A47. Wages and prices"]
        hdr = None
        values = {}
        for row in ws.iter_rows(values_only=True):
            if row and isinstance(row[1], str) and "Composite Average Weekly Earnings" in row[1]:
                hdr = row[1]
            try:
                y = int(row[0])
            except (TypeError, ValueError):
                continue
            if 1990 <= y <= 2016 and row[1] not in (None, ""):
                values[str(y)] = round(float(row[1]), 2)
        if hdr is None or len(values) < 20:
            raise fetch.SourceError("A47 layout changed; refusing to store")
        rec = {
            "id": "earnings_boe_composite", "group": "earnings",
            "label": "Composite average weekly earnings (£/week), Bank of England historical dataset",
            "publisher": "Bank of England (compiled from ONS and earlier official sources)",
            "source_url": "https://www.bankofengland.co.uk/statistics/research-datasets",
            "api_url": url, "source_title": hdr, "source_id": "A47 col B", "unit": "GBP/week",
            "geography": "GB/UK", "adjustment": "Original",
            "methodology": "Composite earnings series spliced by the BoE from official sources.",
            "limitations": "Ends 2016. Definition differs from ONS AWE (2000 onward): the two overlap in "
                           "2000-2016 and differ by a few percent; do not treat the splice as one survey.",
            "coverage": [min(values), max(values)], "source_release": "v3.1", "next_release": "",
            "warnings": [], "values": values, "partial": {}, "last_updated": date.today().isoformat(),
        }
        _write(out, rec)
        print(f"MILL earnings_boe_composite {min(values)}-{max(values)}")
        # Building societies' basic (standard variable) mortgage rate, monthly 1990-2016 (ONS series AJNK)
        ws = wb["M12. Mthly HH loan rates 1939+"]
        by_year = {}
        for row in ws.iter_rows(values_only=True):
            try:
                y = int(row[0])
            except (TypeError, ValueError):
                continue
            if 1990 <= y <= 2016 and row[4] not in (None, ""):
                by_year.setdefault(y, []).append(float(row[4]))
        rates = {str(y): round(sum(v) / len(v), 3) for y, v in sorted(by_year.items()) if len(v) == 12}
        if len(rates) < 5:
            raise fetch.SourceError("M12 layout changed; refusing to store mortgage rates")
        rec2 = dict(rec, id="mortgage_svr_bs_hist", group="housing",
                    label="Building societies' basic (standard variable) mortgage rate (%)",
                    source_title="M12 col E: Basic rate on Mortgages Building Societies (ONS series code AJNK)",
                    source_id="M12 col E / ONS AJNK", unit="%",
                    methodology="Mean of 12 monthly observations, from the BoE historical dataset (compiled from ONS).",
                    limitations="Series ends 1995; used only to bridge 1990-1994 before the BoE quoted-rate series (IUMTLMV) begins. "
                               "Different institution mix from the BoE series; 1995 overlaps for comparison.",
                    coverage=[min(rates), max(rates)], values=rates)
        _write(data / "series" / "mortgage_svr_bs_hist.json", rec2)
        print(f"MILL mortgage_svr_bs_hist {min(rates)}-{max(rates)}")
    except Exception as exc:
        print("MILL FAIL", exc)


def tax_rules(data):
    """HMRC income tax + NI rules by tax year -> data/curated/uk_tax_rules.json (last good kept on failure)."""
    from . import hmrc
    try:
        out = hmrc.build()
        if _write(data / "curated" / "uk_tax_rules.json", out):
            print(f"HMRC uk_tax_rules.json updated ({len(out['years'])} tax years)")
        else:
            print("HMRC uk_tax_rules.json unchanged")
    except Exception as exc:
        print("HMRC FAIL", exc, "-> kept previous tax rules")


def energy_bills(data):
    """DESNZ annual domestic energy bills -> data/series/energy_*.json (last good kept on failure)."""
    from . import desnz
    try:
        for rec in desnz.build():
            path = data / "series" / f"{rec['id']}.json"
            try:
                old = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                old = None
            if old and len(old["values"]) - len(rec["values"]) > 2:
                print("DESNZ", rec["id"], "REJECTED: would drop observations; kept previous")
                continue
            if old and old["values"] == rec["values"]:
                rec["last_updated"] = old["last_updated"]
            if _write(path, rec):
                print(f"DESNZ {rec['id']} updated {rec['coverage']}")
    except Exception as exc:
        print("DESNZ FAIL", exc, "-> kept previous energy bills")


def company_financials(data):
    """SEC EDGAR 20-F facts; on any failure the previous file is kept untouched."""
    from . import edgar
    path = data / "curated" / "company_financials.json"
    try:
        _write(path, edgar.build())
    except Exception as exc:  # noqa: BLE001 - preserve last good data
        print(f"company_financials: kept previous data ({exc})", file=sys.stderr)


def _series_files(data, builder, label):
    """Write one or more series JSON files; on failure keep whatever is already there."""
    try:
        recs = builder()
        for rec in (recs if isinstance(recs, list) else [recs]):
            _write(data / "series" / (rec["id"] + ".json"), rec)
            print(f"{label} {rec['id']} {rec['coverage'][0]}-{rec['coverage'][1]}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: kept previous data ({exc})", file=sys.stderr)


def run(data, static=False, news_on=True, **kw):
    company_financials(data)
    from . import ashe, council_tax
    _series_files(data, ashe.build, "ASHE")
    _series_files(data, council_tax.build_bands, "COUNCILTAX")
    _series_files(data, council_tax.build_scotland, "COUNCILTAX-SCOT")
    _series_files(data, council_tax.build_wales, "COUNCILTAX-WALES")
    worldbank_context(data)
    tax_rules(data)
    energy_bills(data)
    if kw.get("news", news_on):
        news(data)
    millennium(data, force=static)
