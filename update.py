#!/usr/bin/env python3
"""Update independently published UK economic series and official headlines.
No AI, no synthetic observations. Keep last good file on upstream failures.
"""
import json
import csv
import io
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
HEADERS = {"User-Agent": "UK-Living-Cost-Watch/2.0 (public statistics; github.com/scarab0793/Cost-of-Living-Watch-UK)"}
INDICATORS = {
    "cpi": ("FP.CPI.TOTL", "Consumer price index (2010=100)", "index"),
    "inflation": ("FP.CPI.TOTL.ZG", "Consumer price inflation (annual %)", "%"),
    "gdp_per_capita": ("NY.GDP.PCAP.CD", "GDP per capita (current US$)", "US$"),
    "unemployment": ("SL.UEM.TOTL.ZS", "Unemployment (% of labour force, modelled ILO estimate)", "%"),
    "gdp_per_capita_ppp": ("NY.GDP.PCAP.PP.KD", "GDP per capita (constant 2021 international $ PPP)", "2021 international $"),
    "household_consumption_share": ("NE.CON.PRVT.ZS", "Household consumption expenditure (% of GDP)", "%"),
    "electricity_access": ("EG.ELC.ACCS.ZS", "Access to electricity (% of population)", "%"),
    "renewable_electricity_share": ("EG.ELC.RNEW.ZS", "Renewable electricity output (% of total electricity output)", "%"),
    "energy_use": ("EG.USE.PCAP.KG.OE", "Energy use (kg of oil equivalent per capita)", "kg oil eq."),
    "fuel_imports_share": ("TM.VAL.FUEL.ZS.UN", "Fuel imports (% of merchandise imports)", "%"),
    "income_share_lowest": ("SI.DST.FRST.20", "Income share held by lowest 20%", "%"),
    "income_share_highest": ("SI.DST.05TH.20", "Income share held by highest 20%", "%"),
    "gini": ("SI.POV.GINI", "Gini index (income inequality)", "index"),
    "life_expectancy": ("SP.DYN.LE00.IN", "Life expectancy at birth (years)", "years"),
    "government_expenditure_share": ("NE.CON.GOVT.ZS", "General government final consumption expenditure (% of GDP)", "%"),
    "tax_share": ("GC.TAX.TOTL.GD.ZS", "Tax revenue (% of GDP; central government)", "%"),
    "government_revenue_share": ("GC.REV.XGRT.GD.ZS", "Revenue excluding grants (% of GDP)", "%"),
    "household_consumption": ("NE.CON.PRVT.PC.KD", "Household final consumption expenditure per capita (constant 2015 US$)", "2015 US$"),
}

def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as r:
        return json.load(r)

def write_if_changed(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        print("Updated", path.relative_to(ROOT))
    else:
        print("Unchanged", path.relative_to(ROOT))

def economic():
    output = {"country": "United Kingdom", "provider": "World Bank Open Data", "provider_url": "https://data.worldbank.org/country/united-kingdom", "series": {}}
    for key, (code, label, unit) in INDICATORS.items():
        try:
            url = f"https://api.worldbank.org/v2/country/GBR/indicator/{code}?format=json&per_page=150"
            raw = get_json(url)
            values = {str(int(r["date"])): r["value"] for r in raw[1] if r.get("value") is not None and r.get("date", "").isdigit() and 1990 <= int(r["date"]) <= 2026}
            if not values:
                print("No observations:", key)
                continue
            output["series"][key] = {"label": label, "unit": unit, "indicator": code, "source_url": f"https://data.worldbank.org/indicator/{code}?locations=GB", "values": dict(sorted(values.items()))}
            print(key, len(values), "observations")
        except Exception as exc:
            print("Series error:", key, exc)
    if len(output["series"]) >= 3:
        write_if_changed(ROOT / "data" / "economic.json", output)
    else:
        print("Insufficient economic series; preserving last good data")

def ons_series():
    """Add ONS published UK monthly time-series, using annual observations only."""
    source = {
        "ons_cpi_index": ("mm23", "d7bt", "ONS CPI all items index (2015=100)", "index"),
        "ons_cpi_inflation": ("mm23", "d7g7", "ONS CPI all items 12-month rate", "%"),
        "ons_cpih_inflation": ("mm23", "l55o", "ONS CPIH all items 12-month rate", "%"),
    }
    target = ROOT / "data" / "economic.json"
    if not target.exists():
        print("ONS series skipped: economic.json absent")
        return
    data = json.loads(target.read_text(encoding="utf-8"))
    count = 0
    for key, (dataset, code, label, unit) in source.items():
        try:
            url = f"https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/{code}/{dataset}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=25) as response:
                lines = response.read().decode("utf-8-sig", errors="replace").splitlines()
            annual = {}
            for row in csv.reader(lines):
                if len(row) < 2:
                    continue
                year = row[0].strip().strip('"')
                if len(year) != 4 or not year.isdigit() or not 1990 <= int(year) <= 2026:
                    continue
                try:
                    annual[year] = float(row[1].strip())
                except ValueError:
                    pass
            if len(annual) >= 5:
                data["series"][key] = {
                    "label": label, "unit": unit, "indicator": code.upper(),
                    "source_url": f"https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/{code}/{dataset}",
                    "values": dict(sorted(annual.items()))
                }
                count += 1
                print("ONS", key, len(annual), "years")
            else:
                print("ONS series missing annual rows", key)
        except Exception as exc:
            print("ONS series error", key, exc)
    if count:
        write_if_changed(target, data)

def news():
    feeds = {
        "HM Treasury": "https://www.gov.uk/government/organisations/hm-treasury.atom",
        "HMRC": "https://www.gov.uk/government/organisations/hm-revenue-customs.atom",
        "Energy Security & Net Zero": "https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero.atom",
    }
    items = []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for source, url in feeds.items():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
                root = ET.fromstring(r.read())
            for entry in root.findall("a:entry", ns)[:20]:
                title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                date = entry.findtext("a:updated", default="", namespaces=ns)
                link = next((x.get("href") for x in entry.findall("a:link", ns) if x.get("rel", "alternate") == "alternate"), "")
                if title and link and link.startswith("https://www.gov.uk/"):
                    items.append({"title": title, "date": date, "url": link, "source": source})
        except Exception as exc:
            print("News feed error:", source, exc)
    if items:
        items = sorted({x["url"]: x for x in items}.values(), key=lambda x: x["date"], reverse=True)[:45]
        write_if_changed(ROOT / "data" / "stories.json", items)
    else:
        print("No news; preserving last good data")

if __name__ == "__main__":
    economic()
    ons_series()
    news()
