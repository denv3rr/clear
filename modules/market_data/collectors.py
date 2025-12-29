import json
import time
import os
import re
from email.utils import parsedate_to_datetime
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
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
            if not title:
                continue
            items.append({
                "title": title,
                "url": link,
                "published": pub_date,
                "source": self.name,
            })
        return CollectorResult(self.name, items)


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


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


def _dedupe_items(items: List[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped: Dict[tuple, Dict[str, object]] = {}
    for item in items:
        title = _normalize_title(str(item.get("title", "")))
        source = (item.get("source") or "").strip().lower()
        url = (item.get("url") or "").strip().lower()
        key = (title, source)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
        existing_ts = existing.get("published_ts")
        incoming_ts = item.get("published_ts")
        if incoming_ts and (not existing_ts or incoming_ts > existing_ts):
            deduped[key] = item
            continue
        if not existing.get("url") and item.get("url"):
            deduped[key] = item
            continue
    return list(deduped.values())


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
        with open(HEALTH_FILE, "r", encoding="ascii") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_health(health: Dict[str, Dict[str, object]]) -> None:
    parent = os.path.dirname(HEALTH_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(HEALTH_FILE, "w", encoding="ascii") as f:
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

CONFLICT_CATEGORIES: List[str] = [
    "conflict",
    "world",
    "energy",
    "shipping",
    "defense",
    "finance",
    "tech",
    "agriculture",
    "general",
]


REGION_KEYWORDS: Dict[str, List[str]] = {
    "North America": ["us", "u.s.", "united states", "canada", "mexico"],
    "Europe": ["europe", "eu", "uk", "germany", "france", "italy"],
    "Middle East": ["middle east", "gulf", "iran", "iraq", "israel", "saudi", "qatar"],
    "Asia-Pacific": ["china", "japan", "korea", "australia", "asia", "india"],
    "Latin America": ["brazil", "argentina", "latin america", "chile", "peru"],
    "Africa": ["africa", "nigeria", "south africa", "egypt"],
}

NEWS_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "markets": ["stocks", "equities", "markets", "index", "wall street", "shares"],
    "rates": ["rates", "yield", "treasury", "bond", "fed", "central bank"],
    "energy": ["oil", "gas", "opec", "energy", "power", "electricity"],
    "shipping": ["shipping", "port", "freight", "logistics", "container", "supply chain"],
    "conflict": ["war", "strike", "protest", "attack", "conflict", "ceasefire"],
    "technology": ["ai", "chip", "semiconductor", "cloud", "cyber", "software"],
    "economy": ["gdp", "inflation", "jobs", "employment", "economy", "growth"],
    "policy": ["regulation", "sanction", "tariff", "policy", "election", "government"],
    "commodities": ["gold", "copper", "wheat", "corn", "soy", "commodity"],
}

NEWS_CATEGORIES: List[str] = sorted(
    {*(NEWS_CATEGORY_KEYWORDS.keys()), *CONFLICT_CATEGORIES}
)

NEWS_CATEGORY_ALIASES: Dict[str, str] = {
    "technology": "tech",
    "logistics": "shipping",
    "supply chain": "shipping",
    "commodities": "commodities",
}

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "fear": ["fear", "panic", "crisis", "turmoil", "shock", "uncertainty", "risk"],
    "anger": ["anger", "backlash", "protest", "strike", "boycott", "sanction"],
    "optimism": ["rally", "surge", "boost", "recover", "optimism", "beat"],
    "sadness": ["slump", "decline", "recession", "layoffs", "loss", "downgrade"],
    "anticipation": ["forecast", "expect", "outlook", "ahead", "guidance", "plan"],
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
    tags: List[str],
    industries: List[str],
) -> List[str]:
    categories = set()
    for key, keywords in NEWS_CATEGORY_KEYWORDS.items():
        if any(word in text_l for word in keywords):
            categories.add(key)
    for tag in tags:
        if tag:
            categories.add(str(tag).lower())
    for industry in industries:
        if industry:
            categories.add(str(industry).lower())
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
        count = sum(1 for word in keywords if word in text_l)
        if count:
            emotions[emotion] = count
    return emotions


def classify_event(text: str) -> Dict[str, List[str]]:
    text_l = (text or "").lower()
    industries = [k for k, words in INDUSTRY_KEYWORDS.items() if any(w in text_l for w in words)]
    regions = [k for k, words in REGION_KEYWORDS.items() if any(w in text_l for w in words)]
    tags = []
    if "strike" in text_l or "protest" in text_l:
        tags.append("disruption")
    if "attack" in text_l or "war" in text_l or "conflict" in text_l:
        tags.append("conflict")
    if "storm" in text_l or "hurricane" in text_l or "flood" in text_l:
        tags.append("weather")
    categories = _extract_news_categories(text_l, tags, industries)
    sentiment = _score_sentiment(text)
    emotions = _extract_emotions(text_l)
    return {
        "industries": industries,
        "regions": regions,
        "tags": tags,
        "categories": categories,
        "sentiment": sentiment,
        "emotions": emotions,
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
        published_ts = _parse_published_ts(str(item.get("published", "")))
        meta = classify_event(title)
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
        with open(path, "r", encoding="ascii") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        ts = int(payload.get("ts", 0) or 0)
        if not allow_stale and (int(time.time()) - ts) > ttl_seconds:
            return None
        return payload.get("items", [])
    except Exception:
        return None


def store_cached_news(path: str, items: List[Dict[str, object]]) -> None:
    payload = {"ts": int(time.time()), "items": items}
    parent = None
    try:
        import os
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    except Exception:
        parent = None
    with open(path, "w", encoding="ascii") as f:
        json.dump(payload, f, indent=2)
