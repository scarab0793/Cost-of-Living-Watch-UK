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


# Statutory England valuation-band ratios to Band D (Local Government Finance Act 1992): A 6/9 ... H 18/9.
BAND_RATIO = {"a": (6, 9), "b": (7, 9), "c": (8, 9), "d": (9, 9), "e": (11, 9), "f": (13, 9), "g": (15, 9), "h": (18, 9)}


def build_bands():
    """Per-band England average bills, derived from average Band D with the statutory ratios.
    Checked against the authority-level Table 9 of the latest release (Camden A = 6/9 of D)."""
    d = build()
    out = [d]
    for b, (n, m) in BAND_RATIO.items():
        if b == "d":
            continue
        out.append(dict(d, id=f"council_tax_band_{b}", label=f"Average Band {b.upper()} Council Tax, England (£ per year)",
                        derived=True, source_id="derived from Band D",
                        methodology=d["methodology"] + f" Band {b.upper()} = Band D x {n}/{m}, the fixed statutory ratio for England (applies equally to every authority).",
                        limitations=d["limitations"] + " Derived arithmetically, not separately published as an England average.",
                        values={y: round(v * n / m, 2) for y, v in d["values"].items()}))
    return out


# ---------------------------------------------------------------------------------------------
# Scotland and Wales. Northern Ireland has no Council Tax (domestic rates on capital value): see gaps.

PLAIN_UA = "UK-Living-Cost-Watch/3.0 (public statistics)"  # gov.scot returns an empty page for the longer UA
SCOT_PAGE = "https://www.gov.scot/publications/council-tax-datasets/"
WALES_DS = "https://stats.gov.wales/en-GB/3ca971eb-7d9b-4b79-89fa-6d7f77431aad"
ENG_RATIO = {"a": (6, 9), "b": (7, 9), "c": (8, 9), "d": (9, 9), "e": (11, 9), "f": (13, 9), "g": (15, 9), "h": (18, 9)}
SCOT_NEW = {"a": (240, 360), "b": (280, 360), "c": (320, 360), "d": (360, 360), "e": (473, 360),
            "f": (585, 360), "g": (705, 360), "h": (882, 360)}  # from 2017-18, as printed in the gov.scot band file
WALES_NEW = dict(ENG_RATIO, i=(21, 9))  # 2005 revaluation added band I


def _bands(base, d, ratio_for_year, label_geo, extra_lim):
    out = [dict(base, id=f"council_tax_{label_geo[0]}_band_d")]
    letters = sorted({b for y in d["values"] for b in ratio_for_year(int(y))})
    for b in letters:
        if b == "d":
            continue
        vals = {y: round(v * ratio_for_year(int(y))[b][0] / ratio_for_year(int(y))[b][1], 2)
                for y, v in d["values"].items() if b in ratio_for_year(int(y))}
        out.append(dict(base, id=f"council_tax_{label_geo[0]}_band_{b}", derived=True,
                        label=f"Average Band {b.upper()} Council Tax, {label_geo[1]} (£ per year)",
                        source_id="derived from Band D", values=vals, coverage=[min(vals), max(vals)],
                        methodology=base["methodology"] + f" Band {b.upper()} = Band D x the statutory ratio in force that year.",
                        limitations=base["limitations"] + " Derived arithmetically from the published average Band D."))
    out[0]["label"] = f"Average Band D Council Tax, {label_geo[1]} (£ per year)"
    return out


def _scot_get(url, timeout=90):
    """gov.scot sometimes answers 202 with an empty body while it warms the page; retry until content arrives."""
    import time
    for _ in range(8):
        body = fetch.http_get(url, timeout=timeout, ua=PLAIN_UA)
        if body:
            return body
        time.sleep(6)
    raise fetch.SourceError(f"gov.scot returned an empty body for {url}")


