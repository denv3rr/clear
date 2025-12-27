from modules.market_data.trackers import GlobalTrackers, TrackerPoint


def test_search_snapshot_matches_fields():
    trackers = GlobalTrackers()
    snapshot = {
        "points": [
            {
                "kind": "flight",
                "label": "AAL762",
                "category": "commercial",
                "icao24": "abc123",
                "callsign": "AAL762",
                "operator": "AAL",
                "flight_number": "762",
                "tail_number": "N123AA",
                "country": "United States",
            },
            {
                "kind": "ship",
                "label": "VESSEL01",
                "category": "cargo",
                "country": "Singapore",
            },
        ]
    }
    result = trackers.search_snapshot(snapshot, query="aal", fields=None, kind="flight", limit=10)
    assert result["count"] == 1
    assert result["points"][0]["label"] == "AAL762"


def test_history_returns_empty_for_missing_id():
    trackers = GlobalTrackers()
    result = trackers.get_history("missing")
    assert result["history"] == []


def test_history_summary_distance():
    trackers = GlobalTrackers()
    trackers._path_history = {
        "flight:TEST:US:commercial": [
            (1, 0.0, 0.0, 400.0, 30000.0, 90.0),
            (2, 1.0, 1.0, 410.0, 31000.0, 95.0),
        ]
    }
    trackers._id_index = {"abc123": "flight:TEST:US:commercial"}
    trackers._state["path_history"] = trackers._path_history
    trackers._state["id_index"] = trackers._id_index
    trackers._state["route_cache"] = {}
    result = trackers.get_history("abc123")
    assert result["summary"]["points"] == 2
    assert result["summary"]["distance_km"] > 0
    assert result["summary"]["direction"] in {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    assert result["summary"]["avg_altitude_ft"] is not None
    assert "->" in result["summary"]["route_hint"]
    # Second call should hit cache
    result_cached = trackers.get_history("abc123")
    assert result_cached["summary"]["distance_km"] == result["summary"]["distance_km"]


def test_detail_returns_point():
    trackers = GlobalTrackers()
    trackers._cached = {
        "flights": [
            TrackerPoint(
                lat=1.0,
                lon=2.0,
                label="AAL762",
                category="commercial",
                kind="flight",
                icao24="abc123",
            )
        ],
        "ships": [],
        "warnings": [],
    }
    trackers._state["cached"] = trackers._cached
    detail = trackers.get_detail("abc123", allow_refresh=False)
    assert detail["point"]["label"] == "AAL762"
