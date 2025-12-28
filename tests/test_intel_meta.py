from modules.market_data.intel import get_intel_meta


def test_intel_meta_has_regions_and_sources():
    meta = get_intel_meta()
    assert isinstance(meta.get("regions"), list)
    assert meta["regions"]
    assert isinstance(meta.get("sources"), list)
    assert meta["sources"]
    assert isinstance(meta.get("industries"), list)
    assert meta["industries"]
