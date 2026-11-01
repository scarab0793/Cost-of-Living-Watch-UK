"""DESNZ Quarterly Energy Prices: annual domestic electricity and gas bills (cash terms, £/year).

Source: https://www.gov.uk/government/statistical-data-sets/annual-domestic-energy-price-statistics
Tables QEP 2.2.1 (electricity, UK, fixed 3,600 kWh/yr) and QEP 2.3.1 (gas, GB, fixed 13,600 kWh/yr).
Official statistics: bills are modelled for a fixed consumption level, not measured household spend.
Coverage starts 2010; earlier £ bills are not published in these tables.
"""
import io
import json
import re
from datetime import date

from . import fetch

PAGE = "annual-domestic-energy-price-statistics"
SPECS = [
    # id, table title key, long sheet (2010-2023), short sheet (to latest year), column, label, kwh
    ("energy_elec_direct_debit", "QEP 2.2.1", "2.2.1 (Historic)", "2.2.1 (3600kWh Historic)", 6,
     "Average annual electricity bill, direct debit, UK (£/year)", 3600, "electricity"),
    ("energy_elec_standard_credit", "QEP 2.2.1", "2.2.1 (Historic)", "2.2.1 (3600kWh Historic)", 3,
     "Average annual electricity bill, standard credit, UK (£/year)", 3600, "electricity"),
    ("energy_gas_direct_debit", "QEP 2.3.1", "2.3.1 (Historic)", "2.3.1 (13600kWh Historic)", 6,
     "Average annual gas bill, direct debit, GB (£/year)", 13600, "gas"),
    ("energy_gas_standard_credit", "QEP 2.3.1", "2.3.1 (Historic)", "2.3.1 (13600kWh Historic)", 3,
     "Average annual gas bill, standard credit, GB (£/year)", 13600, "gas"),
]


def _attachments():
    meta = json.loads(fetch.http_get(f"https://www.gov.uk/api/content/government/statistical-data-sets/{PAGE}"))
    return meta["details"].get("attachments", []), meta.get("public_updated_at", "")


def _year_values(wb, sheet, col):
    ws = wb[sheet]
    rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    hdr = next(i for i, r in enumerate(rows) if r[0] == "Year")
    out = {}
    for r in rows[hdr + 1:]:
        m = re.match(r"\s*(\d{4})", str(r[0] or ""))
        if m and len(r) > col and isinstance(r[col], (int, float)):
            out[m.group(1)] = round(float(r[col]), 2)
    return out


def build():
    import openpyxl  # required for this job
    atts, updated = _attachments()
    books = {}
    series = []
    for sid, key, long_sheet, short_sheet, col, label, kwh, fuel in SPECS:
        if key not in books:
            att = next((a for a in atts if key in (a.get("title") or "")), None)
            if not att:
                raise fetch.SourceError(f"DESNZ attachment {key} not found")
            books[key] = (att["url"], openpyxl.load_workbook(io.BytesIO(fetch.http_get(att["url"], timeout=120)),
                                                             read_only=True, data_only=True))
        url, wb = books[key]
        values = _year_values(wb, long_sheet, col)
        for y, v in _year_values(wb, short_sheet, col).items():  # newer years on the same consumption basis
            values.setdefault(y, v)
        if len(values) < 10:
            raise fetch.SourceError(f"{sid}: only {len(values)} years parsed")
        series.append({
            "id": sid, "group": "energy", "label": label, "publisher": "Department for Energy Security and Net Zero",
            "source_url": f"https://www.gov.uk/government/statistical-data-sets/{PAGE}", "api_url": url,
            "source_title": f"{key} {sheet_title(long_sheet)}", "source_id": key, "unit": "GBP/year",
            "geography": "UK" if fuel == "electricity" else "Great Britain",
            "adjustment": "Cash (nominal) terms, VAT inclusive",
            "methodology": f"Bill for a fixed annual consumption of {kwh:,} kWh. Not actual household spend.",
            "limitations": ("Starts 2010; £ bills before 2010 are not published in these tables. Consumption basis "
                            "changes in DESNZ's newer tables (from 2025) and is not mixed in. "
                            "Includes Energy Price Guarantee from Oct 2022, excludes Energy Bills Support Scheme £200."),
            "coverage": [min(values), max(values)], "source_release": updated[:10], "next_release": "",
            "warnings": [], "values": dict(sorted(values.items())), "partial": {},
            "last_updated": date.today().isoformat(),
        })
    return series


def sheet_title(s):
    return s
