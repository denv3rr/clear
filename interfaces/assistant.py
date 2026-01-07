from __future__ import annotations

from typing import Any, Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich import box

from interfaces.shell import ShellRenderer
from interfaces.menu_layout import build_sidebar, compact_for_width
from utils.input import InputSafe
from web_api.summarizer import summarize


class AssistantModule:
    def __init__(self) -> None:
        self.console = Console()
        self.history: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {
            "region": "Global",
            "industry": "all",
            "tickers": "",
            "sources": "",
            "client_id": "",
            "account_id": "",
        }

    def run(self) -> None:
        while True:
            choice = self._render_menu()
            if choice in ("0", "m"):
                return
            if choice == "x":
                return
            if choice == "1":
                self._ask_question()
            elif choice == "2":
                self._edit_context()
            elif choice == "3":
                self.history = []

    def _render_menu(self) -> str:
        options = {
            "1": "Ask a question",
            "2": "Edit context",
            "3": "Clear history",
            "0": "Back",
        }
        compact = compact_for_width(self.console.width)
        sidebar = build_sidebar(
            [("Assistant", options)],
            show_main=True,
            show_back=False,
            show_exit=True,
            compact=compact,
        )
        content = Group(self._history_panel(), self._context_panel())
        return ShellRenderer.render_and_prompt(
            content,
            context_actions=options,
            valid_choices=list(options.keys()) + ["m", "x"],
            prompt_label=">",
            show_main=False,
            show_back=False,
            show_exit=False,
            show_header=False,
            sidebar_override=sidebar,
        )

    def _history_panel(self) -> Panel:
        if not self.history:
            body = Text("No assistant responses yet.", style="dim")
        else:
            lines: List[str] = []
            for item in self.history[-5:]:
                lines.append(f"Q: {item.get('question', '')}")
                lines.append(f"A: {item.get('answer', '')}")
                confidence = item.get("confidence")
                if confidence:
                    lines.append(f"Confidence: {confidence}")
                sources = item.get("sources") or []
                if sources:
                    source_list = ", ".join(
                        f"{src.get('route', '')}" for src in sources
                    )
                    lines.append(f"Sources: {source_list}")
                warnings = item.get("warnings") or []
                if warnings:
                    lines.append(f"Warnings: {', '.join(warnings)}")
                lines.append("")
            body = Text("\n".join(lines).strip())
        return Panel(body, title="[bold]Assistant History[/bold]", box=box.ROUNDED)

    def _context_panel(self) -> Panel:
        lines = [
            f"Region: {self.context.get('region') or ''}",
            f"Industry: {self.context.get('industry') or ''}",
            f"Tickers: {self.context.get('tickers') or ''}",
            f"Sources: {self.context.get('sources') or ''}",
            f"Client ID: {self.context.get('client_id') or ''}",
            f"Account ID: {self.context.get('account_id') or ''}",
        ]
        body = Text("\n".join(lines))
        return Panel(body, title="[bold]Context[/bold]", box=box.SQUARE)

    def _ask_question(self) -> None:
        question = InputSafe.get_string("Ask Clear")
        if not question.strip():
            return
        sources = self._split_list(self.context.get("sources"))
        context = dict(self.context)
        context["tickers"] = self._split_list(self.context.get("tickers"))
        response = summarize(question, context, sources)
        self.history.append(
            {
                "question": question,
                "answer": response.get("answer"),
                "confidence": response.get("confidence"),
                "sources": response.get("sources"),
                "warnings": response.get("warnings"),
            }
        )
        InputSafe.pause("Press Enter to continue...")

    def _edit_context(self) -> None:
        self.context["region"] = self._prompt_context_value(
            "Region", self.context.get("region", "Global")
        )
        self.context["industry"] = self._prompt_context_value(
            "Industry", self.context.get("industry", "all")
        )
        self.context["tickers"] = self._prompt_context_value(
            "Tickers (comma-separated)", self.context.get("tickers", "")
        )
        self.context["sources"] = self._prompt_context_value(
            "Sources (comma-separated)", self.context.get("sources", "")
        )
        self.context["client_id"] = self._prompt_context_value(
            "Client ID", self.context.get("client_id", "")
        )
        self.context["account_id"] = self._prompt_context_value(
            "Account ID", self.context.get("account_id", "")
        )

    def _prompt_context_value(self, label: str, current: str) -> str:
        prompt = f"{label} [{current}]"
        value = InputSafe.get_string(prompt).strip()
        return value or current

    @staticmethod
    def _split_list(value: Optional[str]) -> Optional[List[str]]:
        if not value:
            return None
        items = [item.strip() for item in str(value).split(",") if item.strip()]
        return items or None
