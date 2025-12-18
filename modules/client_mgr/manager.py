from rich.console import Console
from rich.console import Group
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.align import Align
from rich.text import Text
from rich.rule import Rule

from typing import Optional, Tuple, List, Union

from utils.input import InputSafe
from utils.charts import ChartRenderer
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.data_handler import DataHandler
from modules.client_mgr.valuation import ValuationEngine
from modules.client_mgr.toolkit import FinancialToolkit
from modules.client_mgr.toolkit import RegimeModels, RegimeRenderer

# Maps active_interval to the number of points we render on the sparkline
INTERVAL_POINTS = {
    "1W": 40,   # Increased point count for hourly data
    "1M": 22,
    "3M": 66,
    "6M": 132,
    "1Y": 252,
}

# Maps active_interval to the lookback period requested from Yahoo
HISTORY_PERIOD = {
    "1W": "5d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1Y": "1y",
}

# Maps active_interval to the data granularity
# CRITICAL: 1W needs 60m data to have enough points for Regime/Volatility math
HISTORY_INTERVAL_MAP = {
    "1W": "60m", 
    "1M": "1d",
    "3M": "1d",
    "6M": "1d",
    "1Y": "1d",
}

CAPM_PERIOD = {
    "1W": "1mo",
    "1M": "6mo",
    "3M": "1y",
    "6M": "2y",
    "1Y": "5y",
}

