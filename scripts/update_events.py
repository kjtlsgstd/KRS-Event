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
import hashlib
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "sources.json"
EVENTS_FILE = ROOT / "events.json"

HEADERS = {"User-Agent": "KristiansandEventguideBot/0.1 (+personal local event guide)"}
MIN_SAFE_EVENT_COUNT = 2

SEEDED_EVENTS = [
    {
        "id": "seed-kultur-i-kveld",
        "title": "Kultur i kveld: arrangementer i Kristiansand",
        "date": "2026-07-01",
        "time": "",
        "venue": "Kultur i kveld",
        "area": "Kristiansand",
        "category": ["culture"],
        "family": False,
        "price": "",
        "description": "Seedet kildeoppføring for lokale kulturarrangementer. Åpne kilden for oppdatert program og datoer.",
        "url": "https://kulturikveld.no/arrangementer/kristiansand",
        "source": "seed",
    },
    {
        "id": "seed-visit-sorlandet",
        "title": "Visit Sørlandet: hva skjer i regionen",
        "date": "2026-07-02",
        "time": "",
        "venue": "Visit Sørlandet",
        "area": "Kristiansand",
        "category": ["culture", "family", "outdoor"],
        "family": True,
        "price": "",
        "description": "Seedet oppføring for familieaktiviteter, konserter, festivaler og byliv i Kristiansand-regionen.",
        "url": "https://www.visitsorlandet.com/hva-skjer/",
        "source": "seed",
    },
    {
        "id": "seed-kvadraturen",
        "title": "Kvadraturen: byliv, marked og sentrumsarrangementer",
        "date": "2026-07-03",
        "time": "",
        "venue": "Kvadraturen",
        "area": "Sentrum",
        "category": ["food", "outdoor", "culture"],
        "family": True,
        "price": "",
        "description": "Seedet oppføring for aktiviteter i sentrum. Sjekk kilden for nøyaktige arrangementer og tider.",
        "url": "https://kvadraturen.no/kalender-hva-skjer-i-kristiansand/",
        "source": "seed",
    },
    {
        "id": "seed-kilden",
        "title": "Kilden: konserter, teater og forestillinger",
        "date": "2026-07-04",
        "time": "",
        "venue": "Kilden",
        "area": "Odderøya",
        "category": ["concert", "show", "family"],
        "family": True,
        "price": "",
        "description": "Seedet oppføring for Kildens program. Åpne kilden for billetter, klokkeslett og sal.",
        "url": "https://kilden.com/program/",
        "source": "seed",
    },
    {
        "id": "seed-kunstsilo",
        "title": "Kunstsilo: utstillinger, samtaler og verksteder",
        "date": "2026-07-05",
        "time": "",
        "venue": "Kunstsilo",
        "area": "Odderøya",
        "category": ["culture", "family"],
        "family": True,
        "price": "",
        "description": "Seedet oppføring for Kunstsilos arrangementer, inkludert familieverksteder og samtaler.",
        "url": "https://www.kunstsilo.no/arrangementer/",
        "source": "seed",
    },
    {
        "id": "seed-vitensenteret",
        "title": "Vitensenteret Sørlandet: aktiviteter for barn og familie",
        "date": "2026-07-06",
        "time": "",
        "venue": "Vitensenteret Sørlandet",
        "area": "Kristiansand",
        "category": ["family"],
        "family": True,
        "price": "",
        "description": "Seedet oppføring for familieprogram, drop-in og ferieaktiviteter.",
        "url": "https://vitensor.no/",
        "source": "seed",
    },
    {
        "id": "seed-vaktbua",
        "title": "Vaktbua: konserter og klubbkvelder",
        "date": "2026-07-07",
        "time": "",
        "venue": "Vaktbua",
        "area": "Odderøya",
        "category": ["concert"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for konserter og klubbarrangementer på Vaktbua.",
        "url": "https://www.vaktbua.no/events",
        "source": "seed",
    },
    {
        "id": "seed-krs-live",
        "title": "KRS LIVE: konsertprogram",
        "date": "2026-07-08",
        "time": "",
        "venue": "KRS LIVE",
        "area": "Kristiansand",
        "category": ["concert"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for større konserter og livescener.",
        "url": "https://www.krslive.no/",
        "source": "seed",
    },
    {
        "id": "seed-teateret",
        "title": "Teateret: standup, show og konserter",
        "date": "2026-07-09",
        "time": "",
        "venue": "Teateret",
        "area": "Sentrum",
        "category": ["show", "concert"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for sceneprogram, standup og byliv på Teateret.",
        "url": "https://teateret.no/",
        "source": "seed",
    },
    {
        "id": "seed-ravnedalen-live",
        "title": "Ravnedalen Live: sommerkonserter",
        "date": "2026-07-10",
        "time": "",
        "venue": "Ravnedalen Live",
        "area": "Ravnedalen",
        "category": ["concert", "festival", "outdoor"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for festival- og konsertprogram i Ravnedalen.",
        "url": "https://ravnedalenlive.no/",
        "source": "seed",
    },
    {
        "id": "seed-maakeskrik",
        "title": "Måkeskrik: festivalprogram",
        "date": "2026-07-11",
        "time": "",
        "venue": "Måkeskrik",
        "area": "Bendiksbukta",
        "category": ["festival", "concert", "outdoor"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for Måkeskrik-programmet.",
        "url": "https://www.maakeskrik.no/",
        "source": "seed",
    },
    {
        "id": "seed-palmesus",
        "title": "Palmesus: strandfestival",
        "date": "2026-07-12",
        "time": "",
        "venue": "Palmesus",
        "area": "Bystranda",
        "category": ["festival", "concert", "outdoor"],
        "family": False,
        "price": "",
        "description": "Seedet oppføring for Palmesus og relaterte festivalarrangementer.",
        "url": "https://www.palmesus.com/",
        "source": "seed",
    },
]


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def generic_extract_titles(source: dict) -> list[dict]:
    """Very conservative fallback parser.
    It finds likely event links, but does not pretend to know dates if no date is structured.
    """
    if requests is None or BeautifulSoup is None:
        return []

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
            event_id = hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]
            events.append({
                "id": f"{urlparse(url).netloc}-{event_id}",
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
    current = load_json(EVENTS_FILE, [])
    if isinstance(current, list):
        usable = [
            normalize_event(e)
            for e in current
            if isinstance(e, dict) and e.get("id") not in {"sample-001", "guide-status"}
        ]
        if len(usable) >= MIN_SAFE_EVENT_COUNT:
            return usable
    return [normalize_event(e) for e in SEEDED_EVENTS]


def normalize_event(event: dict) -> dict:
    normalized = {
        "id": clean(str(event.get("id") or "")),
        "title": clean(str(event.get("title") or "Uten tittel")),
        "date": clean(str(event.get("date") or "")),
        "time": clean(str(event.get("time") or "")),
        "venue": clean(str(event.get("venue") or "")),
        "area": clean(str(event.get("area") or "")),
        "category": event.get("category") if isinstance(event.get("category"), list) else [],
        "family": bool(event.get("family")),
        "price": clean(str(event.get("price") or "")),
        "description": clean(str(event.get("description") or "")),
        "url": clean(str(event.get("url") or "")),
        "source": clean(str(event.get("source") or "")),
    }
    if not normalized["id"]:
        raw = "|".join([normalized["title"], normalized["date"], normalized["venue"], normalized["url"]])
        normalized["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    normalized["category"] = [clean(str(c)) for c in normalized["category"] if clean(str(c))]
    return normalized


def main() -> None:
    sources = load_json(SOURCES_FILE, [])
    seeded = seed_events()
    scraped = []
    for source in sources if isinstance(sources, list) else []:
        if source.get("scrape", True) and source.get("priority", 9) <= 2:
            scraped.extend(generic_extract_titles(source))

    events = dedupe(seeded + scraped)
    if len(events) < MIN_SAFE_EVENT_COUNT:
        events = seeded

    payload = sorted(
        [normalize_event(e) for e in events],
        key=lambda e: (e.get("date") or "9999-99-99", e.get("title", "")),
    )
    if len(payload) < MIN_SAFE_EVENT_COUNT:
        raise RuntimeError("Refusing to overwrite events.json with fewer than two events")

    EVENTS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} events to {EVENTS_FILE}")


if __name__ == "__main__":
    main()
