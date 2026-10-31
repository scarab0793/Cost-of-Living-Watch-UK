#!/usr/bin/env python3
"""Fetch recent official GOV.UK news without AI or third-party packages."""
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

FEEDS = {
    "HM Treasury": "https://www.gov.uk/government/organisations/hm-treasury.atom",
    "HMRC": "https://www.gov.uk/government/organisations/hm-revenue-customs.atom",
    "Department for Energy Security and Net Zero": "https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero.atom",
}
items = []
for source, url in FEEDS.items():
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "UKLivingCostIndex/1.0 (public data dashboard)"})
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns)[:20]:
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            date = entry.findtext("a:updated", default="", namespaces=ns)
            link = next((x.get("href") for x in entry.findall("a:link", ns) if x.get("rel", "alternate") == "alternate"), "")
            if title and link and link.startswith("https://www.gov.uk/"):
                items.append({"title": title, "date": date, "url": link, "source": source})
    except Exception as exc:
        print(f"Feed error {source}: {exc}")
items = list({x["url"]: x for x in items}.values())
items.sort(key=lambda x: x["date"], reverse=True)
path = Path("data/stories.json")
if items:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[:45], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {len(items[:45])} verified official headlines at {datetime.now(timezone.utc).isoformat()}")
else:
    print("No feeds available; retaining last successful data.")
