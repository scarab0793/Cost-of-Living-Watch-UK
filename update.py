#!/usr/bin/env python3
"""Refresh UK cost-of-living datasets from official sources.

No AI, no estimates, no interpolation. Principles:
  * every series is checked against the title the publisher returns (wrong series are rejected)
  * a failed or implausible download never overwrites the last good data
  * only genuinely new/revised observations change files (clean diffs, quiet Git history)
  * all outcomes are recorded in data/status.json and data/changes.json

Usage:  python update.py [--only ID,ID] [--static]   (--static also refreshes one-off archives)
Exit code is 0 unless the pipeline itself is broken; individual source failures are logged, not fatal,
because the previous good data is preserved.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from pipeline import fetch  # noqa: E402
from pipeline.catalogue import CATALOGUE  # noqa: E402

DATA = ROOT / "data"
SERIES_DIR = DATA / "series"
CURATED_DIR = DATA / "curated"
THIS_YEAR = date.today().year
MAX_DROP = 2  # a refresh may lose at most this many observations before it is rejected


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def run_fetch(spec):
    k = spec["kind"]
    if k == "ons":
        return fetch.ons_timeseries(spec["cdid"], spec["dataset"])
    if k == "boe":
        return fetch.boe_iadb(spec["code"])
    if k == "hpi":
        return fetch.landregistry_hpi(spec["region"])
    if k == "worldbank":
        return fetch.worldbank(spec["code"])
    raise ValueError(f"unknown kind {k}")


def validate(spec, result):
    """Return (clean_annual, clean_partial, warnings). Raise fetch.SourceError to reject."""
    title = result["meta"].get("Title", "")
    if not re.search(spec["expect"], title, re.I):
        raise fetch.SourceError(f"title mismatch: expected /{spec['expect']}/ got '{title}'")
    scale = spec["scale"]
    annual = {y: round(v * scale, 6) for y, v in result["annual"].items()
              if y.isdigit() and 1990 <= int(y) <= THIS_YEAR + 1}
    partial = {y: {**p, "mean": round(p["mean"] * scale, 6)} for y, p in result["partial"].items()
               if y.isdigit() and 1990 <= int(y) <= THIS_YEAR + 1}
    if len(annual) < spec["min_obs"]:
        raise fetch.SourceError(f"only {len(annual)} annual observations (need {spec['min_obs']})")
    warnings = []
    ys = sorted(annual, key=int)
    for a, b in zip(ys, ys[1:]):
        if annual[a] > 0 and annual[b] / annual[a] > 8:
            warnings.append(f"large jump {a}->{b}: {annual[a]} -> {annual[b]} (kept, flagged)")
    return annual, partial, warnings


def diff(old, new):
    changed = {y: (old[y], new[y]) for y in new if y in old and abs(old[y] - new[y]) > 1e-9 * max(1, abs(old[y]))}
    added = [y for y in new if y not in old]
    removed = [y for y in old if y not in new]
    return changed, added, removed


def refresh(only=None):
    status, changes = {}, []
    for spec in CATALOGUE:
        if only and spec["id"] not in only:
            continue
        path = SERIES_DIR / f"{spec['id']}.json"
        old = read_json(path)
        try:
            result = run_fetch(spec)
            annual, partial, warnings = validate(spec, result)
            if old:
                changed, added, removed = diff(old["values"], annual)
                if len(removed) > MAX_DROP:
                    raise fetch.SourceError(f"refresh would drop {len(removed)} observations ({removed[:5]}...)")
            else:
                changed, added, removed = {}, list(annual), []
            record = {
                "id": spec["id"], "label": spec["label"], "group": spec["group"], "publisher": spec["publisher"],
                "source_url": result["meta"].get("source_url") or spec.get("source_url", ""),
                "api_url": result.get("api_url", ""), "source_title": result["meta"].get("Title", ""),
                "source_id": spec.get("cdid") or spec.get("code") or spec.get("region") or "",
                "unit": spec["unit"], "geography": spec["geography"], "adjustment": spec["adjusted"],
                "methodology": spec["method"], "limitations": spec["limitations"],
                "coverage": [min(annual, key=int), max(annual, key=int)],
                "source_release": result["meta"].get("Release date", ""),
                "next_release": result["meta"].get("Next release", ""),
                "warnings": warnings, "values": dict(sorted(annual.items(), key=lambda kv: int(kv[0]))),
                "partial": dict(sorted(partial.items())),
                "last_updated": old["last_updated"] if old else date.today().isoformat(),
            }
            if old and (changed or added or removed or old.get("partial") != record["partial"]):
                record["last_updated"] = date.today().isoformat()
            wrote = write_json(path, record)
            status[spec["id"]] = {"ok": True, "obs": len(annual), "coverage": record["coverage"], "warnings": warnings}
            if wrote and old and (changed or added or removed):
                changes.append({"id": spec["id"], "date": date.today().isoformat(), "added": added,
                                "revised": {y: {"from": a, "to": b} for y, (a, b) in changed.items()},
                                "removed": removed})
            print(f"OK   {spec['id']:34s} {len(annual):3d} obs {record['coverage']} {'(updated)' if wrote else ''}")
        except Exception as exc:  # keep last good data
            status[spec["id"]] = {"ok": False, "error": str(exc)[:300],
                                  "preserved_last_good": bool(old)}
            print(f"FAIL {spec['id']:34s} {exc}  -> {'kept previous data' if old else 'NO DATA YET'}")
    return status, changes


def build_bundle(status):
    """One file for the website: all series plus curated datasets plus honest gap list."""
    series = {}
    for p in sorted(SERIES_DIR.glob("*.json")):
        d = read_json(p)
        if d:
            series[d["id"]] = d
    curated = {}
    for p in sorted(CURATED_DIR.glob("*.json")):
        d = read_json(p)
        if d:
            curated[p.stem] = d
    gaps = read_json(DATA / "gaps.json", [])
    bundle = {"generated": date.today().isoformat(), "series": series, "curated": curated, "gaps": gaps}
    return write_json(DATA / "dataset.json", bundle)


def prior_status():
    return read_json(DATA / "status.json", {}) or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s}

    status, changes = refresh(only or None)
    if only:  # merge partial run into previous status
        merged = prior_status().get("series", {})
        merged.update(status)
        status = merged

    try:
        from pipeline import extras
        extras.run(DATA, static=args.static, news=not args.no_news)
    except ImportError:
        pass

    if changes:
        log = read_json(DATA / "changes.json", [])
        log = (changes + log)[:400]
        write_json(DATA / "changes.json", log)

    failures = [k for k, v in status.items() if not v.get("ok")]
    write_json(DATA / "status.json", {
        "checked": date.today().isoformat(),
        "series_ok": len(status) - len(failures), "series_failed": len(failures),
        "failed_ids": failures, "series": status,
    })
    build_bundle(status)
    print(f"\n{len(status)-len(failures)}/{len(status)} series ok; {len(failures)} failed (previous data preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
