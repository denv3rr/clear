import pytest

from scripts.capture_globe_fixture import validate_tracker_scene_capture


def test_tracker_fixture_validation_rejects_empty_scene():
    with pytest.raises(RuntimeError, match="failed closed"):
        validate_tracker_scene_capture(
            {
                "scene_payload": {
                    "scene_id": "osint-trackers",
                    "layers": [
                        {"id": "live-trackers", "kind": "point", "features": []},
                        {"id": "tracker-trails", "kind": "path", "features": []},
                    ],
                    "focus_targets": [],
                    "meta": {
                        "warnings": [
                            "No live flight data returned from OpenSky.",
                            "No vessel feed configured.",
                        ]
                    },
                }
            }
        )
