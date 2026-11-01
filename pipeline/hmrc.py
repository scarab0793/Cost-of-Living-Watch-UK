"""HMRC historical tax-parameter tables -> data/curated/uk_tax_rules.json

Sources (HMRC "Tax structure and parameters statistics", official statistics):
  Table A.1 Income Tax personal allowances      /government/statistics/income-tax-personal-allowances-and-reliefs
  Table A.2 Rates of Income Tax                 /government/statistics/rates-of-income-statistics
  Table A.4 NICs 1999-2000 onwards              /government/statistics/main-features-of-national-insurance-contributions
  Table A.4A NICs 1985-1999                     /government/statistics/main-features-of-national-insurance-contributions-1985-to-1999

URLs of the .ods attachments change with each release, so they are discovered through the GOV.UK
content API at run time. Tax years are keyed by the calendar year in which they START ("2025" = 2025-26).

Modelling notes (all stated on the website):
  * Rates are for England, Wales and Northern Ireland; Scottish income tax differs from 2017-18.
  * Single person, under 65, employee, not contracted out, no pension/student loan/benefits in kind.
  * Where HMRC publishes two values for one year because rates changed mid-year (2022-23, 2023-24) the
    year is split into time-weighted periods, using the dates given in the HMRC footnotes.
"""
import io
import json
import re
import zipfile
from xml.etree import ElementTree as ET

from . import fetch

