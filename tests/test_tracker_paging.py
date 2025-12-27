from modules.market_data.trackers import GlobalTrackers


def test_slice_points_clamps_offset():
    points = [{"id": i} for i in range(10)]
    sample, offset, total = GlobalTrackers._slice_points(points, offset=8, limit=4)
    assert total == 10
    assert offset == 6
    assert [row["id"] for row in sample] == [6, 7, 8, 9]


def test_slice_points_handles_empty():
    sample, offset, total = GlobalTrackers._slice_points([], offset=3, limit=5)
    assert sample == []
    assert offset == 0
    assert total == 0
