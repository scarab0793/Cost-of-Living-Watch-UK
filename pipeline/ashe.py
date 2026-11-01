"""ASHE / NES median gross weekly earnings, full-time adults (ONS dataset, xlsx).

Writes two series (never merged here):
  earnings_median_ft       UK, ASHE, 1997 onward (all adults, 10th/25th/75th/90th percentile also kept in `percentiles`)
  earnings_median_ft_nes   GB, New Earnings Survey, 1990-1996 (a different survey, so kept separate)
"""
import io
import re
from datetime import date

from . import fetch

PAGE = ("https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/"
        "earningstimeseriesofmediangrossweeklyearningsfrom1968to2022")
COLS = {"p10": 23, "p25": 25, "median": 27, "p75": 29, "p90": 31}  # 'Male & Female Adult' block


def _table(ws):
    rows = list(ws.iter_rows(values_only=True))
    if "Male & Female Adult" not in [v for v in rows[6] if v] or rows[7][27] != 0.5:
        raise fetch.SourceError("ASHE sheet layout changed")
    out = {}
    for r in rows[12:]:
        y = r[1]
        if isinstance(y, str) and re.fullmatch(r"\d{4}inc", y):
            y = int(y[:4])
        if not isinstance(y, int) or not 1960 < y < 2100:
            continue
        v = {k: r[c] for k, c in COLS.items() if isinstance(r[c], (int, float))}
        if "median" in v:
            out[str(y)] = v
    return out


def build():
    import openpyxl
    html = fetch.http_get(PAGE).decode("utf8", "ignore")
    m = re.search(r'href="([^"]+\.xlsx)"', html)
    if not m:
        raise fetch.SourceError("ASHE xlsx link not found")
    url = "https://www.ons.gov.uk" + m.group(1)
    wb = openpyxl.load_workbook(io.BytesIO(fetch.http_get(url, timeout=120)), read_only=True, data_only=True)
    uk, gb = _table(wb["UK Median Time-series"]), _table(wb["GB Median Time-series"])
    if len(uk) < 25 or "1990" not in gb:
        raise fetch.SourceError("ASHE coverage too small")
    base = dict(group="earnings", unit="GBP/week", publisher="Office for National Statistics",
                source_url=PAGE, api_url=url, adjustment="Original, cash terms",
                source_release="ASHE time series", next_release="Annual, normally October/November",
                warnings=[], partial={}, last_updated=date.today().isoformat())
    a = dict(base, id="earnings_median_ft", label="Median gross weekly earnings, full-time adults, UK (ASHE)",
             geography="United Kingdom", source_id="UK Median Time-series, Male & Female Adult 50th percentile",
             methodology="Annual Survey of Hours and Earnings, adults on adult rates whose pay was not affected by absence. "
                         "Years shown as 2004inc/2006inc are used (the series comparable with later years).",
             limitations="Full-time employees only (excludes part-time and self-employed). Survey changes from 2023 mean 2022-23 comparisons need caution; latest year is provisional.",
             coverage=[min(uk), max(uk)], values={y: d["median"] for y, d in uk.items()},
             percentiles={y: {k: v for k, v in d.items() if k != "median"} for y, d in uk.items()})
    gb = {y: d for y, d in gb.items() if int(y) <= 1996 and int(y) >= 1990}
    b = dict(base, id="earnings_median_ft_nes", label="Median gross weekly earnings, full-time adults, GB (New Earnings Survey, 1990-96)",
             geography="Great Britain", source_id="GB Median Time-series, Male & Female Adult 50th percentile",
             methodology="New Earnings Survey, the predecessor of ASHE. Great Britain, not UK.",
             limitations="Different survey and geography from ASHE (1997 onward): do not treat as one continuous series without noting the break.",
             coverage=[min(gb), max(gb)], values={y: d["median"] for y, d in gb.items()}, percentiles={})
    return [a, b]
