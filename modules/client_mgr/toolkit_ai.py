from typing import Optional

from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from utils.report_synth import ReportSynthesizer, build_report_context, build_ai_sections


def render_ai_sections(sections: list) -> Optional[Group]:
    if not sections:
        return None
    panels = []
    for section in sections:
        title = str(section.get("title", "Advisor Notes"))
        rows = section.get("rows", []) or []
        if rows and isinstance(rows[0], list):
            table = Table.grid(padding=(0, 1))
            table.add_column(style="bold cyan", width=18)
            table.add_column(style="white")
            for row in rows:
                left = str(row[0]) if len(row) > 0 else ""
                right = str(row[1]) if len(row) > 1 else ""
                table.add_row(left, right)
            body = table
        else:
            text = Text()
            for row in rows:
                text.append(f"{row}\n")
            body = text
        panels.append(Panel(body, title=title, border_style="cyan"))
    return Group(*panels)


def build_ai_panel(ai_conf: dict, report: dict, report_type: str) -> Optional[Group]:
    if not bool(ai_conf.get("enabled", True)):
        return None
    synthesizer = ReportSynthesizer(
        provider=str(ai_conf.get("provider", "rule_based")),
        model_id=str(ai_conf.get("model_id", "rule_based_v1")),
        persona=str(ai_conf.get("persona", "advisor_legal_v1")),
        cache_file=str(ai_conf.get("cache_file", "data/ai_report_cache.json")),
        cache_ttl=int(ai_conf.get("cache_ttl", 21600)),
        endpoint=str(ai_conf.get("endpoint", "")),
    )
    context = build_report_context(
        report,
        report_type,
        region="Global",
        industry="portfolio",
        news_items=[],
    )
    ai_payload = synthesizer.synthesize(context)
    sections = build_ai_sections(ai_payload)
    return render_ai_sections(sections)
