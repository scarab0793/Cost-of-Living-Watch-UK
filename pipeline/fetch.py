"""Fetchers for official UK statistical sources. Standard library only.

Every fetcher returns a dict:
    {"annual": {"1990": 1.0, ...},      # observations for complete years
     "partial": {"2026": {"mean": x, "months": 9, "last": "2026-09"}},
     "meta": {...}}                    # title / release info taken from the source itself

Nothing here estimates or interpolates. A year is only in "annual" if the
publisher gave an annual figure, or if all 12 monthly observations exist.
"""
import csv
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "UK-Living-Cost-Watch/3.0 (public statistics; github.com/scarab0793/Cost-of-Living-Watch-UK)"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}
_last_call = {}


class SourceError(Exception):
    pass


def http_get(url, timeout=60, tries=4, min_gap=2.0, ua=None):
    """GET with polite throttling per host, retry on 429/5xx with backoff."""
    host = urllib.parse.urlsplit(url).netloc
    delay = 5
    for attempt in range(1, tries + 1):
        wait = min_gap - (time.time() - _last_call.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua or UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if not retryable or attempt == tries:
                raise SourceError(f"HTTP {exc.code} for {url}") from exc
            retry_after = exc.headers.get("Retry-After")
            time.sleep(int(retry_after) if retry_after and retry_after.isdigit() else delay)
            delay *= 2
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == tries:
                raise SourceError(f"{type(exc).__name__} for {url}: {exc}") from exc
            time.sleep(delay)
            delay *= 2
    raise SourceError(f"gave up on {url}")


def _num(text):
    text = (text or "").strip().replace(",", "")
    if text in ("", "-", "..", "x", "[x]", "N/A"):
        return None
    return float(text)


def _summarise_monthly(monthly):
    """monthly: {(year, month): value} -> (annual for full years, partial for incomplete)."""
    by_year = {}
    for (y, m), v in monthly.items():
        by_year.setdefault(y, {})[m] = v
    annual, partial = {}, {}
    for y, ms in sorted(by_year.items()):
        mean = sum(ms.values()) / len(ms)
        if len(ms) == 12:
            annual[str(y)] = mean
        else:
            partial[str(y)] = {"mean": mean, "months": len(ms), "last": f"{y}-{max(ms):02d}"}
    return annual, partial


# --------------------------------------------------------------------------- ONS
ONS_TOPICS = {
    "mm23": "economy/inflationandpriceindices",
    "emp": "employmentandlabourmarket/peopleinwork/earningsandworkinghours",
    "pusf": "economy/governmentpublicsectorandtaxes/publicsectorfinance",
    "qna": "economy/grossdomesticproductgdp",
    "ukea": "economy/grossdomesticproductgdp",
}


def ons_timeseries(cdid, dataset):
    topic = ONS_TOPICS[dataset]
    uri = f"/{topic}/timeseries/{cdid.lower()}/{dataset}"
    url = "https://www.ons.gov.uk/generator?format=csv&uri=" + uri
    text = http_get(url).decode("utf-8-sig", errors="replace")
    meta, annual, monthly = {}, {}, {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        key = row[0].strip()
        if key in ("Title", "CDID", "Source dataset ID", "Unit", "PreUnit", "Release date", "Next release"):
            meta[key] = row[1].strip()
            continue
        if re.fullmatch(r"\d{4}", key):
            try:
                v = _num(row[1])
            except ValueError:
                continue
            if v is not None:
                annual[key] = v
            continue
        m = re.fullmatch(r"(\d{4}) ([A-Z]{3})", key)
        if m and m.group(2) in MONTHS:
            try:
                v = _num(row[1])
            except ValueError:
                continue
            if v is not None:
                monthly[(int(m.group(1)), MONTHS[m.group(2)])] = v
    if not meta.get("Title"):
        raise SourceError(f"ONS response for {cdid}/{dataset} had no title (not a series CSV?)")
    meta["source_url"] = f"https://www.ons.gov.uk{uri}"
    partial = {}
    if monthly:
        m_annual, m_partial = _summarise_monthly(monthly)
        # Use ONS's own annual figure where it exists; only fall back to monthly for partial years.
        for y, p in m_partial.items():
            if y not in annual:
                partial[y] = p
    return {"annual": annual, "partial": partial, "meta": meta, "api_url": url}


# --------------------------------------------------------------------------- Bank of England
def boe_iadb(code, date_from="01/Jan/1990"):
    url = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes"
           f"&Datefrom={date_from}&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
    rows = []
    for attempt in range(4):
        text = http_get(url).decode("utf-8-sig", errors="replace")
        rows = list(csv.reader(io.StringIO(text)))
        if rows and rows[0][:1] == ["DATE"]:
            break
        time.sleep(5 * (attempt + 1))
    else:
        raise SourceError(f"BoE IADB response for {code} was not a CSV table after retries")
    by_month = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        try:
            dt = time.strptime(row[0].strip(), "%d %b %Y")
            v = _num(row[1])
        except ValueError:
            continue
        if v is not None:
            by_month.setdefault((dt.tm_year, dt.tm_mon), []).append(v)
    # One value per calendar month: mean of the observations in that month
    monthly = {k: sum(v) / len(v) for k, v in by_month.items()}
    annual, partial = _summarise_monthly(monthly)
    return {"annual": annual, "partial": partial, "meta": {"Title": rows[0][1] if len(rows[0]) > 1 else code}, "api_url": url}


# --------------------------------------------------------------------------- Land Registry
HPI_REGIONS = {
    "united-kingdom": "United Kingdom", "england": "England", "wales": "Wales",
    "scotland": "Scotland", "northern-ireland": "Northern Ireland",
    "north-east": "North East", "north-west": "North West",
    "yorkshire-and-the-humber": "Yorkshire and The Humber", "east-midlands": "East Midlands",
    "west-midlands": "West Midlands", "east-of-england": "East of England",
    "london": "London", "south-east": "South East", "south-west": "South West",
}


def landregistry_hpi(region, field="average price"):
    monthly = {}
    page = 0
    while page < 10:
        url = (f"https://landregistry.data.gov.uk/data/ukhpi/region/{region}.csv"
               f"?_pageSize=200&_page={page}&_sort=refMonth&min-refMonth=1990-01&_view=all")
        text = http_get(url, timeout=90).decode("utf-8-sig", errors="replace")
        n_rows = 0
        for row in csv.DictReader(io.StringIO(text)):
            n_rows += 1
            ref = row.get("ref month", "")
            m = re.fullmatch(r"(\d{4})-(\d{2})", ref)
            if not m:
                continue
            try:
                v = _num(row.get(field, ""))
            except ValueError:
                continue
            if v is not None:
                monthly[(int(m.group(1)), int(m.group(2)))] = v
        if n_rows < 200:
            break
        page += 1
    if not monthly:
        raise SourceError(f"Land Registry returned no {field} rows for {region}")
    annual, partial = _summarise_monthly(monthly)
    return {"annual": annual, "partial": partial,
            "meta": {"Title": f"UK HPI {field}, {HPI_REGIONS.get(region, region)}"}, "api_url": url}


# --------------------------------------------------------------------------- World Bank
def worldbank(code):
    url = f"https://api.worldbank.org/v2/country/GBR/indicator/{code}?format=json&per_page=200"
    raw = json.loads(http_get(url, timeout=40))
    if not isinstance(raw, list) or len(raw) < 2 or not raw[1]:
        raise SourceError(f"World Bank returned no rows for {code}")
    annual = {r["date"]: r["value"] for r in raw[1]
              if r.get("value") is not None and str(r.get("date", "")).isdigit() and int(r["date"]) >= 1990}
    title = raw[1][0].get("indicator", {}).get("value", code)
    return {"annual": dict(sorted(annual.items())), "partial": {}, "meta": {"Title": title}, "api_url": url}
