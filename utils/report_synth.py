import hashlib
import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional


_WORD_RE = re.compile(r"[A-Za-z']+")

EMOTION_LEXICON = {
    "fear": ["fear", "risk", "threat", "panic", "anxiety", "volatile", "crisis"],
    "anger": ["anger", "outrage", "protest", "riot", "strike", "backlash"],
    "optimism": ["optimism", "rebound", "recovery", "growth", "rally", "improve"],
    "sadness": ["loss", "decline", "downturn", "recession", "collapse"],
    "uncertainty": ["uncertain", "unknown", "volatile", "instability", "fragile"],
    "urgency": ["urgent", "immediate", "rapid", "emergency", "critical"],
}

BIAS_MARKERS = [
    "alleged",
    "reportedly",
    "sources say",
    "according to",
    "claims",
    "insiders",
]

SENSATIONALISM_MARKERS = [
    "shocking",
    "collapse",
    "meltdown",
    "panic",
    "chaos",
    "crisis",
]


@dataclass
class ReportContext:
    report_type: str
    region: str
    industry: str
    summary: List[str]
    risk_level: Optional[str]
    risk_score: Optional[int]
    confidence: Optional[str]
    signals: List[str]
    impacts: List[str]
    sections: List[Dict[str, object]]
    news_items: List[Dict[str, object]]


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in _WORD_RE.findall(text or "")]


def _score_text(text: str) -> Dict[str, object]:
    tokens = _tokenize(text)
    token_counts = Counter(tokens)
    total = len(tokens)
    emotion_counts = {k: 0 for k in EMOTION_LEXICON}
    triggers = {k: [] for k in EMOTION_LEXICON}
    bias_hits = []
    sensational_hits = []
    text_l = (text or "").lower()

    for emotion, words in EMOTION_LEXICON.items():
        for word in words:
            count = token_counts.get(word, 0)
            if count:
                emotion_counts[emotion] += count
                triggers[emotion].append(word)

    for marker in BIAS_MARKERS:
        if marker in text_l:
            bias_hits.append(marker)

    for marker in SENSATIONALISM_MARKERS:
        if marker in text_l:
            sensational_hits.append(marker)

    emotion_density = {
        k: (emotion_counts[k] / total) if total else 0.0
        for k in emotion_counts
    }
    overall = sum(emotion_counts.values()) / total if total else 0.0
    return {
        "total_words": total,
        "emotion_counts": emotion_counts,
        "emotion_density": emotion_density,
        "emotion_triggers": {k: sorted(set(v)) for k, v in triggers.items()},
        "bias_markers": sorted(set(bias_hits)),
        "sensationalism_markers": sorted(set(sensational_hits)),
        "overall_emotion_score": overall,
    }


def analyze_news_items(items: List[Dict[str, object]]) -> Dict[str, object]:
    per_item = []
    totals = {k: 0.0 for k in EMOTION_LEXICON}
    total_articles = 0
    bias_terms = []
    sensational_terms = []
    for item in items:
        title = str(item.get("title", ""))
        score = _score_text(title)
        per_item.append({
            "title": title,
            "source": item.get("source", ""),
            "emotion_density": score["emotion_density"],
            "emotion_triggers": score["emotion_triggers"],
            "bias_markers": score["bias_markers"],
            "sensationalism_markers": score["sensationalism_markers"],
            "overall_emotion_score": score["overall_emotion_score"],
        })
        for key, val in score["emotion_density"].items():
            totals[key] += float(val)
        bias_terms.extend(score["bias_markers"])
        sensational_terms.extend(score["sensationalism_markers"])
        total_articles += 1

    aggregate = {
        "emotion_density": {
            k: (totals[k] / total_articles) if total_articles else 0.0
            for k in totals
        },
        "bias_markers": sorted(set(bias_terms)),
        "sensationalism_markers": sorted(set(sensational_terms)),
        "article_count": total_articles,
    }
    return {"aggregate": aggregate, "items": per_item}


def filter_fresh_news_items(
    items: List[Dict[str, object]],
    max_age_hours: int = 24,
) -> List[Dict[str, object]]:
    if not items:
        return []
    now = int(time.time())
    cutoff = now - int(max_age_hours * 3600)
    fresh: List[Dict[str, object]] = []
    for item in items:
        ts = item.get("published_ts")
        if ts is None:
            continue
        try:
            ts_int = int(ts)
        except Exception:
            continue
        if ts_int >= cutoff:
            fresh.append(item)
    return fresh


