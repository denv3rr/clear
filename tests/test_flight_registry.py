from modules.market_data.flight_registry import get_operator_info


def test_operator_registry_defaults():
    info = get_operator_info("AAL")
    assert info["name"] == "American Airlines"
    assert info["country"] == "United States"


def test_operator_registry_missing():
    info = get_operator_info("ZZZ")
    assert info["name"] == ""
