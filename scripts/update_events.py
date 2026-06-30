"""
Kristiansand Eventguide - daglig oppdatering

Første versjon er bevisst enkel og robust:
- Leser sources.json
- Beholder manuelle/seedede eventer hvis live parsing feiler
- Skriver events.json i et stabilt format

Neste steg er å legge inn egne parser-funksjoner per kilde. Unngå scraping
av lukkede sosiale medier og respekter robots.txt/vilkår.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "sources.json"
EVENTS_FILE = ROOT / "events.json"

HEADERS = {"User-Agent": "KristiansandEventguideBot/0.1 (+personal local event guide)"}


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def generic_extract_titles(source: dict) -> list[dict]:
    """Very conservative fallback parser.
    It finds likely event links, but does not pretend to know dates if no date is structured.
    """
    url = source.get("url", "")
    if not url.startswith("http") or any(x in url for x in ["facebook.com", "instagram.com", "x.com", "snapchat.com", "google.com"]):
        return []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code >= 400:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        events = []
        for a in soup.find_all("a", href=True):
            text = clean(a.get_text(" "))
            href = a["href"]
            if len(text) < 8 or len(text) > 120:
                continue
            hay = text.lower()
            if not any(k in hay for k in ["konsert", "festival", "barn", "show", "stand", "teater", "verksted", "live", "arrangement", "event"]):
                continue
            link = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
            events.append({
                "id": f"{urlparse(url).netloc}-{abs(hash(link))}",
                "title": text,
                "date": "",
                "time": "",
                "venue": source["name"],
                "area": "Kristiansand",
                "category": classify(text, source),
                "family": "barn" in hay or source.get("type") == "family",
                "price": "",
                "description": "Automatisk funnet mulig arrangement. Dato må verifiseres i kilden.",
                "url": link,
                "source": source["name"],
            })
        return dedupe(events)[:20]
    except Exception:
        return []


def classify(text: str, source: dict) -> list[str]:
    hay = (text + " " + source.get("type", "") + " " + source.get("name", "")).lower()
    cats = []
    rules = {
        "family": ["barn", "familie", "vitensenter", "dyreparken"],
        "concert": ["konsert", "live", "band", "dj"],
        "festival": ["festival", "palmesus", "måkeskrik", "ravnedalen live"],
        "food": ["mat", "street food", "vinsmaking", "marked"],
        "outdoor": ["odderøya", "ravnedalen", "baneheia", "utendørs"],
        "show": ["show", "stand", "teater", "forestilling", "komedie"],
    }
    for cat, words in rules.items():
        if any(w in hay for w in words):
            cats.append(cat)
    return cats or ["culture"]


def dedupe(events: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for e in events:
        key = (clean(e.get("title", "")).lower(), e.get("date", ""), clean(e.get("venue", "")).lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def seed_events() -> list[dict]:
    # Replace or extend with hand-curated events if needed.
    return [{
        "id": "guide-status",
        "title": "Guiden er aktiv – sjekk kildelisten for manuelle sosiale medier",
        "date": date.today().isoformat(),
        "time": "",
        "venue": "Kristiansand",
        "area": "Kristiansand",
        "category": ["system"],
        "family": False,
        "price": "",
        "description": "Automatisk oppdatering kjørte. Sosiale medier og kilder uten stabil kalender bør sjekkes via kildelenkene.",
        "url": "",
        "source": "GitHub Actions",
    }]


def main() -> None:
    sources = load_json(SOURCES_FILE, [])
    events = seed_events()
    for source in sources:
        if source.get("priority", 9) <= 2:
            events.extend(generic_extract_titles(source))
    events = dedupe(events)
    payload = sorted(events, key=lambda e: (e.get("date") or "9999-99-99", e.get("title", "")))
    EVENTS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} events to {EVENTS_FILE}")


if __name__ == "__main__":
    main()
