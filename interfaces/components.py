# interfaces/components.py
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align
from rich.text import Text
from rich.console import Group
from rich.rule import Rule
from rich.layout import Layout

from modules.client_mgr.client_model import Client, Account

from utils.charts import ChartRenderer

class UIComponents:
    """
    Pure UI Factory.
    Accepts Data -> Returns Rich Renderables.
    No input handling, API calls, or complex calculations allowed here.
    """

    @staticmethod
    def header(title: str, subtitle: str = "", breadcrumbs: str = "") -> Panel:
        """Standardized top-of-screen header."""
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            f"[bold gold1]{title}[/bold gold1]", 
            f"[dim]{breadcrumbs}[/dim]"
        )
        if subtitle:
            grid.add_row(f"[white]{subtitle}[/white]")
            
        return Panel(grid, style="on black", box=box.SQUARE)

    @staticmethod
    def client_list_table(clients: list, valuation_map: dict) -> Table:
        """Renders the main list of clients."""
        table = Table(title="[bold gold1]Clients[/bold gold1]", box=box.ROUNDED, expand=True)
        table.add_column("Client ID", style="dim", width=10)
        table.add_column("Name", style="bold white")
        table.add_column("Risk Profile", style="yellow")
        table.add_column("Total AUM", style="green", justify="right")
        table.add_column("Accts", style="dim", justify="right")

        for client in clients:
            total_val = valuation_map.get(client.client_id, 0.0)
            table.add_row(
                client.client_id[:8],
                client.name,
                client.risk_profile,
                f"${total_val:,.2f}",
                str(len(client.accounts))
            )
        return table

    @staticmethod
    def portfolio_summary_panel(market_val: float, manual_val: float, spark_data: list = None) -> Panel:
        """Dashboard panel showing Total AUM and a Sparkline."""
        combined = market_val + manual_val
        
        # Left Side: Numeric Breakdown
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim")
        grid.add_column(justify="right", style="bold white")
        
        grid.add_row("Market Assets", f"[bold green]${market_val:,.2f}[/bold green]")
        if manual_val > 0:
            grid.add_row("Off-Market", f"[bold magenta]${manual_val:,.2f}[/bold magenta]")
        grid.add_row(Rule(style="dim"))
        grid.add_row("Total Net Worth", f"[bold white]${combined:,.2f}[/bold white]")

        # Right Side: Sparkline Chart
        content = grid
        if spark_data:
            # Using your existing ChartRenderer
            sparkline = ChartRenderer.generate_sparkline(spark_data, length=30)
            
            chart_group = Group(
                Align.center(Text("Performance Trend", style="dim")),
                Align.center(sparkline)
            )
            
            layout = Table.grid(expand=True)
            layout.add_column(ratio=1)
            layout.add_column(ratio=1)
            layout.add_row(grid, chart_group)
            content = layout

        return Panel(content, title="[bold gold1]Portfolio Overview[/bold gold1]", box=box.HEAVY)

    @staticmethod
    def account_list_panel(client: Client, enriched_data: dict) -> Panel:
        """Table of accounts for the Client Dashboard."""
        table = Table(box=box.SIMPLE_HEAD, expand=True)
        table.add_column("Account Name")
        table.add_column("Type", style="cyan")
        table.add_column("Holdings", justify="center")
        table.add_column("Est. Value", justify="right", style="bold green")

        for acc in client.accounts:
            # Quick summation of enriched prices for this account
            val = sum(enriched_data.get(t, {}).get('price', 0) * q for t, q in acc.holdings.items())
            table.add_row(
                acc.account_name,
                acc.account_type,
                str(len(acc.holdings)),
                f"${val:,.2f}"
            )
            
        return Panel(table, title=f"[bold gold1]Accounts ({len(client.accounts)})[/bold gold1]", box=box.ROUNDED)

    @staticmethod
    def capm_metrics_panel(metrics: dict) -> Panel:
        """Compact CAPM/Risk display."""
        if not metrics or metrics.get('error'):
            return Panel("[dim]Insufficient data for risk models.[/dim]", title="Risk Metrics", border_style="dim")

        def _fmt(value: float, fmt: str, fallback: str = "N/A") -> str:
            return fallback if value is None else fmt.format(value)

        table = Table(box=box.SIMPLE, expand=True, show_header=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_column("Desc", style="dim italic")
        
        table.add_row("Beta", _fmt(metrics.get('beta'), "{:.2f}"), "Volatility vs Market")
        table.add_row("Alpha", _fmt(metrics.get('alpha_annual'), "{:+.2%}"), "Excess Return")
        table.add_row("Sharpe", _fmt(metrics.get('sharpe'), "{:.2f}"), "Risk-Adjusted")
        
        return Panel(table, title="[bold blue]Risk Profile (CAPM)[/bold blue]", box=box.ROUNDED)

    @staticmethod
    def holdings_table(account: Account, enriched_data: dict, total_val: float) -> Table:
        """Detailed holdings table with Lots and Trends."""
        table = Table(title="[bold gold1]Market Holdings[/bold gold1]", box=box.HEAVY, expand=True)
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Trend", justify="center", width=5)
        table.add_column("Quantity", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Market Value", style="green", justify="right")
        table.add_column("Alloc %", justify="right", style="dim")

        sorted_holdings = sorted(
            account.holdings.items(),
            key=lambda item: enriched_data.get(item[0], {}).get("market_value", 0),
            reverse=True,
        )

        for ticker, total_qty in sorted_holdings:
            data = enriched_data.get(ticker, {})
            lots = account.lots.get(ticker, [])

            mkt_val = float(data.get("market_value", 0.0) or 0.0)
            change_pct = float(data.get("change_pct", 0.0) or 0.0)

            # Calc Avg Cost
            avg_cost = 0.0
            if lots:
                total_cost = sum(float(l["qty"]) * float(l["basis"]) for l in lots)
                total_lot_qty = sum(float(l["qty"]) for l in lots)
                avg_cost = (total_cost / total_lot_qty) if total_lot_qty > 0 else 0.0

            trend = ChartRenderer.get_trend_arrow(change_pct)
            alloc_pct = (mkt_val / total_val * 100) if total_val > 0 else 0.0

            # Main Row
            table.add_row(
                ticker,
                trend,
                f"{total_qty:,.4f}",
                f"${avg_cost:,.2f}",
                f"${mkt_val:,.2f}",
                f"{alloc_pct:>.1f}%",
            )

            # Lot Sub-rows
            for i, lot in enumerate(lots, 1):
                table.add_row(
                    Text(f"  └─ Lot {i}", style="dim"),
                    "",
                    Text(f"{lot['qty']:,.4f}", style="dim", justify="right"),
                    Text(f"${lot['basis']:,.2f}", style="dim", justify="right"),
                    Text(lot.get("timestamp", "N/A"), style="dim"),
                    "",
                )
        return table

    @staticmethod
    def manual_assets_table(manual_holdings: list) -> Table:
        """Table for Off-Market Assets."""
        table = Table(title="[bold magenta]Off-Market Holdings[/bold magenta]", box=box.SIMPLE_HEAD, expand=True)
        table.add_column("#", style="dim", width=4)
        table.add_column("Asset", style="bold magenta")
        table.add_column("Est. Value", justify="right", style="magenta")
        table.add_column("Notes", style="dim")

        for i, item in enumerate(manual_holdings, 1):
            table.add_row(
                str(i),
                item.get("name", "Unknown"),
                f"${item.get('total_value', 0.0):,.2f}",
                item.get("notes", "")[:30]
            )
        return table

    @staticmethod
    def account_detail_overview(market_val: float, manual_val: float, spark_data: list) -> Panel:
        """Specific header panel for the Account-level dashboard."""
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        
        # Stats side
        stats = Table.grid(padding=(0, 1))
        stats.add_row("[dim]Market:[/dim]", f"[green]${market_val:,.2f}[/green]")
        stats.add_row("[dim]Manual:[/dim]", f"[magenta]${manual_val:,.2f}[/magenta]")
        
        # Chart side
        spark = ChartRenderer.generate_sparkline(spark_data, length=30)
        
        grid.add_row(stats, Align.right(Group(Text("Account Performance", style="dim size=8"), spark)))
        
        return Panel(grid, title="[bold gold1]Account Snapshot[/bold gold1]", border_style="cyan")

    @staticmethod
    def risk_profile_full_width(metrics: dict) -> Panel:
        """Detailed risk analysis panel with high-fidelity financial metrics."""
        if not metrics or metrics.get('error'):
            return Panel("[dim]Insufficient historical data for risk modeling.[/dim]", 
                            title="Risk & Volatility Analysis", border_style="dim")

        def _fmt(value: float, fmt: str, fallback: str = "N/A") -> str:
            return fallback if value is None else fmt.format(value)

        table = Table(box=box.SIMPLE, expand=True)
        table.add_column("Metric", style="bold cyan")
        table.add_column("Value", justify="right")
        table.add_column("Benchmark (SPY)", justify="right", style="dim")
        table.add_column("Interpretation", style="italic")

        # Extract values calculated from real historical series
        beta = metrics.get('beta', 1.0)
        alpha = metrics.get('alpha_annual', 0.0)
        r_sq = metrics.get('r_squared', 0.0)
        vol = metrics.get('vol_annual', metrics.get('volatility_annual', metrics.get('volatility', 0.0)))
        sharpe = metrics.get('sharpe', 0.0)

        table.add_row("Beta (Systemic Risk)", _fmt(beta, "{:.2f}"), "1.00", "Sensitivity to market moves")
        table.add_row("Alpha (Jensen's)", _fmt(alpha, "{:+.2%}"), "0.00%", "Excess return vs risk-adjusted")
        table.add_row("R-Squared", _fmt(r_sq, "{:.2f}"), "1.00", "Correlation/Reliability of Beta")
        table.add_row("Volatility (σ)", _fmt(vol, "{:.2%}"), "15%", "Annualized standard deviation")
        table.add_row("Sharpe Ratio", _fmt(sharpe, "{:.2f}"), "N/A", "Risk-adjusted return efficiency")

        return Panel(table, title="[bold gold1]Annualized Risk Profile[/bold gold1]", box=box.ROUNDED)
