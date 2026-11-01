"""Average Band D Council Tax, England (including parish precepts, and adult social care precept where levied).

Keyed by the year the financial year STARTS (2025 = 2025-26), same convention as the tax rules.
- 2012 onward: refreshed from the latest MHCLG 'Council Tax levels set by local authorities in England', Table 3.
- 2002-2011: frozen historical table from the 2011-12 release (Table 1, 'Band D for area', includes parish
  precepts). Values transcribed from that official table; the release is not updated any more.
- 1993-2001 is not integrated (gap): no machine-readable table found.
"""
import io
import json
import re
import zipfile
from datetime import date
from xml.etree import ElementTree as ET

from . import fetch
from .hmrc import NS, T

OLD_SRC = ("https://assets.publishing.service.gov.uk/media/5a796f41ed915d042206863f/1870223.xls")
OLD = {2002: 975.56, 2003: 1101.75, 2004: 1166.56, 2005: 1213.81, 2006: 1267.91,
       2007: 1321.32, 2008: 1373.08, 2009: 1413.84, 2010: 1439.22, 2011: 1439.33}


def _latest_release():
    j = json.loads(fetch.http_get("https://www.gov.uk/api/search.json?q=council+tax+levels+set+by+local+authorities+in+england"
                                  "&count=60&fields=title,link"))
    cands = []
    for r in j["results"]:
        m = re.fullmatch(r"/government/statistics/council-tax-levels-set-by-local-authorities-in-england-(\d{4})-to-(\d{4})(?:-revised)?", r["link"])
        if m:
            cands.append((int(m.group(1)), r["link"]))
    if not cands:
        raise fetch.SourceError("no Council Tax levels release found")
    return max(cands)[1]


def _sheet(blob, name):
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(blob)).read("content.xml"))
    for sh in root.iter(T + "table"):
        if sh.get(T + "name") == name:
            rows = []
            for r in sh.iter(T + "table-row"):
                cells = []
                for c in r.findall(T + "table-cell"):
                    rep = int(c.get(T + "number-columns-repeated", "1"))
                    cells += ["".join("".join(p.itertext()) for p in c.findall("x:p", NS))] * min(rep, 10)
                rows.append(cells)
            return rows
    raise fetch.SourceError(f"sheet {name} missing")


def build():
    link = _latest_release()
    j = json.loads(fetch.http_get("https://www.gov.uk/api/content" + link))
    ods = next((a["url"] for a in j["details"]["attachments"] if a.get("url", "").endswith(".ods")
                and "Tables_1" in a["url"].split("/")[-1]), None)
    if not ods:
        raise fetch.SourceError("Tables 1-9 ods not found")
    rows = _sheet(fetch.http_get(ods, timeout=120), "Table_3")
    values = dict((str(k), v) for k, v in OLD.items())
    for r in rows:
        m = re.match(r"(\d{4}) to (\d{4})", r[0]) if r else None
        if m and len(r) > 1:
            try:
                values[m.group(1)] = float(r[1].replace(",", ""))
            except ValueError:
                pass
    new = [y for y in values if int(y) >= 2012]
    if len(new) < 12 or values.get("2025", 0) < 1500:
        raise fetch.SourceError("Council Tax Table 3 layout changed; refusing to store")
    return {
        "id": "council_tax_band_d", "group": "housing",
        "label": "Average Band D Council Tax, England (£ per year)", "unit": "GBP/year",
        "publisher": "MHCLG (DLUHC) – Council Tax levels set by local authorities in England",
        "source_url": "https://www.gov.uk" + link, "api_url": ods, "geography": "England",
        "source_id": "Table 3 (2012 on); 2011-12 release Table 1 (2002-2011)", "adjustment": "Cash terms",
        "methodology": "Average Band D for the area, including parish precepts and the adult social care precept. Key = year the financial year starts (2025 = 2025-26). "
                       "2002-2011 are from the frozen 2011-12 release (%s); 2012 onward refreshed from the latest release." % OLD_SRC,
        "limitations": "England only (Scotland, Wales and Northern Ireland have different systems). Band D is a reference band, not what the typical household pays: "
                       "most English homes are in Bands A-C, so the average bill is lower. 1993-2001 not integrated. Council Tax benefit/reduction is not modelled.",
        "coverage": [min(values), max(values)], "source_release": link.rsplit("/", 1)[-1], "next_release": "Annually, March",
        "warnings": [], "partial": {}, "values": dict(sorted(values.items())), "last_updated": date.today().isoformat(),
    }
