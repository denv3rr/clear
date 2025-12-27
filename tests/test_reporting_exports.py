from modules.client_mgr.client_model import Client, Account
from modules.reporting.engine import ReportEngine


class DummyPriceService:
    def get_quotes(self, tickers):
        return {str(ticker): 150.0 for ticker in tickers}


def _build_client():
    acc1 = Account(account_name="Core", account_type="Taxable")
    acc1.holdings = {"AAPL": 10}
    acc1.lots = {"AAPL": [{"qty": 10, "basis": 100.0, "timestamp": "2024-01-01T00:00:00"}]}

    acc2 = Account(account_name="Growth", account_type="Roth IRA")
    acc2.holdings = {"MSFT": 5}
    acc2.lots = {"MSFT": [{"qty": 5, "basis": 200.0, "timestamp": "2024-01-01T00:00:00"}]}

    client = Client(name="Atlas")
    client.accounts = [acc1, acc2]
    return client


def test_client_export_summary_sections():
    engine = ReportEngine(price_service=DummyPriceService())
    client = _build_client()
    report = engine.generate_client_portfolio_report(client, output_format="json", detailed=False)
    assert report.payload.report_type == "client_portfolio_export"
    section_titles = [section.title for section in report.payload.sections]
    assert "Accounts Summary" in section_titles
    assert "Holdings Detail" in section_titles


def test_client_export_detailed_includes_account_sections():
    engine = ReportEngine(price_service=DummyPriceService())
    client = _build_client()
    report = engine.generate_client_portfolio_report(client, output_format="md", detailed=True)
    section_titles = [section.title for section in report.payload.sections]
    assert any(title.startswith("Account Detail:") for title in section_titles)


def test_account_export():
    engine = ReportEngine(price_service=DummyPriceService())
    client = _build_client()
    report = engine.generate_account_portfolio_report(client, client.accounts[0], output_format="md")
    assert report.payload.report_type == "account_portfolio_export"