def build_scotland():
    import openpyxl
    html = _scot_get(SCOT_PAGE).decode("utf8", "ignore")
    m = re.search(r'href="([^"]+Band%2BD%2BCouncil%2BTax%2Brates%2Bby%2Byear[^"]+\.xlsx)"', html)
    if not m:
        raise fetch.SourceError("Scottish Band D by year file not found")
    url = "https://www.gov.scot" + m.group(1)
    ws = openpyxl.load_workbook(io.BytesIO(_scot_get(url, 120)), read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    hdr = next(r for r in rows if r and r[1] and re.match(r"1996-97", str(r[1])))
    scot = next(r for r in rows if r and str(r[0]).strip() == "Scotland")
    values = {}
    for h, v in zip(hdr[1:], scot[1:]):
        mm = re.match(r"(\d{4})-\d\d", str(h or ""))
        if mm and isinstance(v, (int, float)):
            values[mm.group(1)] = round(float(v), 2)
    if len(values) < 28 or values.get("2025", 0) < 1200:
        raise fetch.SourceError("Scottish Band D layout changed; refusing to store")
    base = {"group": "housing", "unit": "GBP/year", "publisher": "Scottish Government – Council Tax datasets (Council Tax Assumptions)",
            "source_url": SCOT_PAGE, "api_url": url, "geography": "Scotland", "adjustment": "Cash terms",
            "source_release": url.rsplit("/", 1)[-1].replace("%2B", " "), "next_release": "Annually, spring", "warnings": [], "partial": {},
            "coverage": [min(values), max(values)], "values": dict(sorted(values.items())), "last_updated": date.today().isoformat(),
            "source_id": "Scotland row, Band D Council Tax by year",
            "methodology": "Scotland average Band D (weighted by Band D equivalents), key = year the financial year starts (2025 = 2025-26). "
                           "Band ratios: England-style 6/9...18/9 until 2016-17; 240/360...882/360 from 2017-18 (higher bands E-H pay more).",
            "limitations": "Scotland only. Band D is a reference band, not the typical bill. Water and waste-water charges (billed with Council Tax in Scotland) are not included. Council Tax Reduction not modelled."}
    ratio = lambda y: SCOT_NEW if y >= 2017 else ENG_RATIO
    return _bands(base, base, ratio, ("scotland", "Scotland"), "")


def _wales_csv():
    import http.cookiejar
    import urllib.parse
    import urllib.request
    jar = http.cookiejar.CookieJar()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)
    hdr = {"User-Agent": "Mozilla/5.0 UK-Living-Cost-Watch", "Referer": WALES_DS, "Origin": "https://stats.gov.wales"}
    opener.open(urllib.request.Request(WALES_DS, headers=hdr), timeout=60).read()
    data = urllib.parse.urlencode({"view_type": "unfiltered", "format": "csv", "view_choice": "raw", "extended": "no",
                                   "download_language": "en-GB", "selected_filter_options": "[]"}).encode()
    try:
        opener.open(urllib.request.Request(WALES_DS + "/download", data=data, headers=hdr), timeout=60)
        raise fetch.SourceError("StatsWales download did not redirect")
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303):
            raise fetch.SourceError(f"StatsWales download HTTP {e.code}") from e
        loc = e.headers["Location"]
    import time
    for _ in range(5):
        try:
            r = opener.open(urllib.request.Request("https://stats.gov.wales" + loc, headers=hdr), timeout=120)
            return r.read().decode("utf-8-sig")
        except urllib.error.HTTPError:
            time.sleep(4)
    raise fetch.SourceError("StatsWales CSV not available")


def build_wales():
    import csv
    values = {}
    for r in csv.DictReader(io.StringIO(_wales_csv())):
        if (r["Row"] == "Total CT for billing authority area" and r["Authority"] == "Total Unitary Authorities"
                and r["Data description"].startswith("£") and r["Data values"]):
            values[r["Year"][:4]] = round(float(r["Data values"]), 2)
    if len(values) < 30 or not 2000 < values.get("2025", 0) < 3000:
        raise fetch.SourceError("StatsWales Band D layout changed; refusing to store")
    base = {"group": "housing", "unit": "GBP/year", "publisher": "Welsh Government – Council tax levels (StatsWales: Composition of average band D council tax by billing authority)",
            "source_url": WALES_DS, "api_url": WALES_DS + "/download", "geography": "Wales", "adjustment": "Cash terms",
            "source_release": "StatsWales dataset 3ca971eb (accredited official statistics)", "next_release": "March each year", "warnings": [], "partial": {},
            "coverage": [min(values), max(values)], "values": dict(sorted(values.items())), "last_updated": date.today().isoformat(),
            "source_id": "Total CT for billing authority area, Total Unitary Authorities",
            "methodology": "Wales average Band D including community council and police elements, key = year the financial year starts (2025 = 2025-26). "
                           "Band ratios: 6/9...18/9 until 2004-05; band I (21/9) added with the 2005 revaluation.",
            "limitations": "Wales only. Band D is a reference band, not the typical bill. The 2005 revaluation moved homes between bands, so bills for a given band are not like-for-like across 2004/05. Council Tax Reduction not modelled."}
    ratio = lambda y: WALES_NEW if y >= 2005 else ENG_RATIO
    return _bands(base, base, ratio, ("wales", "Wales"), "")