NS = {"t": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "x": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
T = "{%s}" % NS["t"]
PAGES = {
    "a1": "income-tax-personal-allowances-and-reliefs",
    "a2": "rates-of-income-statistics",
    "a4": "main-features-of-national-insurance-contributions",
    "a4a": "main-features-of-national-insurance-contributions-1985-to-1999",
}


def discover(slug):
    meta = json.loads(fetch.http_get(f"https://www.gov.uk/api/content/government/statistics/{slug}"))
    text = json.dumps(meta)
    links = re.findall(r"https://assets\.publishing\.service\.gov\.uk/[^\"\\ ]+\.ods", text)
    if not links:
        raise fetch.SourceError(f"no .ods attachment found on {slug}")
    return links[0], meta.get("public_updated_at", "")


def read_ods(blob):
    root = ET.fromstring(zipfile.ZipFile(io.BytesIO(blob)).read("content.xml"))
    sheet = next(root.iter(T + "table"))
    rows = []
    for r in sheet.iter(T + "table-row"):
        cells = []
        for c in r.findall(T + "table-cell"):
            rep = int(c.get(T + "number-columns-repeated", "1"))
            txt = "".join("".join(p.itertext()) for p in c.findall("x:p", NS))
            cells += [txt] * min(rep, 40)
        while cells and cells[-1] == "":
            cells.pop()
        rows.append(cells)
    return rows


def money(s):
    m = re.search(r"£?\s*([\d,]+(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def pct_list(s):
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", s or "")]


def year_of(label):
    m = re.match(r"\s*(\d{4}) to (\d{4})", label or "")
    return int(m.group(1)) if m else None


def band(s):
    """'2,001 to 23,700' -> (2001, 23700); 'Over 20,700' -> (20700, None); 'N/A' -> None"""
    if not s or s.startswith("N/A"):
        return None
    s = s.split("(")[0]
    nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+", s) if x.replace(",", "")]
    if s.strip().lower().startswith("over"):
        return (nums[0], None)
    if len(nums) >= 2:
        return (nums[0], nums[1])
    return None


def parse_income_tax(rows_a1, rows_a2):
    pa = {}
    for r in rows_a1:
        y = year_of(r[0]) if r else None
        if y:
            pa[y] = money(r[1])
    out = {}
    for r in rows_a2:
        y = year_of(r[0]) if r else None
        if not y:
            continue
        r = r + [""] * (11 - len(r))
        lower, starting, basic, higher, additional = (band(r[1]), band(r[3]), band(r[5]), band(r[7]), band(r[9]))
        rate = lambda i: pct_list(r[i] + "%") if r[i] and not r[i].startswith("N/A") else []
        num = lambda i: float(re.match(r"\s*([\d.]+)", r[i]).group(1)) if r[i] and re.match(r"\s*[\d.]+", r[i]) else None
        bands = []  # (upper limit of taxable income or None, rate %)
        if lower:
            bands.append((lower[1], num(2)))
        if starting:
            bands.append((starting[1], num(4)))
        bands.append((basic[1], num(6)))
        if additional:  # additional-rate tier exists
            bands.append((higher[1], num(8)))
            bands.append((None, num(10)))
        else:
            bands.append((None, num(8)))
        out[y] = {"label": r[0].strip(), "personal_allowance": pa.get(y), "bands": bands,
                  "pa_taper_above": 100000 if y >= 2010 else None}
    return out


def _col_map(header):
    return {i: year_of(h) for i, h in enumerate(header) if year_of(h)}


def row_by_label(rows, startswith, nth=0):
    hits = [r for r in rows if len(r) > 1 and (r[1] if r[0] == "" or r[0].startswith("Class") else r[0]).startswith(startswith)]
    return hits[nth] if len(hits) > nth else None


def parse_ni(rows_a4a, rows_a4):
    ni = {}
    # ---- 1990-91 .. 1998-99: weekly LEL/UEL, "X% above LEL plus 2% of LEL"
    hdr = next(r for r in rows_a4a if r and r[0] == "NICS Class")
    cmap = _col_map(hdr)
    lel = row_by_label(rows_a4a, "Lower earnings limit")
    uel = row_by_label(rows_a4a, "Upper earnings limit")
    main = next(r for r in rows_a4a if len(r) > 1 and "rate payable on all earnings below UEL" in r[1] and "above LEL" in "".join(r))
    for i, y in cmap.items():
        if 1990 <= y <= 1998:
            m = re.search(r"(\d+(?:\.\d+)?)% above LEL plus (\d+(?:\.\d+)?)% of LEL", main[i])
            if not m:
                raise fetch.SourceError(f"unrecognised NI rule for {y}: {main[i]!r}")
            ni[y] = {"regime": "entry_fee", "periods": [{"months": 12, "lel": money(lel[i]), "pt": None,
                     "uel": money(uel[i]), "main": float(m.group(1)), "entry_fee": float(m.group(2)), "above_uel": 0.0}]}
    # ---- 1999-00 onwards
    hdr = next(r for r in rows_a4 if r and r[0] == "NICS Class")
    cmap = _col_map(hdr)
    lel = row_by_label(rows_a4, "Lower earnings limit")
    pt = row_by_label(rows_a4, "Primary threshold")
    uel = row_by_label(rows_a4, "Upper earnings limit")
    main = row_by_label(rows_a4, "Primary (employee) main contribution rate")
    addl = row_by_label(rows_a4, "Primary (employee) additional contribution rate")
    for i, y in cmap.items():
        if y < 1999:
            continue
        mains, adds, pts = pct_list(main[i]), pct_list(addl[i]) if addl[i] != "N/A" else [0.0], [money(x) for x in re.findall(r"£[\d,]+", pt[i])]
        if y == 1999:  # PT not yet in force; 10% between LEL and UEL (HMRC footnote 6)
            periods = [{"months": 12, "lel": money(lel[i]), "pt": money(lel[i]), "uel": money(uel[i]), "main": mains[0], "above_uel": 0.0}]
        elif y == 2022:  # HSC levy Apr-Nov 2022 (+1.25pp); PT 190 until 5 Jul 2022 then 242
            periods = [{"months": 3, "lel": money(lel[i]), "pt": 190.0, "uel": money(uel[i]), "main": 13.25, "above_uel": 3.25},
                       {"months": 5, "lel": money(lel[i]), "pt": 242.0, "uel": money(uel[i]), "main": 13.25, "above_uel": 3.25},
                       {"months": 4, "lel": money(lel[i]), "pt": 242.0, "uel": money(uel[i]), "main": 12.0, "above_uel": 2.0}]
        elif y == 2023:  # 12% to 5 Jan 2024 (9 months), 10% from 6 Jan 2024 (3 months)
            periods = [{"months": 9, "lel": money(lel[i]), "pt": money(pt[i]), "uel": money(uel[i]), "main": 12.0, "above_uel": 2.0},
                       {"months": 3, "lel": money(lel[i]), "pt": money(pt[i]), "uel": money(uel[i]), "main": 10.0, "above_uel": 2.0}]
        else:
            if len(mains) != 1 or len(pts) > 1:
                raise fetch.SourceError(f"unexpected multi-value NI cell for {y}: {main[i]!r} / {pt[i]!r}")
            periods = [{"months": 12, "lel": money(lel[i]), "pt": pts[0] if pts else money(lel[i]),
                        "uel": money(uel[i]), "main": mains[0], "above_uel": adds[0] if adds else 0.0}]
        ni[y] = {"regime": "threshold", "periods": periods}
    return ni


def build():
    blobs, updated = {}, {}
    for key, slug in PAGES.items():
        url, upd = discover(slug)
        blobs[key] = (url, fetch.http_get(url))
        updated[key] = {"url": url, "page": f"https://www.gov.uk/government/statistics/{slug}", "updated": upd}
    rows = {k: read_ods(v[1]) for k, v in blobs.items()}
    it = parse_income_tax(rows["a1"], rows["a2"])
    ni = parse_ni(rows["a4a"], rows["a4"])
    years = sorted(set(it) & set(ni))
    if len(years) < 30 or years[0] != 1990:
        raise fetch.SourceError(f"implausible year coverage {years[:3]}..{years[-3:]}")
    out = {
        "id": "uk_tax_rules", "title": "Income Tax and Employee National Insurance rules by tax year",
        "publisher": "HM Revenue & Customs (official statistics)",
        "sources": updated, "key": "Tax year start (2025 = 2025-26)",
        "scope": "England, Wales and Northern Ireland; single person under 65; employee, not contracted out",
        "limitations": ("Scottish income tax bands differ from 2017-18. Ignores pension contributions, student loan, "
                        "tax credits, benefits in kind and Class 1 contracting-out. 2022-23 and 2023-24 NI are "
                        "time-weighted across in-year rate changes."),
        "years": {str(y): {"income_tax": it[y], "ni": ni[y]} for y in years},
    }
    return out