class ClientManager:
    """
    Manages client creation, portfolio viewing, and account/holding modification.
    """
    def __init__(self):
        self.console = Console()
        self.clients: List[Client] = DataHandler.load_clients()
        self.valuation_engine = ValuationEngine()

    # --- CORE BUSINESS/UTILITY LOGIC ---

    def _recalculate_account_value(self, account: Account) -> float:
        """
        Recalculates account value using the ValuationEngine and updates 
        the account's current_value field in place.
        """
        # Default to 1M/1d for simple list view totals
        total_value, _ = self.valuation_engine.calculate_portfolio_value(
            account.holdings,
            history_period="1mo",
            history_interval="1d"
        )
        account.current_value = total_value
        return total_value

    def _get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Looks up a client by ID from the in-memory list."""
        if not client_id: return None
        return next((c for c in self.clients if c.client_id.startswith(client_id)), None)

    # --- MAIN VIEW ---

    def run(self):
        """Main loop for the Client Management Module."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.display_client_list()

            self.console.print("\n[bold gold1]CLIENT MANAGER ACTIONS:[/bold gold1]")
            self.console.print("[1] ➕ Add New Client")
            self.console.print("[2] 📝 Select Client (by ID)")
            self.console.print("[3] 🗑️ Delete Client (by ID) [bold red]![/bold red]")
            self.console.print("[0] 🔙 Return to Main Menu")
            
            choice = InputSafe.get_option(["1", "2", "3", "0"], prompt_text="[>]")
            
            if choice == "0":
                DataHandler.save_clients(self.clients)
                self.console.clear()
                print("\x1b[3J", end="")
                break
            elif choice == "1":
                self.add_client_workflow()
            elif choice == "2":
                self.select_client_workflow()
            elif choice == "3":
                self.delete_client_workflow()

    # --- CLIENT LIST VIEW ---
    
    def display_client_list(self):
        """Renders the list of current clients with summary data."""
        table = Table(title="[bold gold1]Clients[/bold gold1]", box=box.ROUNDED, expand=True)
        table.add_column("Client ID", style="dim", width=10)
        table.add_column("Name", style="bold white")
        table.add_column("Risk Profile", style="yellow")
        table.add_column("Total AUM", style="green", justify="right")
        table.add_column("Accts", style="dim", justify="right")
        
        for client in self.clients:
            # Recalculate all accounts and sum for the total client value shown in the list
            total_value = sum(self._recalculate_account_value(acc) for acc in client.accounts)
            
            table.add_row(
                client.client_id[:8],
                client.name,
                client.risk_profile,
                f"${total_value:,.2f}",
                str(len(client.accounts))
            )

        self.console.print(table)

    # --- CLIENT DASHBOARD VIEW ---
    
    def _build_client_details_panel(self, client: Client) -> Panel:
        details_grid = Table.grid(padding=(0,2))
        details_grid.add_column(style="bold yellow")
        details_grid.add_column(style="white")
        details_grid.add_row("Client ID:", client.client_id)
        details_grid.add_row("Name:", client.name)
        details_grid.add_row("Risk Profile:", client.risk_profile)
        
        return Panel(details_grid, title="[bold blue]CLIENT DETAILS[/bold blue]", box=box.ROUNDED, width=100)

    def display_client_dashboard(self, client: Client):
        """Composes and displays the client's main dashboard with CHARTS."""

        interval = getattr(client, "active_interval", "1M")
                
        # 1. Aggregate Holdings for Global View
        all_holdings = {}
        for acc in client.accounts:
            for t, q in acc.holdings.items():
                all_holdings[t] = all_holdings.get(t, 0) + q

        # 2. Fetch Data (Threaded) with CORRECT granularity
        hp = HISTORY_PERIOD.get(interval, "1mo")
        hi = HISTORY_INTERVAL_MAP.get(interval, "1d")

        total_val, enriched_data = self.valuation_engine.calculate_portfolio_value(
            all_holdings,
            history_period=hp,
            history_interval=hi,
        )
        
        # 3. Generate Portfolio History Chart
        port_history = self.valuation_engine.generate_synthetic_portfolio_history(
            enriched_data,
            all_holdings,
            interval=interval
        )
        
        n_points = INTERVAL_POINTS.get(interval, 22)
        # Right-aligned slicing provided by valuation logic, safe-guard view here
        port_series = port_history[-n_points:] if port_history else []
        render_n = min(n_points, len(port_series)) if port_series else 0
        
        port_sparkline = ChartRenderer.generate_sparkline(port_series, length=render_n) if render_n > 0 else Text("N/A", style="dim")
        
        # --- RENDER UI ---
        
        # Header Area
        title_grid = Table.grid(expand=True)
        title_grid.add_column(justify="left")
        title_grid.add_column(justify="right")
        title_grid.add_row(
            f"[bold gold1]CLIENT:[/bold gold1] {client.name}",
            f"[dim]ID: {client.client_id}[/dim]"
        )
        title_grid.add_row(f"[bold gold1]Active Accounts:[/bold gold1] {len(client.accounts)}")
        title_grid.add_row(f"[bold gold1]Interval:[/bold gold1] [bold white]([/bold white][bold green]{interval}[/bold green][bold white])[/bold white]")
        self.console.print(Panel(title_grid, style="on black", box=box.SQUARE))

        # AUM & Chart Panel
        aum_text = Text(f"${total_val:,.2f}", style="bold green" if total_val > 0 else "white")
        aum_panel = Panel(
            (
                Text.assemble("TOTAL AUM\n", aum_text, "\n\n", port_sparkline)
            ),
            box=box.HEAVY,
            border_style="green",
            title=f"[bold gold1]Portfolio Performance ([bold green]{interval}[/bold green])[/bold gold1]"
        )
        self.console.print(aum_panel)

        # --- Manual / Off-Market totals ---
        manual_total = 0.0
        manual_count = 0
        for acc in client.accounts:
            mh = getattr(acc, "manual_holdings", []) or []
            manual_count += len(mh)
            mt, _ = self.valuation_engine.calculate_manual_holdings_value(mh)
            manual_total += mt

        combined_total = float(total_val) + float(manual_total)

        aum_grid = Table.grid(padding=(0, 2))
        aum_grid.add_column(style="dim")
        aum_grid.add_column(justify="right", style="bold white")
        aum_grid.add_row("Market-Priced AUM", f"[bold green]${total_val:,.2f}[/bold green]")
        if manual_count > 0:
            aum_grid.add_row("Off-Market", f"[bold magenta]${manual_total:,.2f}[/bold magenta]")
            aum_grid.add_row("Combined (Est.)", f"[bold white]${combined_total:,.2f}[/bold white]")

        self.console.print(Panel(Align.left(aum_grid), title="[bold gold1]Total AUM[/bold gold1]", box=box.HEAVY))

        # --- CAPM Snapshot (market holdings only) ---
        capm_period = CAPM_PERIOD.get(interval, "1y")
        capm = FinancialToolkit.compute_capm_metrics_from_holdings(all_holdings, benchmark_ticker="SPY", period=capm_period)

        capm_table = Table(box=box.SIMPLE_HEAD, expand=True)
        capm_table.add_column("Metric", style="bold")
        capm_table.add_column("Value", justify="right")
        capm_table.add_column("Notes", style="dim")

        if capm.get("error"):
            capm_table.add_row("CAPM", "[yellow]N/A[/yellow]", str(capm.get("error")))
        else:
            capm_table.add_row("Beta", f"{capm.get('beta', 0.0):.2f}", f"vs {capm.get('benchmark','SPY')}")
            capm_table.add_row("Alpha (Annual)", f"{capm.get('alpha_annual', 0.0):+.2%}", "Excess return vs. risk taken")
            capm_table.add_row("R-Squared", f"{capm.get('r_squared', 0.0):.2f}", "Correlation strength to benchmark")
            capm_table.add_row("Sharpe (Est.)", f"{capm.get('sharpe', 0.0):.2f}", "Risk-adjusted return (approx.)")
            capm_table.add_row("Volatility (Annual)", f"{capm.get('vol_annual', 0.0):.2%}", "Annualized stdev of portfolio returns")

        self.console.print(Panel(capm_table, title="[bold gold1]CAPM & Risk Snapshot (Market Holdings Only)[/bold gold1]", box=box.HEAVY))

        # Regime Models
        # (derived from portfolio history)
        returns = []
        if port_history and len(port_history) >= 8:
            for i in range(1, len(port_history)):
                prev = port_history[i - 1]
                curr = port_history[i]
                if prev > 0:
                    returns.append((curr - prev) / prev)

        if returns and len(returns) >= 8:
            snapshot = RegimeModels.snapshot_from_value_series(
                port_series,
                interval=interval,
                label="Portfolio"
            )
            panel = RegimeRenderer.render(snapshot)
            self.console.print(panel)
        else:
            self.console.print(
                Panel(
                    "[dim]Insufficient portfolio history for regime analysis.[/dim]",
                    title="[bold]Market Regime[/bold]",
                    border_style="dim"
                )
            )

        # Account Breakdown Table
        acc_table = Table(box=box.SIMPLE_HEAD, expand=True)
        acc_table.add_column("Account")
        acc_table.add_column("Type")
        acc_table.add_column("Holdings")
        acc_table.add_column("Est. Value", justify="right")
        
        for acc in client.accounts:
            # Quick local calc, reusing enriched prices
            acc_val = sum(enriched_data.get(t, {}).get('price', 0) * q for t, q in acc.holdings.items())
            acc_table.add_row(
                acc.account_name,
                acc.account_type,
                str(len(acc.holdings)),
                f"[bold green]${acc_val:,.2f}[/bold green]"
            )
        self.console.print(Panel(acc_table, title=f"[bold gold1]All Client Accounts[/bold gold1] [bold white]|[/bold white] [bold gold1]{client.name}[/bold gold1]", box=box.HEAVY))
        self.console.print("")
        self.console.rule()

    # --- WORKFLOWS ---

    def select_client_workflow(self):
        client_id_input = self.console.input("[bold cyan]Enter Client ID (partial match allowed):[/bold cyan] ").strip()
        client = self._get_client_by_id(client_id_input)
        
        if client:
            self.client_dashboard_loop(client)
        else:
            self.console.print(f"[red]Error: Client with ID starting '{client_id_input}' not found.[/red]")
            InputSafe.pause()

    def client_dashboard_loop(self, client: Client):
        """Displays a specific client's portfolio dashboard and manages client actions."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            self.display_client_dashboard(client)
            
            self.console.print(f"\n[bold gold1]CLIENT OPTIONS | {client.name}[/bold gold1]")
            self.console.print("[1] 📝 Edit Client Profile")
            self.console.print("[2] 💰 Manage Accounts & Holdings")
            self.console.print("[3] 🛠️ Tools (Models & Analysis)")
            self.console.print("[4] ⏱  Change Interval (portfolio-wide)")
            self.console.print("[0] 🔙 Return to Client List")
            
            choice = InputSafe.get_option(["1", "2", "3", "4", "0"], prompt_text="[>]")
            
            if choice == "0":
                DataHandler.save_clients(self.clients)
                break
            elif choice == "1":
                self.edit_client_workflow(client)
            elif choice == "2":
                self.manage_accounts_workflow(client)
            elif choice == "3":
                toolkit = FinancialToolkit(client)
                toolkit.run()
            elif choice == "4":
                self._change_interval_workflow(client)
                
    # --- ACCOUNT MANAGEMENT ---
    
    def _select_account_action(self, client: Client) -> Tuple[str, Union[Account, None]]:
        """
        Displays accounts and returns the user's INTENT.
        Returns: (Action_String, Account_Object_or_None)
        """
        options = []
        
        self.console.print(f"\n[bold gold1]MANAGE ACCOUNTS | {client.name}[/bold gold1]")
        
        # Show accounts with selection indices
        account_table = Table(box=box.SIMPLE, show_header=True, expand=True)
        account_table.add_column("#", style="bold yellow", width=4)
        account_table.add_column("Account Name", style="white")
        account_table.add_column("Type", style="cyan")
        account_table.add_column("Value", justify="right", style="green")
        
        total_val = 0.0
        for i, acc in enumerate(client.accounts, 1):
            val = self._recalculate_account_value(acc)
            total_val += val
            options.append(str(i))
            account_table.add_row(
                str(i),
                acc.account_name,
                acc.account_type,
                f"${val:,.2f}"
            )
        
        # Add Total Row
        account_table.add_row("", "[dim]Total[/dim]", "", f"[bold green]${total_val:,.2f}[/bold green]")
        
        self.console.print(f"[dim]Total Accounts: {len(client.accounts)}[/dim]")
        self.console.print(account_table)
        self.console.print(Align.right("[dim]Note: Market totals exclude off-market assets.[/dim]"))

        self.console.print("\n[bold gold1]MENU[/bold gold1]")
        self.console.print(f"[A] ➕ Add New Account")
        self.console.print(f"[R] ➖ Remove Account")
        self.console.print("[0] 🔙 Return to Client Dashboard")
        self.console.print("[dim]Or enter account number #[/dim]")

        # We need case insensitive matching for A and R
        choice = self.console.input("[bold cyan][>][/bold cyan] ").strip().upper()
        
        if choice == '0':
            return "BACK", None
        elif choice == 'A':
            return "ADD", None
        elif choice == 'R':
            return "REMOVE", None
        elif choice in options:
            idx = int(choice) - 1
            return "SELECT", client.accounts[idx]
        else:
            self.console.print("[red]Invalid selection.[/red]")
            InputSafe.pause()
            return "INVALID", None

    def manage_accounts_workflow(self, client: Client):
        """Controller for the Accounts screen."""
        while True:
            self.console.clear()
            print("\x1b[3J", end="")
            action, account = self._select_account_action(client)
            
            if action == "BACK":
                break
            elif action == "ADD":
                self.add_account_workflow(client)
            elif action == "REMOVE":
                self.remove_account_workflow(client)
            elif action == "SELECT" and account:
                self.manage_holdings_loop(client, account)

    def manage_holdings_loop(self, client: Client, account: Account):
        """Dedicated loop for managing holdings for a single selected account."""

        while True:
            interval = getattr(client, "active_interval", getattr(account, "active_interval", "1M"))

            # Ensure this account stays synced to the page-wide interval
            account.active_interval = interval

            self.console.clear()
            print("\x1b[3J", end="")

            # Header Area
            title_grid = Table.grid(expand=True)
            title_grid.add_column(justify="left")
            title_grid.add_column(justify="right")
            title_grid.add_row(
                f"[bold gold1]ACCOUNT DASHBOARD[/bold gold1] [bold white]|[/bold white] [bold gold1]([/bold gold1]{account.account_name}[bold gold1])[/bold gold1] [bold white]|[/bold white] [bold gold1]([/bold gold1]{account.account_type}[bold gold1])[/bold gold1]"
            )
            title_grid.add_row(Rule(style="bold white"))
            title_grid.add_row(f"[bold gold1]CLIENT:[/bold gold1] {client.name}", f"[dim]ID: {client.client_id}[/dim]")
            title_grid.add_row(f"[bold gold1]Interval:[/bold gold1] [bold white]([/bold white][bold green]{interval}[/bold green][bold white])[/bold white]")
            self.console.print(Panel(title_grid, style="on black", box=box.SQUARE))

            # ============================================================
            # ACCOUNT SNAPSHOT (LEFT) + VALUE OVER TIME (RIGHT)
            # ============================================================

            # --- Market valuation for this account ---
            hp = HISTORY_PERIOD.get(interval, "1mo")
            hi = HISTORY_INTERVAL_MAP.get(interval, "1d")

            acc_market_value, acc_enriched = self.valuation_engine.calculate_portfolio_value(
                account.holdings,
                history_period=hp,
                history_interval=hi,
            )

            # --- Manual / off-market valuation ---
            manual_total, _ = self.valuation_engine.calculate_manual_holdings_value(
                account.manual_holdings or []
            )

            combined_total = acc_market_value + manual_total

            # --- CAPM metrics (market holdings only) ---
            capm_period = CAPM_PERIOD.get(interval, "1y")
            capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                account.holdings,
                benchmark_ticker="SPY",
                period=capm_period
            )

            # ---------------- LEFT SIDE: Snapshot data ----------------
            snapshot = Table.grid(padding=(0, 2))
            snapshot.add_column(style="dim", justify="left")
            snapshot.add_column(justify="right", style="bold white")

            snapshot.add_row(
                "Market Value",
                f"[bold green]${acc_market_value:,.2f}[/bold green]"
            )

            if manual_total > 0:
                snapshot.add_row(
                    "Manual (Est.)",
                    f"[bold magenta]${manual_total:,.2f}[/bold magenta]"
                )
                snapshot.add_row(
                    "Combined (Est.)",
                    f"[bold white]${combined_total:,.2f}[/bold white]"
                )

            # --- CAPM values (preserved exactly) ---
            if not capm.get("error"):
                snapshot.add_row("Beta", f"{capm.get('beta', 0.0):.2f}")
                snapshot.add_row("Alpha (Ann.)", f"{capm.get('alpha_annual', 0.0):+.2%}")
                snapshot.add_row("R²", f"{capm.get('r_squared', 0.0):.2f}")

            note = Text(
                "Note: Market valuation & CAPM exclude off-market assets.",
                style="dim"
            )

            left_panel = Panel(
                Group(snapshot, Text(""), note),
                title="[bold]Account Snapshot[/bold]",
                box=box.HEAVY
            )

            # ---------------- RIGHT SIDE: Value-over-time chart ----------------

            acc_history = self.valuation_engine.generate_synthetic_portfolio_history(
                acc_enriched,
                account.holdings,
                interval=interval
            )

            chart_body = Text("No historical data available.", style="dim")

            if acc_history and len(acc_history) >= 3:
                interval_points = INTERVAL_POINTS.get(interval, 22)

                # Keep interval semantics, but cap the rendered width to avoid terminal overflow
                MAX_RENDER_POINTS = 48
                render_points = interval_points if interval_points <= MAX_RENDER_POINTS else MAX_RENDER_POINTS

                series = acc_history[-render_points:]

                spark = ChartRenderer.generate_sparkline(
                    series,
                    length=render_points
                )

                start_val = series[0]
                end_val = series[-1]

                pct = ((end_val - start_val) / start_val) * 100 if start_val != 0 else 0.0
                pct_style = "bold green" if pct >= 0 else "bold red"

                chart_body = Group(
                    Align.center(spark),
                    Align.center(
                        Text(
                            f"\nStart: ${start_val:,.2f}   "
                            f"End: ${end_val:,.2f}   "
                            f"({pct:+.2f}%)",
                            style=pct_style
                        )
                    )
                )

            right_panel = Panel(
                chart_body,
                title=f"[bold]Account Value Over Time [bold white]([/bold white][bold green]{interval}[/bold green][bold white])[/bold white][/bold]",
                box=box.HEAVY,
                padding=(3, 2),
            )

            # ---------------- COMBINED LAYOUT ----------------
            layout = Table.grid(expand=True)
            layout.add_column(ratio=2)
            layout.add_column(ratio=3)

            layout.add_row(left_panel, right_panel)

            self.console.print(layout)

            # Regime History (Sub-accounts)
            returns = []
            history_for_regime = acc_history[-(INTERVAL_POINTS.get(interval, 22) + 1):]
            if history_for_regime and len(history_for_regime) >= 2:
                for i in range(1, len(history_for_regime)):
                    prev = history_for_regime[i - 1]
                    curr = history_for_regime[i]
                    if prev > 0:
                        returns.append((curr - prev) / prev)

            if len(returns) >= 8:
                snapshot = RegimeModels.compute_markov_snapshot(
                    returns,
                    horizon=1,
                    label="Account"
                )
                self.console.print(RegimeRenderer.render(snapshot))
            # End Regime History ------------
            
            # Data Display
            self.display_account_holdings(account)

            self.console.print("\n[bold gold1]ACCOUNT ACTIONS:[/bold gold1]")
            self.console.print("[1] ➕ Add/Update Holding (Ticker & Qty)")
            self.console.print("[2] ➖ Remove Holding")
            self.console.print("[3] 📝 Edit Account Details")
            self.console.print("[4] ⏱  Change Interval (portfolio-wide)")
            self.console.print("[0] 🔙 Return to Accounts")
            
            choice = InputSafe.get_option(["1", "2", "3", "4", "0"], prompt_text="[>]")

            if choice == "0":
                break
            elif choice == "1":
                self.add_holding_workflow(account)
            elif choice == "2":
                self.remove_holding_workflow(account)
            elif choice == "3":
                self.edit_account_workflow(account)
            elif choice == "4":
                self._change_interval_workflow(client)

    # --- HOLDINGS & DETAILS LOGIC ---

    def display_account_holdings(self, account: Account):
        """Renders the detailed holdings with robust pricing and trend data."""
        
        # Get enriched data from ValuationEngine
        interval = getattr(account, "active_interval", "1M")
        hp = HISTORY_PERIOD.get(interval, "1mo")
        hi = HISTORY_INTERVAL_MAP.get(interval, "1d")

        total_val, enriched_data = self.valuation_engine.calculate_portfolio_value(
            account.holdings,
            history_period=hp,
            history_interval=hi,
        )
        
        # --- Generate account value history ---
        acc_history = self.valuation_engine.generate_synthetic_portfolio_history(
            enriched_data,
            account.holdings,
            interval=interval
        )

        # --- Account value-over-time chart (interval-driven) ---
        chart_body = Text("No history available.", style="dim")

        if acc_history and len(acc_history) >= 2:
            interval_points = INTERVAL_POINTS.get(interval, 22)

            # Cap render width for terminal safety
            MAX_RENDER_POINTS = 48
            render_points = interval_points if interval_points <= MAX_RENDER_POINTS else MAX_RENDER_POINTS

            series = acc_history[-render_points:]
            sparkline = ChartRenderer.generate_sparkline(series, length=render_points)

            start_val = series[0]
            end_val = series[-1]

            pct = ((end_val - start_val) / start_val) * 100 if start_val != 0 else 0.0
            pct_style = "bold green" if pct >= 0 else "bold red"

            chart_body = Group(
                Align.center(sparkline),
                Align.center(
                    Text(
                        f"\nStart: ${start_val:,.2f}   "
                        f"End: ${end_val:,.2f}   "
                        f"({pct:+.2f}%)",
                        style=pct_style
                    )
                )
            )

        self.console.print(
            Panel(
                chart_body,
                title=f"[bold]Account Value Over Time [/bold] [bold white]([/bold white][bold green]{interval}[/bold green][bold white])[/bold white]",
                box=box.HEAVY,
                padding=(1, 2),
            )
        )
        
        self.console.print("\n")
        table = Table(title=f"[bold gold1]Market Holdings[/bold gold1]", box=box.HEAVY, expand=True)
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Trend", justify="center", width=5)
        table.add_column("Quantity", justify="right")
        table.add_column("Price/Share", justify="right")
        table.add_column("Market Value", style="green", justify="right")
        table.add_column("Alloc %", justify="right", style="dim")

        # Sort holdings by value descending
        sorted_holdings = sorted(
            account.holdings.items(), 
            key=lambda item: enriched_data.get(item[0], {}).get('market_value', 0), 
            reverse=True
        )

        for ticker, quantity in sorted_holdings:
            data = enriched_data.get(ticker, {})
            mkt_val = data.get('market_value', 0.0)
            price = data.get('price', 0.0)
            change_pct = data.get('change_pct', 0.0)
            
            # Determine Trend Arrow
            if change_pct > 0:
                trend = Text("▲", style="bold green")
            elif change_pct < 0:
                trend = Text("▼", style="bold red")
            else:
                trend = Text("-", style="dim")

            # Calculate allocation percentage
            alloc_pct = (mkt_val / total_val * 100) if total_val > 0 else 0.0
            
            table.add_row(
                ticker,
                trend,
                f"{quantity:,.4f}",
                f"${price:,.2f}",
                f"${mkt_val:,.2f}",
                f"{alloc_pct:>.1f}%"
            )

        self.console.print(table)

        # --- Manual holdings list (estimated) ---
        manual_total, manual_norm = self.valuation_engine.calculate_manual_holdings_value(
            getattr(account, "manual_holdings", []) or []
        )

        if manual_norm:
            mtable = Table(
                title="[bold magenta]Off-Market Holdings[/bold magenta]",
                box=box.HEAVY,
                expand=True
            )
            mtable.add_column("#", style="dim", justify="right", width=4)
            mtable.add_column("Asset", style="bold magenta")
            mtable.add_column("Quantity", justify="right")
            mtable.add_column("Unit", justify="right")
            mtable.add_column("Est. Value", justify="right", style="magenta")
            mtable.add_column("Notes", style="dim")

            i = 1
            for e in manual_norm:
                mtable.add_row(
                    str(i),
                    str(e.get("name", "")),
                    f"{float(e.get('quantity', 0.0) or 0.0):,.4f}",
                    f"${float(e.get('unit_price', 0.0) or 0.0):,.2f}",
                    f"${float(e.get('total_value', 0.0) or 0.0):,.2f}",
                    str(e.get("notes", ""))[:60],
                )
                i += 1

            self.console.print(mtable)

        combined_total = total_val + manual_total

        # --- Summary footer (two-track valuation) ---
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="dim")
        summary.add_column(justify="right", style="bold white")
        summary.add_row("Market-Priced Total", f"[bold green]${total_val:,.2f}[/bold green]")

        if manual_total > 0:
            summary.add_row("Off-Market Total", f"[bold magenta]${manual_total:,.2f}[/bold magenta]")
            summary.add_row("Combined", f"${combined_total:,.2f}")

        total_line = Text.assemble(
            ("Total Account Value: ", "bold white"),
            (f"${combined_total:,.2f}", "bold green"),
        )

        note_line = Text("Note: Market totals exclude off-market assets.", style="dim")

        # Right-align each line inside the panel
        footer_content = Group(
            Align.right(summary),
            Text(""),
            Align.right(total_line),
            Align.right(note_line),
        )

        footer_panel = Panel.fit(
            footer_content,
            box=box.HEAVY,
            border_style="white",
            padding=(0, 2),
        )

        # Right-align the whole panel on the console as well
        self.console.print(Align.right(footer_panel))

    def add_holding_workflow(self, account: Account):
        """Adds or updates a priced holding OR a manual/off-market asset without terminating the program."""

        self.console.print("\n[dim]Enter Ticker alone OR 'Ticker Quantity' (e.g. 'NVDA 10').[/dim]")
        self.console.print("[dim]Type 'MANUAL' to add an off-market asset (estimated value).[/dim]")

        raw_input = ""
        try:
            raw_input = (self.console.input("[bold cyan]Ticker Input:[/bold cyan] ") or "").strip()
        except Exception:
            raw_input = ""

        if not raw_input:
            InputSafe.pause()
            return

        if raw_input.strip().lower() in ("manual", "m", "off", "offmarket", "off-market"):
            self._add_manual_holding_workflow(account)
            InputSafe.pause()
            return

        # Parse "TICKER [QTY]"
        parts = raw_input.split()
        ticker = parts[0].strip().upper()
        quantity = None

        if len(parts) >= 2:
            try:
                quantity = float(parts[1])
            except Exception:
                self.console.print(f"[red]Could not parse quantity '{parts[1]}'.[/red]")
                InputSafe.pause()
                return

        # Quote feedback (never raises; always returns dict)
        quote = self.valuation_engine.get_quote_data(ticker)
        price = float(quote.get("price", 0.0) or 0.0)
        trend = float(quote.get("change_pct", quote.get("pct", 0.0)) or 0.0)
        if price > 0:
            self.console.print(f"   [dim]Price: ${price:,.2f} | Trend: {trend:+.2f}% | Source: {quote.get('source','N/A')}[/dim]")
        else:
            err = quote.get("error", "") or "Could not fetch live price."
            self.console.print(f"   [yellow]Warning: {err}[/yellow]")
            self.console.print("   [dim]You can still store the ticker + qty; valuation will show $0 until pricing is available.[/dim]")

        # Prompt for quantity if needed
        if quantity is None:
            qty_str = ""
            try:
                qty_str = (self.console.input(f"[bold cyan]Quantity for {ticker}:[/bold cyan] ") or "").strip()
            except Exception:
                qty_str = ""

            if not qty_str:
                InputSafe.pause()
                return

            try:
                quantity = float(qty_str)
            except Exception:
                self.console.print("[red]Invalid quantity.[/red]")
                InputSafe.pause()
                return

        if quantity < 0:
            self.console.print("[red]Quantity cannot be negative.[/red]")
            InputSafe.pause()
            return

        account.holdings[ticker] = float(quantity)
        self.console.print(f"[green]Successfully set {ticker} to {quantity:,.4f} shares.[/green]")

        try:
            DataHandler.save_clients(self.clients)  # Auto-save
        except Exception as ex:
            self.console.print(f"[red]Warning: Could not auto-save client data: {ex}[/red]")

        InputSafe.pause()

    def _add_manual_holding_workflow(self, account: Account):
        """Adds or updates an off-market/manual asset (estimated value)."""

        try:
            name = (self.console.input("\n[bold magenta]Manual Asset Name:[/bold magenta] ") or "").strip()
        except Exception:
            name = ""

        if not name:
            self.console.print("[yellow]No name entered; cancelled.[/yellow]")
            return

        # Quantity (optional; defaults to 1.0)
        qty = 1.0
        try:
            qty_raw = (self.console.input("[bold magenta]Quantity/Units (default 1):[/bold magenta] ") or "").strip()
            if qty_raw:
                qty = float(qty_raw)
        except Exception:
            qty = 1.0

        if qty < 0:
            self.console.print("[red]Quantity cannot be negative.[/red]")
            return

        # Choose valuation input method
        self.console.print("\n[bold magenta]Valuation Input:[/bold magenta]")
        self.console.print("[1] Enter Unit Price (qty × unit)")
        self.console.print("[2] Enter Total Value (override)")
        self.console.print("[0] Cancel")

        choice = InputSafe.get_option(["1", "2", "0"], prompt_text="[>]")
        if choice == "0":
            return

        unit_price = 0.0
        total_value = 0.0

        if choice == "1":
            try:
                unit_raw = (self.console.input("[bold magenta]Unit Price ($):[/bold magenta] ") or "").strip()
                unit_price = float(unit_raw) if unit_raw else 0.0
            except Exception:
                unit_price = 0.0
            total_value = unit_price * qty
        else:
            try:
                tot_raw = (self.console.input("[bold magenta]Total Estimated Value ($):[/bold magenta] ") or "").strip()
                total_value = float(tot_raw) if tot_raw else 0.0
            except Exception:
                total_value = 0.0
            unit_price = (total_value / qty) if qty > 0 else 0.0

        try:
            notes = (self.console.input("[dim]Notes (optional): [/dim]") or "").strip()
        except Exception:
            notes = ""

        entry = {
            "name": name,
            "quantity": float(qty),
            "unit_price": float(unit_price),
            "total_value": float(total_value),
            "currency": "USD",
            "notes": notes,
        }

        # Upsert by name (case-insensitive)
        manual_list = getattr(account, "manual_holdings", None)
        if manual_list is None:
            account.manual_holdings = []
            manual_list = account.manual_holdings

        idx = 0
        found = -1
        while idx < len(manual_list):
            try:
                if str(manual_list[idx].get("name", "")).strip().lower() == name.strip().lower():
                    found = idx
                    break
            except Exception:
                pass
            idx += 1

        if found >= 0:
            manual_list[found] = entry
            self.console.print(f"[green]Updated manual asset '{name}'.[/green]")
        else:
            manual_list.append(entry)
            self.console.print(f"[green]Added manual asset '{name}'.[/green]")

        try:
            DataHandler.save_clients(self.clients)
        except Exception as ex:
            self.console.print(f"[red]Warning: Could not auto-save client data: {ex}[/red]")

    def remove_holding_workflow(self, account: Account):
        """Removes a priced holding, or a manual/off-market asset."""

        self.console.print("\n[dim]Enter a ticker to remove, or type 'MANUAL' to remove an off-market asset.[/dim]")
        try:
            raw = (self.console.input("[bold cyan]Remove:[/bold cyan] ") or "").strip()
        except Exception:
            raw = ""

        if not raw:
            InputSafe.pause()
            return

        if raw.strip().lower() in ("manual", "m"):
            manual_list = getattr(account, "manual_holdings", []) or []
            if not manual_list:
                self.console.print("[yellow]No manual assets on this account.[/yellow]")
                InputSafe.pause()
                return

            manual_total, manual_norm = self.valuation_engine.calculate_manual_holdings_value(manual_list)

            table = Table(title="[bold magenta]Manual Assets[/bold magenta]", box=box.SIMPLE_HEAD, expand=True)
            table.add_column("#", style="dim", width=4, justify="right")
            table.add_column("Asset", style="bold magenta")
            table.add_column("Est. Value", justify="right", style="magenta")

            idx = 1
            for entry in manual_norm:
                table.add_row(str(idx), str(entry.get("name", "")), f"${float(entry.get('total_value', 0.0) or 0.0):,.2f}")
                idx += 1

            self.console.print(table)
            pick = InputSafe.get_option(
                [str(i) for i in range(1, len(manual_norm) + 1)] + ["0"],
                prompt_text="[bold cyan]Select # to remove (0 cancel):[/bold cyan] "
            )
            if pick == "0":
                InputSafe.pause()
                return

            # Remove by name match (manual_norm is sorted view)
            try:
                target_name = str(manual_norm[int(pick) - 1].get("name", "")).strip().lower()
                kept = []
                removed = False
                for entry in manual_list:
                    if not removed and str(entry.get("name", "")).strip().lower() == target_name:
                        removed = True
                        continue
                    kept.append(entry)
                account.manual_holdings = kept
                if removed:
                    self.console.print("[green]Removed manual asset.[/green]")
                else:
                    self.console.print("[yellow]Manual asset not found.[/yellow]")
            except Exception:
                self.console.print("[red]Invalid selection.[/red]")

            try:
                DataHandler.save_clients(self.clients)
            except Exception as ex:
                self.console.print(f"[red]Warning: Could not auto-save client data: {ex}[/red]")

            InputSafe.pause()
            return

        ticker = raw.strip().upper()
        if ticker in account.holdings:
            del account.holdings[ticker]
            self.console.print(f"[green]Removed {ticker}.[/green]")
            try:
                DataHandler.save_clients(self.clients)
            except Exception as ex:
                self.console.print(f"[red]Warning: Could not auto-save client data: {ex}[/red]")
        else:
            self.console.print(f"[red]Ticker '{ticker}' not found.[/red]")

        InputSafe.pause()

    # --- ACCOUNT CRUD (Create/Update/Delete) ---

    def add_account_workflow(self, client: Client):
        self.console.print(f"\n[bold blue]Add Account for {client.name}[/bold blue]")
        name = self.console.input("[bold cyan]Account Name (e.g., Roth IRA):[/bold cyan] ").strip()
        if not name: return

        type_opts = ["Taxable", "IRA", "401k", "Trust", "Crypto"]
        acct_type = InputSafe.get_option(type_opts, prompt_text="Select Type:")
        
        new_acc = Account(account_name=name, account_type=acct_type)
        client.accounts.append(new_acc)
        DataHandler.save_clients(self.clients)
        self.console.print(f"[green]Account '{name}' created.[/green]")
        InputSafe.pause()

    def remove_account_workflow(self, client: Client):
        if not client.accounts:
            self.console.print("[red]No accounts to remove.[/red]")
            InputSafe.pause()
            return
            
        self.console.print(f"\n[bold red]DELETE ACCOUNT[/bold red]")
        for i, acc in enumerate(client.accounts, 1):
            self.console.print(f"[{i}] {acc.account_name} ({len(acc.holdings)} holdings)")
            
        choice = self.console.input("[bold cyan]Select # to delete (or Enter to cancel):[/bold cyan] ").strip()
        if not choice.isdigit(): return
        
        idx = int(choice) - 1
        if 0 <= idx < len(client.accounts):
            acc = client.accounts[idx]
            if InputSafe.get_yes_no(f"Permanently delete '{acc.account_name}'?", default="n"):
                client.accounts.pop(idx)
                DataHandler.save_clients(self.clients)
                self.console.print("[green]Deleted.[/green]")
        else:
            self.console.print("[red]Invalid selection.[/red]")
        InputSafe.pause()

    def edit_account_workflow(self, account: Account):
        self.console.print(f"\n[bold blue]Edit Account: {account.account_name}[/bold blue]")
        
        new_name = self.console.input(f"New Name [{account.account_name}]: ").strip()
        if new_name: account.account_name = new_name
        
        type_opts = ["Taxable", "IRA", "401k", "Trust", "Crypto"]
        self.console.print(f"Current Type: {account.account_type}")
        self.console.print(f"Options: {', '.join(type_opts)}")
        new_type = self.console.input("New Type (leave blank to keep): ").strip()
        
        if new_type:
            match = next((t for t in type_opts if t.lower() == new_type.lower()), None)
            if match:
                account.account_type = match
            else:
                self.console.print(f"[yellow]Unknown type '{new_type}', keeping original.[/yellow]")

        DataHandler.save_clients(self.clients)
        self.console.print("[green]Account updated.[/green]")
        InputSafe.pause()

    # --- CLIENT CRUD ---

    def add_client_workflow(self):
        name = self.console.input("\n[bold cyan]Client Name:[/bold cyan] ").strip()
        if not name: return
        
        risk = InputSafe.get_option(["Conservative", "Moderate", "Aggressive"], prompt_text="Risk Profile")
        
        new_client = Client(name=name, risk_profile=risk)
        new_client.accounts.append(Account(account_name="Primary Brokerage"))
        
        self.clients.append(new_client)
        DataHandler.save_clients(self.clients)
        self.console.print(f"[green]Client created with ID: {new_client.client_id}[/green]")
        InputSafe.pause()

    def edit_client_workflow(self, client: Client):
        self.console.print(f"\n[bold blue]Edit Profile: {client.name}[/bold blue]")
        new_name = self.console.input(f"New Name [{client.name}]: ").strip()
        if new_name: client.name = new_name
        
        new_risk = InputSafe.get_option(["Conservative", "Moderate", "Aggressive", "SKIP"], prompt_text="New Risk (or SKIP):")
        if new_risk != "SKIP":
            client.risk_profile = new_risk
            
        DataHandler.save_clients(self.clients)
        self.console.print("[green]Profile updated.[/green]")
        InputSafe.pause()

    def delete_client_workflow(self):
        cid = self.console.input("\n[bold red]Client ID to DELETE:[/bold red] ").strip()
        client = self._get_client_by_id(cid)
        if not client:
            self.console.print("[red]Client not found.[/red]")
            InputSafe.pause()
            return

        if InputSafe.get_yes_no(f"Are you sure you want to delete {client.name}?", default="n"):
            self.clients.remove(client)
            DataHandler.save_clients(self.clients)
            self.console.print("[green]Client deleted.[/green]")
        InputSafe.pause()

    def _set_page_interval(self, client: Client, interval: str):
        """Sets interval at the client level and propagates to all accounts for page-wide consistency."""
        if interval not in INTERVAL_POINTS:
            # Fallback only if input was truly invalid, but user workflow below prevents this
            interval = "1M"

        client.active_interval = interval

        # Propagate to accounts so account dashboards stay synced
        for acc in client.accounts:
            acc.active_interval = interval

        DataHandler.save_clients(self.clients)

    def _change_interval_workflow(self, client: Client):
        """Interactive interval selection that applies page-wide."""
        self.console.print("\n[bold gold1]Select Interval (page-wide):[/bold gold1]")
        
        # Explicit mapping for robust input handling
        options_list = list(INTERVAL_POINTS.keys()) # ['1W', '1M', '3M', '6M', '1Y']
        
        for i, opt in enumerate(options_list, 1):
            self.console.print(f"[{i}] {opt}")
            
        # Get numeric input to map reliably to the key string
        choice = InputSafe.get_option([str(i) for i in range(1, len(options_list)+1)] + ["0"], prompt_text="[>]")
        
        if choice == "0":
            return
            
        # Map numeric choice back to the string key (e.g. "1" -> "1W")
        selected_interval = options_list[int(choice) - 1]
        
        self._set_page_interval(client, selected_interval)