from modules.client_mgr.client_model import Client, Account
from modules.view_models import account_detail, client_detail, list_clients


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
