from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_guardrails  # noqa: E402


def test_guardrail_scan_matches_baseline():
    findings = check_guardrails.collect_findings()
    baseline = check_guardrails.load_baseline()
    new_ids, missing_ids = check_guardrails.compare_to_baseline(findings, baseline)
    assert not new_ids, f"new guardrail findings: {new_ids}"
    assert not missing_ids, f"remove stale baseline ids: {missing_ids}"


def test_invented_confidence_literals_are_gone_from_tests():
    findings = [
        item
        for item in check_guardrails.collect_findings()
        if item.rule == "invented_confidence"
    ]
    assert findings == []
