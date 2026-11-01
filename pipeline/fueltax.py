"""Fuel duty (official dated rate history) and VAT rates (curated, labelled) -> annual series.

Fuel duty: HMRC 'Historical hydrocarbon oils duty rates' (GOV.UK, Hydrocarbon Oils Bulletin). Every dated change is
read from the page; each calendar year gets the DAY-WEIGHTED average rate (pence per litre) of the main pump grade:
petrol = ultra low sulphur petrol where listed, else unleaded petrol; diesel = ultra low sulphur diesel where listed, else diesel.
Rates already scheduled in the table for later in the current year are included as scheduled.

VAT: curated table below (effective dates and rates), NOT scraped. Sources: VAT Act 1994 s.2 on legislation.gov.uk (checked for
2000, 2010 and 2012), plus the secondary compilation on Wikipedia 'Value-added tax in the United Kingdom' which cites BBC/HMRC.
The exact day of the April 1994 domestic-fuel VAT start is not given by that source, so 1 April 1994 is an assumption.
"""
import html
import json
import re
from datetime import date, datetime

from . import fetch

PAGE = "/government/statistics/hydrocarbon-oils-bulletin/historical-hydrocarbon-oils-duty-rates--2"

# (effective date, percent). Standard rate and domestic fuel & power rate.
VAT_STANDARD = [("1979-06-18", 15.0), ("1991-04-01", 17.5), ("2008-12-01", 15.0), ("2010-01-01", 17.5), ("2011-01-04", 20.0)]
VAT_DOMESTIC_FUEL = [("1979-06-18", 0.0), ("1994-04-01", 8.0), ("1997-09-01", 5.0)]
VAT_SOURCE = ("https://www.legislation.gov.uk/ukpga/1994/23/section/2 ; "
              "https://en.wikipedia.org/wiki/Value-added_tax_in_the_United_Kingdom (secondary, cites BBC and HMRC)")


def _parse_date(s):
    return datetime.strptime(re.sub(r"\s+", " ", s.strip()), "%d %B %Y").date()


def _weighted(changes, y0=1990, y1=None):
    """changes: sorted [(date, rate)]. Day-weighted mean for each calendar year."""
    y1 = y1 or date.today().year
    out = {}
    for y in range(y0, y1 + 1):
        start, end = date(y, 1, 1), date(y + 1, 1, 1)
        tot = 0.0
        for i, (d, r) in enumerate(changes):
            nxt = changes[i + 1][0] if i + 1 < len(changes) else date(2200, 1, 1)
            lo, hi = max(d, start), min(nxt, end)
            if hi > lo:
                tot += r * (hi - lo).days
        out[str(y)] = round(tot / (end - start).days, 4)
    return out


def duty_changes():
    j = json.loads(fetch.http_get("https://www.gov.uk/api/content" + PAGE))
    petrol, diesel = {}, {}
    for t in re.findall(r"<table.*?</table>", j["details"]["body"], re.S):
        rows = [[html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[hd].*?</t[hd]>", r, re.S)]
                for r in re.findall(r"<tr.*?</tr>", t, re.S)]
        head = [re.sub(r"\s+", " ", h).lower() for h in rows[0]]

        def col(*names):
            for n in names:
                if n in head:
                    return head.index(n)
        up, ulsp, dsl, ulsd = col("unleaded petrol"), col("ultra low sulphur petrol"), col("diesel"), col("ultra low sulphur diesel")
        if up is None or dsl is None:
            continue
        for r in rows[1:]:
            try:
                d = _parse_date(r[0])
            except ValueError:
                continue

            def num(i):
                try:
                    return float(r[i]) if i is not None else None
                except ValueError:
                    return None
            p = num(ulsp) if num(ulsp) is not None else num(up)
            g = num(ulsd) if num(ulsd) is not None else num(dsl)
            if p is not None:
                petrol[d] = p
            if g is not None:
                diesel[d] = g
    return sorted(petrol.items()), sorted(diesel.items())


def build():
    petrol, diesel = duty_changes()
    if len(petrol) < 25 or petrol[0][0].year > 1990 or petrol[-1][0].year < 2022:
        raise fetch.SourceError("fuel duty history incomplete; refusing to store")
    page = "https://www.gov.uk" + PAGE
    base = dict(group="tax", publisher="HMRC – Hydrocarbon Oils Bulletin, historical duty rates", source_url=page, api_url="https://www.gov.uk/api/content" + PAGE,
                geography="United Kingdom", adjustment="Cash terms", source_release="Historical hydrocarbon oils duty rates", next_release="With each Budget change",
                warnings=[], partial={}, last_updated=date.today().isoformat(),
                methodology="Day-weighted average over the calendar year of the dated duty rates in force, main pump grade. Rates already legislated for later in the current year are included as scheduled.",
                limitations="Duty only (VAT is separate). Petrol means ultra low sulphur petrol where listed, otherwise unleaded; before 1999 most petrol sold was leaded, which carried a higher duty, so the unleaded rate understates duty paid then.")
    out = []
    for sid, label, ch in (("fuel_duty_petrol", "Fuel duty on petrol (pence per litre)", petrol), ("fuel_duty_diesel", "Fuel duty on diesel (pence per litre)", diesel)):
        v = _weighted(ch)
        out.append(dict(base, id=sid, label=label, unit="pence/litre", values=v, coverage=[min(v), max(v)], source_id=sid))
    vs, vf = _weighted([(date.fromisoformat(d), r) for d, r in VAT_STANDARD]), _weighted([(date.fromisoformat(d), r) for d, r in VAT_DOMESTIC_FUEL])
    vbase = dict(group="tax", publisher="Curated from legislation.gov.uk (VAT Act 1994) and a secondary compilation citing HMRC/BBC", source_url="https://www.legislation.gov.uk/ukpga/1994/23/section/2",
                 api_url="", geography="United Kingdom", adjustment="Statutory rate, day-weighted over the calendar year", source_release="curated table in pipeline/fueltax.py",
                 next_release="Manual: update when the rate changes", warnings=[], partial={}, last_updated=date.today().isoformat(), unit="%", source_id=VAT_SOURCE,
                 limitations="Hand-curated, not downloaded automatically. Zero-rated and reduced-rate goods other than domestic fuel and power are not modelled. Exact start day of the April 1994 domestic-fuel VAT is assumed to be 1 April.")
    out.append(dict(vbase, id="vat_standard_rate", label="VAT standard rate (%)", values=vs, coverage=[min(vs), max(vs)],
                    methodology="Effective dates: " + "; ".join(f"{d} {r}%" for d, r in VAT_STANDARD) + "."))
    out.append(dict(vbase, id="vat_domestic_fuel_rate", label="VAT on domestic gas and electricity (%)", values=vf, coverage=[min(vf), max(vf)],
                    methodology="Effective dates: " + "; ".join(f"{d} {r}%" for d, r in VAT_DOMESTIC_FUEL) + "."))
    return out