def build_report_context(
    report: Dict[str, object],
    report_type: str,
    region: str,
    industry: str,
    news_items: Optional[List[Dict[str, object]]] = None,
) -> ReportContext:
    return ReportContext(
        report_type=report_type,
        region=region,
        industry=industry,
        summary=list(report.get("summary", []) or []),
        risk_level=report.get("risk_level"),
        risk_score=report.get("risk_score"),
        confidence=report.get("confidence"),
        signals=list(report.get("signals", []) or []),
        impacts=list(report.get("impacts", []) or []),
        sections=list(report.get("sections", []) or []),
        news_items=list(news_items or []),
    )


def _context_to_payload(
    context: ReportContext,
    news_items_override: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    news_items = news_items_override if news_items_override is not None else context.news_items
    return {
        "report_type": context.report_type,
        "region": context.region,
        "industry": context.industry,
        "summary": context.summary,
        "risk_level": context.risk_level,
        "risk_score": context.risk_score,
        "confidence": context.confidence,
        "signals": context.signals,
        "impacts": context.impacts,
        "news_items": [
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "tags": item.get("tags", []),
                "regions": item.get("regions", []),
                "industries": item.get("industries", []),
            }
            for item in news_items
        ],
    }


def _compute_cache_key(payload: Dict[str, object], provider: str, model_id: str, persona: str) -> str:
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(stable.encode("ascii", "ignore")).hexdigest()
    return f"{provider}:{model_id}:{persona}:{digest}"


def _load_news_freshness_hours(default_value: int = 4) -> int:
    settings_path = os.path.join(os.getcwd(), "config", "settings.json")
    try:
        with open(settings_path, "r", encoding="ascii") as f:
            data = json.load(f)
    except Exception:
        return default_value
    if not isinstance(data, dict):
        return default_value
    ai = data.get("ai", {})
    if not isinstance(ai, dict):
        return default_value
    raw = ai.get("news_freshness_hours")
    try:
        value = int(raw)
    except Exception:
        return default_value
    return max(1, value)


class ReportSynthesizer:
    def __init__(
        self,
        provider: str = "auto",
        model_id: str = "rule_based_v1",
        persona: str = "advisor_legal_v1",
        cache_file: str = "data/ai_report_cache.json",
        cache_ttl: int = 21600,
        endpoint: str = "",
        news_freshness_hours: Optional[int] = None,
    ):
        self.provider = provider
        self.model_id = model_id
        self.persona = persona
        self.cache_file = cache_file
        self.cache_ttl = cache_ttl
        self.endpoint = endpoint
        if news_freshness_hours is None:
            self.news_freshness_hours = _load_news_freshness_hours()
        else:
            self.news_freshness_hours = max(1, int(news_freshness_hours))

    def synthesize(self, context: ReportContext) -> Dict[str, object]:
        fresh_news = filter_fresh_news_items(context.news_items, self.news_freshness_hours)
        payload = _context_to_payload(context, news_items_override=fresh_news)
        provider = (self.provider or "auto").lower()
        if provider == "local_http":
            cache_key = _compute_cache_key(payload, "local_http", self.model_id, self.persona)
            cached = _load_cache(self.cache_file, cache_key, self.cache_ttl)
            if cached:
                cached["cache"] = {"hit": True}
                return cached
        elif provider == "auto" and self.endpoint:
            cache_key = _compute_cache_key(payload, "local_http", self.model_id, self.persona)
            cached = _load_cache(self.cache_file, cache_key, self.cache_ttl)
            if cached:
                cached["cache"] = {"hit": True}
                return cached

        cache_key_rule = _compute_cache_key(payload, "rule_based", "rule_based_v1", self.persona)
        cached = _load_cache(self.cache_file, cache_key_rule, self.cache_ttl)
        if cached:
            cached["cache"] = {"hit": True}
            return cached

        analysis = analyze_news_items(fresh_news)
        analysis["fresh_article_count"] = len(fresh_news)
        analysis["stale_filtered"] = max(0, len(context.news_items) - len(fresh_news))
        if provider in ("local_http", "auto") and self.endpoint:
            response = _try_local_llm(self.endpoint, payload, self.persona)
            if response:
                result = {
                    "outlook": response.get("outlook", ""),
                    "notes": response.get("notes", []),
                    "analysis": analysis,
                    "provider": "local_http",
                    "model_id": self.model_id,
                    "persona": self.persona,
                }
                cache_key = _compute_cache_key(payload, "local_http", self.model_id, self.persona)
                _store_cache(self.cache_file, cache_key, result)
                result["cache"] = {"hit": False}
                return result

        result = _rule_based_synthesis(context, analysis)
        _store_cache(self.cache_file, cache_key_rule, result)
        result["cache"] = {"hit": False}
        return result


