import json
import time
import unittest
from unittest import mock

from modules.client_mgr.client_model import Account, Client
from modules.reporting.engine import (
    LocalHttpRunner,
    NoModelRunner,
    OllamaRunner,
    PromptBuilder,
    ReportEngine,
    ReportRenderer,
    ReportSection,
    ReportPayload,
    validate_report_schema,
    report_health_check,
    select_model_runner,
    _load_reporting_ai_settings,
)


class FakeModelRunner:
    def __init__(self, payload: str, available: bool = True):
        self.payload = payload
        self._available = available

    def available(self) -> bool:
        return self._available

    def generate(self, prompt):
        return self.payload


class TestReportEngine(unittest.TestCase):
    def test_generate_weekly_brief_template(self):
        client = Client(client_id="client-1", name="Test Client")
        acct = Account(account_name="Primary")
        acct.holdings = {"AAPL": 2.0}
        acct.lots = {"AAPL": [{"qty": 2.0, "basis": 100.0, "timestamp": "2023-01-01T10:00:00"}]}
        client.accounts.append(acct)

        engine = ReportEngine(model_runner=NoModelRunner())
        result = engine.generate_client_weekly_brief(client, output_format="md")
        self.assertIn("Client Weekly Brief", result.content)
        self.assertIn("Portfolio Snapshot", result.content)
        self.assertFalse(result.used_model)

    def test_weekly_brief_skips_trackers_without_tags(self):
        client = Client(client_id="client-5", name="No Tags")
        acct = Account(account_name="Primary")
        acct.holdings = {"AAPL": 1.0}
        client.accounts.append(acct)

        engine = ReportEngine(model_runner=NoModelRunner())
        with mock.patch("modules.reporting.engine.GlobalTrackers") as trackers:
            result = engine.generate_client_weekly_brief(client, output_format="md")
        titles = [section.title for section in result.payload.sections]
        self.assertNotIn("Aviation/Maritime Notes", titles)
        trackers.assert_not_called()

    def test_weekly_brief_includes_trackers_with_relevance(self):
        client = Client(client_id="client-6", name="Logistics Client")
        acct = Account(account_name="Primary")
        acct.holdings = {"AAPL": 1.0}
        acct.tags = ["shipping"]
        client.accounts.append(acct)

        mock_tracker = mock.MagicMock()
        mock_tracker._last_refresh = int(time.time())
        mock_tracker.get_snapshot.return_value = {
            "points": [
                {"kind": "ship", "category": "cargo", "label": "VESSEL-1"}
            ]
        }

        engine = ReportEngine(model_runner=NoModelRunner())
        with mock.patch("modules.reporting.engine.GlobalTrackers", return_value=mock_tracker):
            result = engine.generate_client_weekly_brief(client, output_format="md")
        titles = [section.title for section in result.payload.sections]
        self.assertIn("Aviation/Maritime Notes", titles)
        self.assertIn("trackers_cache", result.payload.data_freshness)

    def test_renderer_json(self):
        payload = ReportPayload(
            report_type="demo",
            client_id="c1",
            client_name="Client",
            generated_at="2025-01-01T00:00:00Z",
            interval="1M",
            sections=[ReportSection("Section", [["Key", "Value"]])],
            data={},
            data_freshness={},
            methodology=["Note"],
        )
        text = ReportRenderer.render_json(payload)
        self.assertIn("\"report_type\": \"demo\"", text)

    def test_prompt_builder(self):
        payload = ReportPayload(
            report_type="demo",
            client_id="c1",
            client_name="Client",
            generated_at="2025-01-01T00:00:00Z",
            interval="1M",
            sections=[],
            data={},
            data_freshness={},
            methodology=[],
        )
        prompt = PromptBuilder.build(payload)
        self.assertIn("schema", prompt)
        self.assertIn("report", prompt)

    def test_schema_validation(self):
        ok, errors = validate_report_schema({"summary": [], "sections": [], "citations": [], "risks": []})
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        ok, errors = validate_report_schema({"summary": []})
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_health_check(self):
        health = report_health_check()
        self.assertIn("report_engine", health)

    def test_select_model_runner_auto_prefers_ollama(self):
        settings = {"enabled": True, "provider": "auto", "model_id": "llama3", "endpoint": "http://127.0.0.1:8080"}
        with mock.patch("modules.reporting.engine.shutil.which") as which:
            which.return_value = "ollama"
            runner = select_model_runner(settings=settings)
            self.assertIsInstance(runner, OllamaRunner)

    def test_select_model_runner_auto_falls_back_local_http(self):
        settings = {"enabled": True, "provider": "auto", "model_id": "llama3", "endpoint": "http://127.0.0.1:8080"}
        with mock.patch("modules.reporting.engine.shutil.which") as which, \
            mock.patch("requests.get") as http_get:
            which.return_value = None
            http_get.return_value.status_code = 200
            runner = select_model_runner(settings=settings)
            self.assertIsInstance(runner, LocalHttpRunner)

    def test_local_http_runner_generate_parses_content(self):
        runner = LocalHttpRunner(model_id="llama3", endpoint="http://127.0.0.1:8080")
        with mock.patch("requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "choices": [{"message": {"content": "{\"summary\": [], \"sections\": [], \"citations\": [], \"risks\": []}"}}]
            }
            text = runner.generate({"schema": "x"})
            self.assertIn("\"summary\"", text)

    def test_load_reporting_ai_settings_prefers_reporting(self):
        payload = {
            "ai": {"provider": "local_http", "model_id": "base"},
            "reporting": {"ai": {"provider": "ollama", "model_id": "llama3", "news_freshness_hours": 2}},
        }
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(payload))), \
            mock.patch("os.path.exists") as exists:
            exists.return_value = True
            settings = _load_reporting_ai_settings()
            self.assertEqual(settings.get("provider"), "ollama")
            self.assertEqual(settings.get("model_id"), "llama3")
            self.assertEqual(settings.get("news_freshness_hours"), 2)

    def test_load_reporting_ai_settings_falls_back_ai(self):
        payload = {
            "ai": {"provider": "local_http", "model_id": "base", "news_freshness_hours": 3},
            "reporting": {},
        }
        with mock.patch("builtins.open", mock.mock_open(read_data=json.dumps(payload))), \
            mock.patch("os.path.exists") as exists:
            exists.return_value = True
            settings = _load_reporting_ai_settings()
            self.assertEqual(settings.get("provider"), "local_http")
            self.assertEqual(settings.get("model_id"), "base")
            self.assertEqual(settings.get("news_freshness_hours"), 3)

    def test_report_news_filters_by_freshness(self):
        client = Client(client_id="client-4", name="News Freshness")
        acct = Account(account_name="Primary")
        acct.holdings = {"AAPL": 1.0}
        client.accounts.append(acct)
        now = int(time.time())
        items = [
            {"title": "Fresh AAPL update", "source": "Test", "published_ts": now - 60},
            {"title": "Old AAPL update", "source": "Test", "published_ts": now - 3600 * 24},
        ]
        with mock.patch("modules.reporting.engine._load_cached_news") as load_news, \
            mock.patch("modules.reporting.engine._load_reporting_ai_settings") as ai_settings:
            load_news.return_value = items
            ai_settings.return_value = {"news_freshness_hours": 1}
            engine = ReportEngine(model_runner=NoModelRunner())
            result = engine.generate_client_weekly_brief(client, output_format="md")
            self.assertIn("Fresh AAPL update", result.content)
            self.assertNotIn("Old AAPL update", result.content)

    def test_model_runner_valid_schema(self):
        client = Client(client_id="client-2", name="Model Client")
        acct = Account(account_name="Primary")
        acct.holdings = {"MSFT": 1.0}
        client.accounts.append(acct)

        model_payload = {
            "summary": ["Model summary"],
            "sections": [{"title": "Model Section", "rows": [["Key", "Value"]]}],
            "citations": [],
            "risks": [],
        }
        runner = FakeModelRunner(payload=json.dumps(model_payload))
        engine = ReportEngine(model_runner=runner)
        result = engine.generate_client_weekly_brief(client, output_format="md")
        self.assertTrue(result.used_model)
        self.assertEqual(result.payload.sections[0].title, "Model Section")

    def test_model_runner_invalid_schema_fallback(self):
        client = Client(client_id="client-3", name="Bad Model Client")
        acct = Account(account_name="Primary")
        acct.holdings = {"MSFT": 1.0}
        client.accounts.append(acct)

        runner = FakeModelRunner(payload=json.dumps({"summary": []}))
        engine = ReportEngine(model_runner=runner)
        result = engine.generate_client_weekly_brief(client, output_format="md")
        self.assertFalse(result.used_model)
        self.assertEqual(result.validation.get("mode"), "fallback")


if __name__ == "__main__":
    unittest.main()
