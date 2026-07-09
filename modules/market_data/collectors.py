import html
import json
import time
import os
import re
from email.utils import parsedate_to_datetime
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import requests

USER_AGENT = "ClearNews/1.0 (+local)"


@dataclass
class CollectorResult:
    source: str
    items: List[Dict[str, object]]


class Collector:
    name = "base"

    def fetch(self) -> CollectorResult:
        raise NotImplementedError


class RSSCollector(Collector):
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url

    def fetch(self) -> CollectorResult:
        items: List[Dict[str, object]] = []
        try:
            resp = requests.get(self.url, timeout=8, headers={"User-Agent": USER_AGENT})
            if resp.status_code != 200:
                return CollectorResult(self.name, [])
            root = ElementTree.fromstring(resp.content)
        except Exception:
            return CollectorResult(self.name, [])

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            summary = _extract_item_summary(item)
            if not title:
                continue
            items.append({
                "title": title,
                "summary": summary,
                "url": link,
                "published": pub_date,
                "source": self.name,
            })
        return CollectorResult(self.name, items)


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _clean_text(value: str) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_item_summary(item: ElementTree.Element) -> str:
    candidates: List[str] = []
    for child in list(item):
        tag = str(child.tag or "").lower()
        text = _clean_text(child.text or "")
        if not text:
            continue
        if tag.endswith("description") or tag.endswith("summary") or tag.endswith("encoded"):
            candidates.append(text)
    if candidates:
        return max(candidates, key=len)
    return ""


def _normalize_match_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if not cleaned:
        return " "
    return f" {re.sub(r'\s+', ' ', cleaned)} "


def _normalize_match_term(term: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (term or "").lower()).strip())


def _match_terms(text_norm: str, keywords: Sequence[str]) -> List[str]:
    matches: List[str] = []
    for keyword in keywords:
        normalized = _normalize_match_term(keyword)
        if normalized and f" {normalized} " in text_norm:
            matches.append(keyword)
    return matches


def _extract_term_matches(
    text_norm: str,
    keyword_map: Dict[str, Sequence[str]],
) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    counts: Dict[str, int] = {}
    matched_terms: Dict[str, List[str]] = {}
    for key, keywords in keyword_map.items():
        matches = _match_terms(text_norm, keywords)
        if matches:
            counts[key] = len(matches)
            matched_terms[key] = sorted(dict.fromkeys(matches))
    return counts, matched_terms


