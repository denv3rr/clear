from modules.market_data.intel import REGIONS
from modules.market_data.scene_payloads import build_intel_scene, build_tracker_scene


def test_build_tracker_scene_payload_composes_live_points_and_trails():
    snapshot = {
        "mode": "combined",
        "warnings": ["source warning"],
        "points": [
            {
                "id": "flt-1",
                "kind": "flight",
                "category": "commercial",
                "label": "AAL120",
                "lat": 40.64,
                "lon": -73.78,
                "updated_ts": 1700000100,
                "speed_heat": 0.6,
                "operator": "AAL",
                "operator_name": "American Airlines",
                "country": "United States",
            },
            {
                "id": "ship-1",
                "kind": "ship",
                "category": "cargo",
                "label": "EVER PRIME",
                "lat": 34.05,
                "lon": 120.3,
                "updated_ts": 1700000200,
                "speed_heat": 0.3,
                "operator": "Evergreen",
                "operator_name": "Evergreen Marine",
                "country": "Singapore",
            },
        ],
    }

    histories = {
        "flt-1": {
            "history": [
                {"ts": 1700000000, "lat": 40.64, "lon": -73.78, "speed_kts": 420, "altitude_ft": 33000},
                {"ts": 1700000300, "lat": 40.2, "lon": -72.1, "speed_kts": 430, "altitude_ft": 33100},
            ],
            "summary": {
                "distance_km": 180.5,
                "duration_sec": 300,
                "avg_speed_kts": 425.0,
                "avg_altitude_ft": 33050.0,
                "route_hint": "JFK -> offshore",
            },
        }
    }

    scene = build_tracker_scene(
        snapshot,
        history_fetcher=lambda tracker_id: histories.get(tracker_id, {"history": []}),
        now=1700000400,
        trail_limit=2,
    )

    assert scene["scene_id"] == "osint-trackers"
    assert scene["kind"] == "osint"
    assert scene["layers"][0]["kind"] == "point"
    assert scene["layers"][1]["kind"] == "path"
    assert len(scene["layers"][0]["features"]) == 2
    assert len(scene["layers"][1]["features"]) == 1
    assert scene["layers"][0]["features"][0]["geometry"]["type"] == "Point"
    assert scene["layers"][1]["features"][0]["geometry"]["type"] == "LineString"
    assert scene["timeline"]["point_count"] == 2
    assert scene["timeline"]["trail_count"] == 1
    assert scene["focus_targets"]
    assert scene["meta"]["selected_point_count"] == 2
    assert "source warning" in scene["meta"]["warnings"]


def test_build_intel_scene_payload_uses_regional_centroids_and_provenance():
    class DummyWeather:
        def fetch(self, region):
            if region.name == "Middle East":
                return {"error": "Open-Meteo HTTP 503"}
            if region.name == "Europe":
                return {
                    "temp_c": 8.0,
                    "wind_ms": 18.0,
                    "precip_mm": 3.0,
                    "precip_24h": 14.0,
                    "wind_max": 22.0,
                    "temp_min": 4.0,
                    "temp_max": 13.0,
                    "impacts": ["Gusty conditions could slow air and sea logistics."],
                }
            return {
                "temp_c": 24.0,
                "wind_ms": 6.0,
                "precip_mm": 0.0,
                "precip_24h": 1.0,
                "wind_max": 8.0,
                "temp_min": 20.0,
                "temp_max": 27.0,
                "impacts": [],
            }

    class DummyConflict:
        def fetch(self, region):
            if region.name == "Europe":
                return {
                    "count": 9,
                    "articles": [
                        {"themes": "shipping, military"},
                        {"themes": "energy, logistics"},
                    ],
                    "impacts": ["Shipping and logistics risk elevated."],
                }
            if region.name == "Middle East":
                return {
                    "error": "GDELT is in cooldown. Try again later.",
                    "cooldown": True,
                }
            return {"count": 0, "articles": [], "impacts": []}

    class DummyIntel:
        def __init__(self):
            self.weather = DummyWeather()
            self.conflict = DummyConflict()

        def fetch_news_signals(self, ttl_seconds=600, enabled_sources=None):
            return {
                "items": [
                    {
                        "title": "European shipping disruption risk rises",
                        "source": "Reuters",
                        "published_ts": 1700000000,
                        "regions": ["Europe"],
                        "industries": ["shipping"],
                        "tags": ["conflict", "disruption"],
                        "categories": ["conflict"],
                        "sentiment": -0.6,
                        "emotions": {"fear": 2},
                    },
                    {
                        "title": "Middle East energy routes remain under pressure",
                        "source": "FT",
                        "published_ts": 1699999800,
                        "regions": ["Middle East"],
                        "industries": ["energy"],
                        "tags": ["conflict", "energy"],
                        "categories": ["conflict"],
                        "sentiment": -0.4,
                        "emotions": {"fear": 1, "urgency": 1},
                    },
                    {
                        "title": "Asia-Pacific factories stabilize after port backlog clears",
                        "source": "Bloomberg",
                        "published_ts": 1699999700,
                        "regions": ["Asia-Pacific"],
                        "industries": ["manufacturing"],
                        "tags": ["supply-chain"],
                        "categories": ["macro"],
                        "sentiment": 0.2,
                        "emotions": {"relief": 1},
                    },
                ],
                "cached": True,
                "stale": True,
                "skipped": ["AP"],
                "health": {"Reuters": {"last_ok": 1700000000}},
            }

        def filter_news_items(self, items, region_name, industry_filter, tickers=None):
            filtered = []
            for item in items:
                if region_name != "Global" and region_name not in (item.get("regions") or []):
                    continue
                if industry_filter != "all" and industry_filter not in (item.get("industries") or []):
                    continue
                filtered.append(item)
            return filtered

        def _filter_impacts(self, impacts, industry_filter):
            if industry_filter == "all":
                return impacts
            return [impact for impact in impacts if industry_filter.lower() in impact.lower()]

    scene = build_intel_scene(
        DummyIntel(),
        now=1700000400,
    )

    assert scene["scene_id"] == "osint-intel"
    assert scene["layers"][0]["kind"] == "point"
    assert len(scene["layers"][0]["features"]) == len(REGIONS) - 1
    assert all(
        feature["properties"]["display_scope"] == "region-centroid"
        for feature in scene["layers"][0]["features"]
    )
    assert all(
        feature["properties"]["region"] != "Global"
        for feature in scene["layers"][0]["features"]
    )
    assert scene["meta"]["stale_news"] is True
    assert "News cache is stale; regional signals may lag live conditions." in scene["meta"]["warnings"]

    europe = next(
        feature
        for feature in scene["layers"][0]["features"]
        if feature["properties"]["region"] == "Europe"
    )
    assert europe["properties"]["combined_risk"]["score"] is not None
    assert europe["properties"]["conflict"]["status"] == "gdelt"
    assert europe["properties"]["presentation"]["dominant_channel"] in {"weather", "conflict", "news", "combined"}

    middle_east = next(
        feature
        for feature in scene["layers"][0]["features"]
        if feature["properties"]["region"] == "Middle East"
    )
    assert middle_east["properties"]["weather"]["status"] == "unavailable"
    assert middle_east["properties"]["conflict"]["status"] == "rss_fallback"
    assert any(
        "precise event locations" in warning.lower() for warning in middle_east["warnings"]
    )
