#!/usr/bin/env python3
"""Update independently published UK economic series and official headlines.
No AI, no synthetic observations. Keep last good file on upstream failures.
"""
import json
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
    news()
