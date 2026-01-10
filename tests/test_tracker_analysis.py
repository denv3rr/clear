import time

from modules.market_data.trackers import GlobalTrackers


def test_tracker_analysis_loiter_and_geofence():
    trackers = GlobalTrackers()
    tracker_id = "abc123"
    tracker_key = "flight:ABC123:US:commercial"
    now = int(time.time())

    trackers._id_index = {tracker_id: tracker_key}
    trackers._path_history = {
        tracker_key: [
            (now - 1800, 40.0, -73.0, 250.0, 30000.0, 90.0),
            (now - 600, 40.001, -73.001, 240.0, 30000.0, 95.0),
            (now, 40.0, -73.0, 245.0, 30000.0, 100.0),
        ]
    }

    analysis = trackers.analyze_tracker(
        tracker_id,
        window_sec=4000,
        loiter_radius_km=5.0,
        loiter_min_minutes=20.0,
        geofences=[
            {"id": "f1", "label": "Test Fence", "lat": 40.0, "lon": -73.0, "radius_km": 5.0}
        ],
    )

    assert analysis["loiter"]["detected"] is True
    assert analysis["geofences"]["events"]
    assert analysis["replay"]
