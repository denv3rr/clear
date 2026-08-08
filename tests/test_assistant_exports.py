from modules.assistant_exports import (
    UNSUPPORTED_CONFIDENCE_WARNING,
    build_assistant_export,
    normalize_assistant_entry,
    render_assistant_export_markdown,
)


def test_normalize_assistant_entry_adds_warning_for_missing_sources():
    entry = normalize_assistant_entry({"question": "Q", "answer": "A"})
    assert entry["confidence"] is None
    assert entry["sources"] == []
    assert "No data sources were returned." in entry["warnings"]


def test_normalize_assistant_entry_strips_unsupported_confidence_labels():
    entry = normalize_assistant_entry(
        {
            "question": "Q",
            "answer": "A",
            "confidence": "Low",
            "sources": [{"route": "/api/clients", "source": "database"}],
        }
    )
    assert entry["confidence"] is None
    assert UNSUPPORTED_CONFIDENCE_WARNING in entry["warnings"]


def test_build_assistant_export_contains_lineage_and_markdown():
    history = [
        {
            "question": "Q",
            "answer": "A",
            "confidence": "Low",
            "sources": [{"route": "/api/clients", "source": "database", "timestamp": 1}],
        }
    ]
    export_payload = build_assistant_export(history, {"region": "Global"}, generated_by="test")
    assert export_payload["generated_by"] == "test"
    assert export_payload["lineage"][0]["route"] == "/api/clients"
    markdown = render_assistant_export_markdown(export_payload)
    assert "Assistant History Export" in markdown
    assert "Confidence:" not in markdown
    assert UNSUPPORTED_CONFIDENCE_WARNING in markdown
