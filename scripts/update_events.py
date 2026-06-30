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
from html import unescape
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

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
LOCAL_TZ = ZoneInfo("Europe/Oslo")

SEEDED_EVENTS = [
    {
        "id": "seed-kultur-i-kveld",
        "title": "Kultur i kveld: arrangementer i Kristiansand",
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
        "date": "",
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
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", unescape(text)).strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(clean(str(part)) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def fetch_html(url: str) -> str:
    if requests is not None:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        return r.text

    current_url = url
    for _ in range(4):
        req = Request(current_url, headers=HEADERS)
        try:
            with urlopen(req, timeout=20) as response:
                return response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise
            location = exc.headers.get("Location")
            if not location:
                raise
            current_url = urljoin(current_url, location)
    raise RuntimeError(f"Too many redirects for {url}")


def as_list(value) -> list:
    if isinstance(value, dict) and not value.get("@type"):
        return list(value.values())
    return value if isinstance(value, list) else [value]


def type_names(item: dict) -> list[str]:
    return [clean(str(value)) for value in as_list(item.get("@type")) if clean(str(value))]


def is_event_type(item: dict) -> bool:
    return any(type_name == "Event" or type_name.endswith("Event") for type_name in type_names(item))


def parse_start(value: str) -> tuple[str, str]:
    value = clean(value)
    if not value:
        return "", ""

    try:
        if "T" not in value:
            return datetime.fromisoformat(value).date().isoformat(), ""

        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(LOCAL_TZ)
        return dt.date().isoformat(), dt.strftime("%H:%M")
    except ValueError:
        return "", ""


def event_from_schema(item: dict, source: dict) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    if not is_event_type(item):
        return None

    title = clean(item.get("name", ""))
    date_value, time_value = parse_start(item.get("startDate", ""))
    offers = item.get("offers") if isinstance(item.get("offers"), (dict, list)) else []
    offer_urls = [clean(offer.get("url", "")) for offer in as_list(offers) if isinstance(offer, dict)]
    url = clean(item.get("url", "")) or next((offer_url for offer_url in offer_urls if offer_url), "")
    if not title or not date_value or not url:
        return None

    location = item.get("location") if isinstance(item.get("location"), dict) else {}
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    venue = clean(location.get("name") or source.get("name", ""))
    area = clean(address.get("addressLocality") or "")
    description = clean(item.get("description", ""))
    blob = " ".join([title, venue, area, description, url]).lower()
    broad_source = source.get("category") in {"ticketing", "local_media"} or source.get("type") in {"ticketing", "concerts"}
    if broad_source and not any(term in blob for term in ["kristiansand", "posebyhaven", "kilden", "ravnedalen", "bystranda", "teateret", "odderøya", "odderoya", "vaktbua"]):
        return None

    return normalize_event({
        "id": f"{urlparse(url).netloc}-{stable_id(title, date_value, venue, url)}",
        "title": title,
        "date": date_value,
        "time": time_value,
        "venue": venue,
        "area": area or "Kristiansand",
        "category": classify(f"{title} {description}", source),
        "family": "barn" in f"{title} {description}".lower() or source.get("type") == "family",
        "price": "",
        "description": description,
        "url": url,
        "source": source["name"],
    })


def parse_schema_events(source: dict) -> list[dict]:
    html = fetch_html(source["url"])
    events = []
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    )
    for script in scripts:
        try:
            payload = json.loads(script.strip())
        except json.JSONDecodeError:
            continue

        queue = as_list(payload)
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue

            event = event_from_schema(item, source)
            if event:
                events.append(event)

            for key in ("itemListElement", "@graph"):
                if key in item:
                    queue.extend(as_list(item[key]))
            if item.get("@type") == "ListItem" and "item" in item:
                queue.extend(as_list(item["item"]))

    today = date.today().isoformat()
    return dedupe([event for event in events if event.get("date", "") >= today])


def parse_kultur_i_kveld(source: dict) -> list[dict]:
    events = parse_schema_events(source)
    for event in events:
        if not url_is_available(event["url"]):
            event["description"] = clean(f'{event["description"]} Direkte eventlenke fra kilden svarte 404, så lenken går til kildeoversikten.')
            event["url"] = source["url"]
    return events


def url_is_available(url: str) -> bool:
    if not url.startswith("http"):
        return False
    try:
        if requests is not None:
            response = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
            return response.status_code < 400

        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=12) as response:
            return response.status < 400
    except Exception:
        return False


def parse_structured_source(source: dict) -> list[dict]:
    return parse_schema_events(source)


def parse_kvadraturen(source: dict) -> list[dict]:
    api_url = "https://kvadraturen.no/umbraco/api/kalender/getCalendarOnDate"
    payload = json.loads(fetch_html(api_url))
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    calendar = payload[1] if isinstance(payload[1], dict) else {}
    rows = calendar.get("hendelser", [])
    events = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue

        title = clean(row.get("navn", ""))
        date_value, time_value = parse_start(row.get("startDateTime", ""))
        time_value = clean(row.get("startTid", ""))
        venue = clean(row.get("hendelsessted", ""))
        url = clean(row.get("nettsideUri", "")) or urljoin(source["url"], f"/kalender/hendelse?id={row.get('id', '')}")
        if not title or not date_value or not url:
            continue

        description = clean(row.get("beskrivelse", ""))
        events.append(normalize_event({
            "id": f"kvadraturen.no-{stable_id(title, date_value, venue, url)}",
            "title": title,
            "date": date_value,
            "time": time_value,
            "venue": venue or "Kvadraturen",
            "area": clean(row.get("by", "")) or "Kristiansand",
            "category": classify(f"{title} {description} {row.get('eventType', '')}", source),
            "family": "barn" in f"{title} {description}".lower() or source.get("type") == "family",
            "price": "",
            "description": description,
            "url": url,
            "source": source["name"],
        }))

    today = date.today().isoformat()
    return dedupe([event for event in events if event.get("date", "") >= today])


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
            link = urljoin(url, href)
            event_id = stable_id(link)
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


def is_seed_event(event: dict) -> bool:
    return clean(str(event.get("id", ""))).startswith("seed-") or clean(str(event.get("source", ""))) == "seed"


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
    if normalized["id"].startswith("seed-") or normalized["source"] == "seed":
        normalized["date"] = ""
        normalized["time"] = ""
    return normalized


def main() -> None:
    sources = load_json(SOURCES_FILE, [])
    seeded = seed_events()
    scraped = []
    parsers = {
        source.get("name", ""): parse_structured_source
        for source in sources
        if isinstance(source, dict) and source.get("scrape", True)
    }
    parsers["Kultur i kveld - Kristiansand"] = parse_kultur_i_kveld
    parsers["Kultur i kveld – Kristiansand"] = parse_kultur_i_kveld
    parsers["Kvadraturen - Hva skjer i Kristiansand"] = parse_kvadraturen
    for source in sources if isinstance(sources, list) else []:
        if not source.get("scrape", True) or source.get("priority", 9) > 2:
            continue
        parser = parsers.get(source.get("name", ""))
        try:
            if parser:
                scraped.extend(parser(source))
            elif source.get("generic_scrape", False):
                scraped.extend(generic_extract_titles(source))
        except Exception as exc:
            print(f"Skipping {source.get('name', 'unknown source')}: {exc}")

    dated_scraped = [e for e in scraped if e.get("date")]
    events = dated_scraped if len(dated_scraped) >= MIN_SAFE_EVENT_COUNT else seeded
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
