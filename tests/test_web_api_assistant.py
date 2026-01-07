import os
from unittest import mock

from fastapi.testclient import TestClient

from web_api import app as web_app
from web_api import summarizer as assistant_summarizer
from web_api.routes import assistant as assistant_routes


def _api_headers():
    key = os.getenv("CLEAR_WEB_API_KEY")
    return {"X-API-Key": key} if key else {}


def test_assistant_summary_endpoint_uses_payload():
    client = TestClient(web_app.app)
    with mock.patch.object(assistant_routes, "summarize") as mocked:
        mocked.return_value = {
            "answer": "OK",
            "sources": [{"route": "/api/clients", "source": "database", "timestamp": 1}],
            "confidence": "Medium",
            "warnings": [],
        }
        resp = client.post(
            "/api/assistant/query",
            json={"question": "How many clients?"},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"] == "OK"
    args, _ = mocked.call_args
    assert args[0] == "How many clients?"
    assert args[1] is None


def test_assistant_non_summary_mode_is_explicit():
    client = TestClient(web_app.app)
    with mock.patch.object(assistant_routes, "summarize") as mocked:
        resp = client.post(
            "/api/assistant/query",
            json={"question": "Compare clients", "mode": "compare"},
            headers=_api_headers(),
        )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["answer"] == "Mode 'compare' is not yet implemented."
    mocked.assert_not_called()


def test_summarize_news_uses_context_and_sources():
    with mock.patch.object(assistant_summarizer, "get_news") as mocked:
        mocked.return_value = {
            "items": [{"title": "A"}],
            "cached": False,
            "stale": False,
            "skipped": [],
            "health": {},
        }
        result = assistant_summarizer.summarize(
            "latest news",
            {"region": "EU", "industry": "tech"},
            ["bbc.com"],
        )
    mocked.assert_called_with({"region": "EU", "industry": "tech"}, ["bbc.com"])
    assert result["confidence"] == "Medium"
    assert result["sources"]
    assert result["sources"][0]["route"] == "/api/intel/news"


def test_summarize_news_warns_when_empty():
    with mock.patch.object(assistant_summarizer, "get_news") as mocked:
        mocked.return_value = {
            "items": [],
            "cached": False,
            "stale": False,
            "skipped": [],
            "health": {},
        }
        result = assistant_summarizer.summarize("news", None, None)
    assert "News feed returned no items." in result["warnings"]
