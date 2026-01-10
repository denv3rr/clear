from typing import Dict

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich import box

from interfaces.shell import ShellRenderer
from modules.client_mgr.toolkit_models import ModelSelector


def prompt_menu(
    title: str,
    options: Dict[str, str],
    show_main: bool = True,
    show_back: bool = True,
    show_exit: bool = True,
) -> str:
    table = Table.grid(padding=(0, 1))
    table.add_column()
    for key, label in options.items():
        table.add_row(f"[bold cyan]{key}[/bold cyan]  {label}")
    panel = Panel(table, title=title, border_style="cyan", box=box.ROUNDED)
    return ShellRenderer.render_and_prompt(
        Group(panel),
        context_actions=options,
        valid_choices=list(options.keys()) + ["m", "x"],
        prompt_label=">",
        show_main=show_main,
        show_back=show_back,
        show_exit=show_exit,
        show_header=False,
    )


class ToolkitMenuMixin:
    def run(self) -> None:
        """Main loop for the Client Tools module."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.console.print(f"[bold gold1]TOOLS | {self.client.name}[/bold gold1]")

            recs = ModelSelector.analyze_suitability(self.client)
            if recs:
                self.console.print(
                    Panel(
                        "\n".join([f"• {r}" for r in recs]),
                        title="[bold green]Recommended Models[/bold green]",
                        border_style="green",
                        width=100,
                    )
                )

            self.console.print("\n[bold white]Quantitative Models[/bold white]")
            self.console.print("[1] CAPM Analysis (Alpha, Beta, R²)")
            self.console.print("[2] Black-Scholes Option Pricing")
            self.console.print("[3] Multi-Model Risk Dashboard")
            self.console.print("[4] Portfolio Regime Snapshot")
            self.console.print("[5] Portfolio Diagnostics")
            self.console.print("[6] Pattern Analysis")
            self.console.print(
                f"[7] Change Interval (Current: {self._selected_interval})"
            )
            self.console.print("[0] Return to Client Dashboard")

            choice = prompt_menu(
                "Tools Menu",
                {
                    "1": "CAPM Analysis (Alpha, Beta, R-squared)",
                    "2": "Black-Scholes Option Pricing",
                    "3": "Multi-Model Risk Dashboard",
                    "4": "Portfolio Regime Snapshot",
                    "5": "Portfolio Diagnostics",
                    "6": "Pattern Analysis",
                    "7": f"Change Interval (Current: {self._selected_interval})",
                    "0": "Return to Client Dashboard",
                },
            )

            if choice in ("0", "m"):
                break
            if choice == "x":
                return
            if choice == "1":
                self._run_capm_analysis()
            elif choice == "2":
                self._run_black_scholes()
            elif choice == "3":
                self._run_multi_model_dashboard()
            elif choice == "4":
                self._run_regime_snapshot()
            elif choice == "5":
                self._run_portfolio_diagnostics()
            elif choice == "6":
                self._run_pattern_suite()
            elif choice == "7":
                updated = self._get_interval_or_select(force=True)
                if updated:
                    self._selected_interval = updated
