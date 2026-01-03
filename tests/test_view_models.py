from datetime import datetime, timedelta

from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.toolkit import RegimeModels
from modules.view_models import (
    _regime_window_payload,
    account_detail,
    client_detail,
    list_clients,
)


def test_client_view_models():
    acc = Account(account_name="Primary", account_type="Taxable")
    acc.holdings = {"AAPL": 5}
    client = Client(name="Nova")
    client.accounts = [acc]

    summary = list_clients([client])[0]
    assert summary["name"] == "Nova"
    assert summary["accounts_count"] == 1

    detail = client_detail(client)
    assert detail["accounts"][0]["account_name"] == "Primary"
    assert detail["accounts"][0]["holdings"]["AAPL"] == 5.0


def test_account_detail_manual_holdings():
    acc = Account(account_name="Alt")
    acc.manual_holdings = [{"total_value": 1234.5}]
    detail = account_detail(acc)
    assert detail["manual_holdings"][0]["total_value"] == 1234.5
    assert detail["active_interval"] == "1M"


def test_account_detail_ignores_invalid_holdings():
    acc = Account(account_name="Alt")
    acc.holdings = {"AAPL": 2, "BROKEN": {"qty": 5}}
    detail = account_detail(acc)
    assert detail["holdings"]["AAPL"] == 2.0
    assert "BROKEN" not in detail["holdings"]


def test_client_detail_includes_tax_profile_and_extra():
    client = Client(name="Nova", tax_profile={"reporting_currency": "EUR"}, extra={"legacy": "yes"})
    acc = Account(account_name="Primary", extra={"origin": "import"})
    client.accounts = [acc]
    detail = client_detail(client)
    assert detail["tax_profile"]["reporting_currency"] == "EUR"
    assert detail["extra"]["legacy"] == "yes"
    assert detail["accounts"][0]["extra"]["origin"] == "import"


def test_regime_window_payload_uses_recent_window():
    base = datetime(2024, 1, 1)
    dates = [base + timedelta(days=idx) for idx in range(40)]
    values = [float(idx) for idx in range(40)]
    payload = _regime_window_payload(dates, values, "1M")
    expected = RegimeModels.INTERVAL_POINTS.get("1M", 21) + 1
    assert payload["interval"] == "1M"
    assert len(payload["series"]) == expected
    assert payload["series"][0]["value"] == values[-expected]
    assert payload["series"][-1]["value"] == values[-1]
