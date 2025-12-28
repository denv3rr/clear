from unittest import mock

from modules.market_data.trackers import GlobalTrackers, TrackerPoint, TrackerProviders


class DummyResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_flights_keeps_points_without_speed_or_alt(monkeypatch):
    monkeypatch.setenv("FLIGHT_DATA_URL", "http://example")
    monkeypatch.delenv("FLIGHT_DATA_PATH", raising=False)
    monkeypatch.delenv("CLEAR_INCLUDE_COMMERCIAL", raising=False)
    payload = [
        {
            "lat": 33.63,
            "lon": -84.43,
            "callsign": "AAL123",
            "category": "commercial",
        }
    ]
    with mock.patch("modules.market_data.trackers.requests.get", return_value=DummyResponse(payload)):
        points, warnings = TrackerProviders.fetch_flights()
    assert points
    assert warnings == []


def test_fetch_flights_merges_multiple_urls(monkeypatch):
    monkeypatch.setenv("FLIGHT_DATA_URL", "http://example/a,http://example/b")
    monkeypatch.delenv("FLIGHT_DATA_PATH", raising=False)

    def fake_get(url, timeout=8):
        if url.endswith("/a"):
            return DummyResponse([{"lat": 1.0, "lon": 2.0, "callsign": "AAA111"}])
        return DummyResponse([{"lat": 3.0, "lon": 4.0, "callsign": "BBB222"}])

    with mock.patch("modules.market_data.trackers.requests.get", side_effect=fake_get):
        points, warnings = TrackerProviders.fetch_flights()
    labels = {pt.label for pt in points}
    assert labels == {"AAA111", "BBB222"}
    assert warnings == []


def test_snapshot_marks_unknown_fields():
    trackers = GlobalTrackers()
    trackers._cached = {
        "flights": [
            TrackerPoint(
                lat=1.0,
                lon=2.0,
                label="NOINFO",
                category="commercial",
                kind="flight",
            )
        ],
        "ships": [],
        "warnings": [],
    }
    trackers._state["cached"] = trackers._cached
    snapshot = trackers.get_snapshot(mode="flights", allow_refresh=False)
    point = snapshot["points"][0]
    assert point["operator"] == "unknown"
    assert point["flight_number"] == "unknown"
    assert point["tail_number"] == "unknown"
    assert point["callsign"] == "unknown"
    assert point["icao24"] == "unknown"


def test_fetch_flights_uses_opensky_when_no_feed(monkeypatch):
    monkeypatch.delenv("FLIGHT_DATA_URL", raising=False)
    monkeypatch.delenv("FLIGHT_DATA_PATH", raising=False)
    monkeypatch.setenv("CLEAR_INCLUDE_COMMERCIAL", "1")

    class OpenSkyResponse:
        status_code = 200

        def json(self):
            return {
                "states": [
                    [
                        "abc123",
                        "AAL123",
                        "United States",
                        1700000000,
                        1700000001,
                        -84.43,
                        33.63,
                        10000.0,
                        False,
                        200.0,
                        90.0,
                        0.0,
                        None,
                        11000.0,
                        "1200",
                        False,
                        0,
                    ]
                ]
            }

    with mock.patch("modules.market_data.trackers.requests.get", return_value=OpenSkyResponse()):
        points, warnings = TrackerProviders.fetch_flights()
    assert points
    assert warnings == []