def _rule_based_synthesis(context: ReportContext, analysis: Dict[str, object]) -> Dict[str, object]:
    risk = context.risk_level or "Unrated"
    confidence = context.confidence or "Unknown"
    signals = context.signals[:6]
    impacts = context.impacts[:6]

    outlook = (
        f"{context.report_type.title()} outlook for {context.region} "
        f"with {context.industry} exposure remains {risk.lower()} risk. "
        f"Confidence is {confidence.lower()} with monitoring focus on "
        f"{', '.join(signals[:3]) if signals else 'macro and supply signals'}."
    )

    notes = [
        f"Risk posture: {risk} (score {context.risk_score or 'n/a'}).",
        f"Primary drivers: {', '.join(signals) if signals else 'No dominant signals identified.'}",
        f"Impact channels: {', '.join(impacts) if impacts else 'No direct impact channels detected.'}",
        "Liquidity and funding lines should be stress-tested against a 24-72h disruption window.",
        "Confirm contractual force majeure triggers and insurance exclusions for conflict/weather events.",
        "Review counterparty concentration and delivery obligations tied to affected regions.",
        "Regulatory exposure: verify cross-border sanctions/compliance posture where applicable.",
        "Monitoring triggers: escalation in conflict density, logistics delays, or volatility spikes.",
        "Recommended action: tighten position limits or add hedges where exposure is outsized.",
    ]

    return {
        "outlook": outlook,
        "notes": notes,
        "analysis": analysis,
        "provider": "rule_based",
        "model_id": "rule_based_v1",
        "persona": "advisor_legal_v1",
    }


def _try_local_llm(endpoint: str, payload: Dict[str, object], persona: str) -> Optional[Dict[str, object]]:
    try:
        import requests
        resp = requests.post(
            endpoint,
            json={"persona": persona, "report": payload},
            timeout=12,
        )
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def _load_cache(path: str, key: str, ttl_seconds: int) -> Optional[Dict[str, object]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="ascii") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None
        entry = payload.get(key)
        if not entry:
            return None
        ts = int(entry.get("ts", 0) or 0)
        if (int(time.time()) - ts) > ttl_seconds:
            return None
        return entry.get("data")
    except Exception:
        return None


def _store_cache(path: str, key: str, data: Dict[str, object]) -> None:
    payload = {}
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="ascii") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                payload = {}
    except Exception:
        payload = {}
    payload[key] = {"ts": int(time.time()), "data": data}
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="ascii") as f:
        json.dump(payload, f, indent=2)


def build_ai_sections(ai_payload: Dict[str, object]) -> List[Dict[str, object]]:
    sections = []
    outlook = ai_payload.get("outlook")
    notes = ai_payload.get("notes") or []
    analysis = ai_payload.get("analysis") or {}
    agg = analysis.get("aggregate", {}) if isinstance(analysis, dict) else {}
    density = agg.get("emotion_density", {}) if isinstance(agg, dict) else {}

    if outlook:
        sections.append({
            "title": "Advisor Outlook",
            "rows": [[outlook, ""]],
        })
    if notes:
        sections.append({
            "title": "Advisor Notes",
            "rows": [[f"- {note}", ""] for note in notes],
        })
    fresh_count = analysis.get("fresh_article_count")
    stale_filtered = analysis.get("stale_filtered")
    if density or fresh_count is not None:
        rows = []
        if fresh_count is not None:
            rows.append(["Fresh Articles", str(fresh_count)])
        if stale_filtered is not None:
            rows.append(["Stale Filtered", str(stale_filtered)])
        rows.extend([[key.title(), f"{value:.2f}"] for key, value in density.items()])
        if agg.get("bias_markers"):
            rows.append(["Bias Markers", ", ".join(agg.get("bias_markers"))])
        if agg.get("sensationalism_markers"):
            rows.append(["Sensationalism", ", ".join(agg.get("sensationalism_markers"))])
        sections.append({
            "title": "News Emotion",
            "rows": rows,
        })
    return sections