def _parse_published_ts(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except Exception:
        return None
    if parsed is None:
        return None
    try:
        return int(parsed.timestamp())
    except Exception:
        return None


TRACKING_QUERY_PARAMS = {
    "cmpid",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ocid",
    "ref",
    "source",
    "taid",
}


def _normalize_summary(summary: str) -> str:
    return _normalize_title(_clean_text(summary or ""))


def _canonicalize_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
    except Exception:
        return raw.lower()
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+$", "", parsed.path or "")
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=False)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(filtered_query, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _coerce_sources(item: Dict[str, object]) -> List[str]:
    values: List[str] = []
    raw_sources = item.get("sources")
    if isinstance(raw_sources, list):
        values.extend(str(source).strip() for source in raw_sources if str(source).strip())
    primary = str(item.get("source") or "").strip()
    if primary:
        values.append(primary)
    return sorted(set(values), key=lambda entry: entry.lower())


def _secondary_dedupe_identity(item: Dict[str, object]) -> Tuple[str, ...]:
    title = _normalize_title(str(item.get("title", "")))
    summary = _normalize_summary(str(item.get("summary", "") or item.get("description", "") or ""))
    if summary:
        return ("content", title, summary)
    source_text = _normalize_summary(str(item.get("source_text", "") or ""))
    if source_text:
        return ("source_text", title, source_text)
    return ("title", title)


def _primary_dedupe_identity(item: Dict[str, object]) -> Tuple[str, ...]:
    canonical_url = _canonicalize_url(str(item.get("url") or ""))
    if canonical_url:
        return ("url", canonical_url)
    return _secondary_dedupe_identity(item)


def _dedupe_rank(item: Dict[str, object]) -> Tuple[int, int, int, int]:
    summary = _clean_text(str(item.get("summary", "") or item.get("description", "") or ""))
    source_text = _clean_text(str(item.get("source_text", "") or ""))
    published_ts = item.get("published_ts")
    try:
        published_value = int(published_ts or 0)
    except Exception:
        published_value = 0
    return (
        1 if _canonicalize_url(str(item.get("url") or "")) else 0,
        published_value,
        len(summary),
        len(source_text),
    )


def _pick_preferred_item(existing: Dict[str, object], incoming: Dict[str, object]) -> Dict[str, object]:
    if _dedupe_rank(incoming) > _dedupe_rank(existing):
        return incoming
    return existing


def _merge_article_provenance(existing: Dict[str, object], incoming: Dict[str, object]) -> Dict[str, object]:
    preferred = dict(_pick_preferred_item(existing, incoming))
    canonical_url = _canonicalize_url(str(preferred.get("url") or "")) or _canonicalize_url(
        str(existing.get("url") or incoming.get("url") or "")
    )
    if canonical_url:
        preferred["canonical_url"] = canonical_url
    sources = sorted(
        set(_coerce_sources(existing)).union(_coerce_sources(incoming)),
        key=lambda entry: entry.lower(),
    )
    if sources:
        preferred["sources"] = sources
        preferred["source"] = sources[0]
    return preferred


def _collapse_duplicates(
    items: List[Dict[str, object]],
    key_builder,
) -> List[Dict[str, object]]:
    deduped: Dict[Tuple[str, ...], Dict[str, object]] = {}
    for item in items:
        key = key_builder(item)
        existing = deduped.get(key)
        if existing is None:
            seed = dict(item)
            sources = _coerce_sources(seed)
            if sources:
                seed["sources"] = sources
                seed["source"] = sources[0]
            canonical_url = _canonicalize_url(str(seed.get("url") or ""))
            if canonical_url:
                seed["canonical_url"] = canonical_url
            deduped[key] = seed
            continue
        deduped[key] = _merge_article_provenance(existing, item)
    return list(deduped.values())


def _dedupe_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    primary_pass = _collapse_duplicates(items, _primary_dedupe_identity)
    return _collapse_duplicates(primary_pass, _secondary_dedupe_identity)


DEFAULT_SOURCES = [
    RSSCollector("CNBC Top", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    RSSCollector("CNBC World", "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
    RSSCollector("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    RSSCollector("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
]

HEALTH_FILE = "data/news_health.json"
FAIL_BACKOFF_SECONDS = 600
MAX_BACKOFF_SECONDS = 3600


def _load_health() -> Dict[str, Dict[str, object]]:
    if not os.path.exists(HEALTH_FILE):
        return {}
    try:
        with open(HEALTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_health(health: Dict[str, Dict[str, object]]) -> None:
    parent = os.path.dirname(HEALTH_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2)


def _should_skip(health: Dict[str, Dict[str, object]], name: str) -> bool:
    entry = health.get(name, {})
    backoff_until = int(entry.get("backoff_until", 0) or 0)
    return int(time.time()) < backoff_until


def _record_success(health: Dict[str, Dict[str, object]], name: str) -> None:
    health[name] = {
        "last_ok": int(time.time()),
        "fail_count": 0,
        "backoff_until": 0,
    }


def _record_failure(health: Dict[str, Dict[str, object]], name: str) -> None:
    entry = health.get(name, {})
    fails = int(entry.get("fail_count", 0) or 0) + 1
    backoff = min(FAIL_BACKOFF_SECONDS * fails, MAX_BACKOFF_SECONDS)
    health[name] = {
        "last_fail": int(time.time()),
        "fail_count": fails,
        "backoff_until": int(time.time()) + backoff,
    }


INDUSTRY_KEYWORDS: Dict[str, List[str]] = {
    "energy": ["oil", "gas", "lng", "opec", "power", "electric", "energy"],
    "agriculture": ["crop", "grain", "wheat", "corn", "soy", "harvest", "agriculture"],
    "shipping": ["shipping", "port", "container", "logistics", "freight", "supply chain"],
    "aviation": ["airline", "airport", "aviation", "flight", "airspace"],
    "defense": ["defense", "military", "weapon", "missile", "security"],
    "finance": ["bank", "rates", "inflation", "credit", "bond", "treasury"],
    "tech": ["semiconductor", "chip", "ai", "cloud", "telecom", "cyber"],
}

EVENT_TAG_KEYWORDS: Dict[str, List[str]] = {
    "conflict": [
        "war",
        "conflict",
        "attack",
        "attacks",
        "attacked",
        "missile",
        "missiles",
        "drone",
        "drones",
        "shelling",
        "bombing",
        "bombardment",
        "raid",
        "raids",
        "offensive",
        "incursion",
        "invasion",
        "troops",
        "military",
        "airstrike",
        "rocket",
        "rockets",
        "artillery",
        "hostage",
        "ceasefire",
        "blockade",
        "naval clash",
    ],
    "disruption": [
        "strike",
        "strikes",
        "walkout",
        "walkouts",
        "lockout",
        "lockouts",
        "protest",
        "protests",
        "shutdown",
        "closure",
        "closures",
        "closed",
        "halt",
        "halts",
        "stoppage",
        "disruption",
        "disrupted",
        "delay",
        "delays",
        "cancelled",
        "canceled",
        "reroute",
        "rerouting",
        "grounded",
        "airspace closure",
        "port closure",
    ],
    "scarcity": [
        "shortage",
        "shortages",
        "food shortage",
        "food shortages",
        "water shortage",
        "water shortages",
        "scarcity",
        "rationing",
        "rationed",
        "famine",
        "hunger",
        "food insecurity",
        "water stress",
        "drought",
        "droughts",
        "crop failure",
        "crop failures",
        "blackout",
        "blackouts",
        "outage",
        "outages",
    ],
    "disaster": [
        "wildfire",
        "wildfires",
        "fire",
        "fires",
        "earthquake",
        "earthquakes",
        "quake",
        "eruption",
        "eruptions",
        "landslide",
        "landslides",
        "flood",
        "flooding",
        "storm surge",
        "evacuation",
        "evacuations",
        "heatwave",
        "heat wave",
        "cold snap",
    ],
    "weather": [
        "storm",
        "storms",
        "hurricane",
        "hurricanes",
        "cyclone",
        "cyclones",
        "typhoon",
        "typhoons",
        "tornado",
        "tornadoes",
        "flood",
        "flooding",
        "blizzard",
        "snowstorm",
        "heavy rain",
        "rainfall",
        "heatwave",
        "heat wave",
        "drought",
        "smoke",
    ],
    "sanctions": [
        "sanction",
        "sanctions",
        "tariff",
        "tariffs",
        "embargo",
        "embargoes",
        "export control",
        "export controls",
        "restriction",
        "restrictions",
        "blacklist",
    ],
    "infrastructure": [
        "pipeline",
        "refinery",
        "grid",
        "power plant",
        "substation",
        "bridge",
        "port",
        "ports",
        "canal",
        "rail",
        "railway",
        "airport",
        "airspace",
        "telecom",
        "communications",
        "internet outage",
        "subsea cable",
        "factory",
        "terminal",
    ],
}

IMPACT_CHANNEL_KEYWORDS: Dict[str, List[str]] = {
    "energy": ["oil", "crude", "gas", "lng", "refinery", "pipeline", "power", "electricity", "grid", "fuel"],
    "shipping_logistics": [
        "shipping",
        "port",
        "ports",
        "freight",
        "logistics",
        "container",
        "supply chain",
        "maritime",
        "rail",
        "railway",
        "truck",
        "trucking",
        "canal",
        "strait",
        "route",
        "routes",
    ],
    "aviation": ["airline", "airport", "aviation", "flight", "airspace", "carrier", "runway", "air cargo"],
    "agriculture_food": [
        "crop",
        "grain",
        "wheat",
        "corn",
        "soy",
        "soybean",
        "harvest",
        "agriculture",
        "fertilizer",
        "livestock",
        "food",
        "farm",
    ],
    "water_utilities": ["water", "reservoir", "utility", "utilities", "desalination", "wastewater", "hydro"],
    "defense_security": ["defense", "military", "weapon", "missile", "security", "troops", "navy", "army", "drone"],
    "manufacturing_supply_chain": [
        "factory",
        "manufacturing",
        "plant",
        "assembly",
        "semiconductor",
        "chip",
        "industrial",
        "mine",
        "smelter",
        "supplier",
    ],
    "finance_insurance": ["bank", "rates", "inflation", "credit", "bond", "treasury", "insurance", "insurer", "fx", "currency"],
}

HOTSPOT_EVENT_TAGS: List[str] = [
    "conflict",
    "disruption",
    "scarcity",
    "disaster",
    "sanctions",
    "infrastructure",
]

CONFLICT_CATEGORIES: List[str] = sorted(HOTSPOT_EVENT_TAGS)


REGION_KEYWORDS: Dict[str, List[str]] = {
    "North America": [
        "north america",
        "united states",
        "u.s.",
        "usa",
        "canada",
        "mexico",
        "panama canal",
    ],
    "Europe": [
        "europe",
        "european union",
        "eu",
        "united kingdom",
        "uk",
        "britain",
        "germany",
        "france",
        "italy",
        "ukraine",
        "russia",
        "kyiv",
        "kharkiv",
        "donbas",
        "crimea",
        "poland",
        "baltic",
        "black sea",
        "romania",
        "belarus",
    ],
    "Middle East": [
        "middle east",
        "gulf",
        "iran",
        "iraq",
        "israel",
        "gaza",
        "west bank",
        "lebanon",
        "syria",
        "yemen",
        "houthi",
        "hezbollah",
        "saudi arabia",
        "saudi",
        "qatar",
        "united arab emirates",
        "uae",
        "oman",
        "jordan",
        "red sea",
    ],
    "Asia-Pacific": [
        "asia pacific",
        "asia-pacific",
        "china",
        "taiwan",
        "japan",
        "korea",
        "south korea",
        "north korea",
        "australia",
        "india",
        "myanmar",
        "burma",
        "yangon",
        "mandalay",
        "rakhine",
        "junta",
        "people's defense force",
        "pdf",
        "philippines",
        "indonesia",
        "vietnam",
        "south china sea",
    ],
    "Latin America": [
        "latin america",
        "brazil",
        "argentina",
        "chile",
        "peru",
        "colombia",
        "venezuela",
        "ecuador",
        "panama",
    ],
    "Africa": [
        "africa",
        "nigeria",
        "south africa",
        "egypt",
        "sudan",
        "south sudan",
        "ethiopia",
        "somalia",
        "mali",
        "burkina faso",
        "niger",
        "mozambique",
        "congo",
        "drc",
        "kenya",
        "sahel",
        "libya",
        "morocco",
        "algeria",
    ],
}

NEWS_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "markets": ["stocks", "equities", "markets", "index", "wall street", "shares"],
    "rates": ["rates", "yield", "treasury", "bond", "fed", "central bank"],
    "energy": ["oil", "gas", "opec", "energy", "power", "electricity"],
    "shipping": ["shipping", "port", "freight", "logistics", "container", "supply chain"],
    "conflict": [
        "war",
        "strike",
        "protest",
        "attack",
        "conflict",
        "ceasefire",
        "missile",
        "drone",
        "shelling",
        "airstrike",
        "offensive",
        "battle",
        "rebel",
        "insurgency",
        "militia",
        "junta",
    ],
    "weather": ["storm", "flood", "hurricane", "cyclone", "wildfire", "heatwave", "drought"],
    "technology": ["ai", "chip", "semiconductor", "cloud", "cyber", "software"],
    "economy": ["gdp", "inflation", "jobs", "employment", "economy", "growth"],
    "policy": ["regulation", "sanction", "tariff", "policy", "election", "government"],
    "commodities": ["gold", "copper", "wheat", "corn", "soy", "commodity"],
}

NEWS_CATEGORIES: List[str] = sorted({
    *NEWS_CATEGORY_KEYWORDS.keys(),
    *EVENT_TAG_KEYWORDS.keys(),
    *IMPACT_CHANNEL_KEYWORDS.keys(),
    *INDUSTRY_KEYWORDS.keys(),
})

NEWS_CATEGORY_ALIASES: Dict[str, str] = {
    "technology": "tech",
    "logistics": "shipping",
    "supply chain": "shipping",
    "commodities": "commodities",
}

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "fear": ["fear", "panic", "crisis", "turmoil", "shock", "uncertainty", "risk", "alarm"],
    "anger": ["anger", "backlash", "protest", "strike", "boycott", "sanction", "outrage"],
    "optimism": ["rally", "surge", "boost", "recover", "optimism", "beat", "rebound"],
    "sadness": ["slump", "decline", "recession", "layoffs", "loss", "downgrade", "damage"],
    "anticipation": ["forecast", "expect", "outlook", "ahead", "guidance", "plan", "watch", "monitor"],
    "relief": ["relief", "reopen", "resume", "aid", "stabilize"],
}

SENTIMENT_LEXICON: Dict[str, int] = {
    "gain": 1,
    "rise": 1,
    "surge": 2,
    "beat": 1,
    "improve": 1,
    "growth": 1,
    "upgrade": 1,
    "record": 1,
    "optimism": 1,
    "recover": 1,
    "drop": -1,
    "fall": -1,
    "slump": -2,
    "decline": -1,
    "miss": -1,
    "downgrade": -1,
    "loss": -1,
    "recession": -2,
    "crisis": -2,
    "uncertainty": -1,
}


def _extract_news_categories(
    text_l: str,
) -> List[str]:
    categories = set()
    for key, keywords in NEWS_CATEGORY_KEYWORDS.items():
        if _match_terms(text_l, keywords):
            categories.add(key)
    if not categories:
        categories.add("general")
    normalized = set()
    for category in categories:
        key = str(category).strip().lower()
        normalized.add(NEWS_CATEGORY_ALIASES.get(key, key))
    return sorted(normalized)


def _score_sentiment(text: str) -> float:
    words = re.findall(r"[a-z]+", (text or "").lower())
    if not words:
        return 0.0
    score = 0
    hits = 0
    for word in words:
        if word in SENTIMENT_LEXICON:
            score += SENTIMENT_LEXICON[word]
            hits += 1
    if hits == 0:
        return 0.0
    return max(-1.0, min(1.0, score / max(1, hits)))


def _extract_emotions(text_l: str) -> Dict[str, int]:
    emotions: Dict[str, int] = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        count = len(_match_terms(text_l, keywords))
        if count:
            emotions[emotion] = count
    return emotions


def classify_event(text: str, summary: str = "") -> Dict[str, object]:
    combined_text = " ".join(part for part in [text, summary] if part).strip()
    text_norm = _normalize_match_text(combined_text)
    industry_counts, industry_terms = _extract_term_matches(text_norm, INDUSTRY_KEYWORDS)
    region_counts, place_terms = _extract_term_matches(text_norm, REGION_KEYWORDS)
    event_counts, event_terms = _extract_term_matches(text_norm, EVENT_TAG_KEYWORDS)
    impact_counts, impact_terms = _extract_term_matches(text_norm, IMPACT_CHANNEL_KEYWORDS)
    industries = sorted(industry_counts.keys())
    regions = sorted(region_counts.keys())
    event_tags = sorted(event_counts.keys())
    impact_channels = sorted(impact_counts.keys())
    categories = _extract_news_categories(text_norm)
    sentiment = _score_sentiment(combined_text)
    emotions = _extract_emotions(text_norm)
    return {
        "industries": industries,
        "regions": regions,
        "tags": event_tags,
        "event_tags": event_tags,
        "event_terms": sorted(
            {
                term
                for values in event_terms.values()
                for term in values
            }
        ),
        "impact_channels": impact_channels,
        "impact_terms": sorted(
            {
                term
                for values in impact_terms.values()
                for term in values
            }
        ),
        "place_terms": sorted(
            {
                term
                for values in place_terms.values()
                for term in values
            }
        ),
        "categories": categories,
        "sentiment": sentiment,
        "emotions": emotions,
        "source_text": combined_text,
        "industry_terms": {
            key: values
            for key, values in industry_terms.items()
            if values
        },
    }


def fetch_news_items(limit: int = 40, enabled: Optional[List[str]] = None) -> Dict[str, object]:
    items: List[Dict[str, object]] = []
    enabled_set = {s.lower() for s in (enabled or [])}
    health = _load_health()
    skipped: List[str] = []
    for collector in DEFAULT_SOURCES:
        if enabled_set and collector.name.lower() not in enabled_set:
            continue
        if _should_skip(health, collector.name):
            skipped.append(collector.name)
            continue
        result = collector.fetch()
        if result.items:
            _record_success(health, collector.name)
        else:
            _record_failure(health, collector.name)
        items.extend(result.items)
    _save_health(health)

    enriched: List[Dict[str, object]] = []
    for item in items:
        title = str(item.get("title", ""))
        summary = str(item.get("summary", "") or "")
        published_ts = _parse_published_ts(str(item.get("published", "")))
        meta = classify_event(title, summary=summary)
        enriched.append({
            **item,
            **meta,
            "published_ts": published_ts,
        })
    enriched = _dedupe_items(enriched)
    enriched.sort(key=lambda it: (it.get("published_ts") or 0), reverse=True)
    enriched = enriched[:limit]
    return {
        "items": enriched,
        "skipped": skipped,
        "health": health,
    }


def load_cached_news(
    path: str,
    ttl_seconds: int,
    allow_stale: bool = False,
) -> Optional[List[Dict[str, object]]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        ts = int(payload.get("ts", 0) or 0)
        if not allow_stale and (int(time.time()) - ts) > ttl_seconds:
            return None
        items = payload.get("items", [])
        if not isinstance(items, list):
            return None
        return _dedupe_items([item for item in items if isinstance(item, dict)])
    except Exception:
        return None


def store_cached_news(path: str, items: List[Dict[str, object]]) -> None:
    payload = {"ts": int(time.time()), "items": _dedupe_items(items)}
    parent = None
    try:
        import os
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    except Exception:
        parent = None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
