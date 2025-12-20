# modules/client_mgr/manager.py

from rich.console import Console
from rich.layout import Layout
from typing import List, Optional, Tuple
from datetime import datetime

# --- Internal Modules ---
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.data_handler import DataHandler
from modules.client_mgr.valuation import ValuationEngine
from modules.client_mgr.toolkit import FinancialToolkit, RegimeModels, RegimeRenderer

# --- Interface & Utils ---
from interfaces.components import UIComponents
from interfaces.navigator import Navigator
from utils.input import InputSafe

# --- Configuration Constants ---
HISTORY_PERIOD = {"1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
HISTORY_INTERVAL_MAP = {"1W": "60m", "1M": "1d", "3M": "1d", "6M": "1d", "1Y": "1d"}
INTERVAL_POINTS = {"1W": 40, "1M": 22, "3M": 66, "6M": 132, "1Y": 252}
CAPM_PERIOD = {"1W": "1mo", "1M": "6mo", "3M": "1y", "6M": "2y", "1Y": "5y"}

class ClientManager:
    """
    Controller for Client & Account Management.
    Orchestrates Data -> UI -> Input -> Action.
    """
    def __init__(self):
        self.console = Console()
        self.clients: List[Client] = DataHandler.load_clients()
        self.valuation_engine = ValuationEngine()

    # =========================================================================
    # MAIN LOOP & LIST VIEW
    # =========================================================================

    def run(self):
        """Entry point for the Manager module."""
        while True:
            # 1. Prepare Data for List View
            # We recalculate total values for the list display
            val_map = {}
            for c in self.clients:
                val = 0.0
                for acc in c.accounts:
                    # Simple valuation for the list view
                    v, _ = self.valuation_engine.calculate_portfolio_value(
                        acc.holdings, history_period="1mo", history_interval="1d"
                    )
                    val += v
                val_map[c.client_id] = val

            # 2. Render List View
            Navigator.clear()
            self.console.print(UIComponents.header("CLIENT MANAGER", breadcrumbs="Main > Clients"))
            self.console.print(UIComponents.client_list_table(self.clients, val_map))

            # 3. Navigation
            options = {
                "1": "➕ Add New Client",
                "2": "📝 Select Client (ID)",
                "3": "🗑️ Delete Client"
            }
            choice = Navigator.show_options(options, title="MANAGER ACTIONS")

            # 4. Handle Action
            if choice == "MAIN_MENU": break
            if choice == "1": self.add_client_workflow()
            elif choice == "2":
                if self.select_client_workflow() == "MAIN_MENU":
                    break
            elif choice == "3": self.delete_client_workflow()
            
            # Save state on loop exit/action completion
            DataHandler.save_clients(self.clients)

    # =========================================================================
    # CLIENT DASHBOARD CONTROLLER
    # =========================================================================

    def select_client_workflow(self):
        cid = InputSafe.get_string("Enter Client ID (partial):")
        client = next((c for c in self.clients if c.client_id.startswith(cid)), None)
        if client:
            return self.client_dashboard_loop(client)
        else:
            self.console.print("[red]Client not found.[/red]")
            InputSafe.pause()
        return None

    def client_dashboard_loop(self, client: Client):
        """Displays specific client portfolio and handles client-level actions."""
        while True:
            # --- 1. Fetch & Calculate Data ---
            interval = str(getattr(client, "active_interval", "1M") or "1M").upper()
            
            # Aggregate holdings
            all_holdings = {}
            all_lots = {}
            for acc in client.accounts:
                for t, q in acc.holdings.items():
                    all_holdings[t] = all_holdings.get(t, 0) + q
                for t, lots in (acc.lots or {}).items():
                    all_lots.setdefault(t, []).extend(lots or [])

            # Market Valuation
            hp = HISTORY_PERIOD.get(interval, "1mo")
            hi = HISTORY_INTERVAL_MAP.get(interval, "1d")
            total_val, enriched_data = self.valuation_engine.calculate_portfolio_value(
                all_holdings, history_period=hp, history_interval=hi
            )

            # Manual Valuation
            manual_total = 0.0
            for acc in client.accounts:
                m_val, _ = self.valuation_engine.calculate_manual_holdings_value(acc.manual_holdings)
                manual_total += m_val

            # History & Charts
            history = self.valuation_engine.generate_synthetic_portfolio_history(
                enriched_data, all_holdings, interval=interval, lot_map=all_lots
            )
            n_points = INTERVAL_POINTS.get(interval, 22)
            spark_data = history[-n_points:] if history else []

            # CAPM Metrics
            capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                all_holdings, benchmark_ticker="SPY", period=CAPM_PERIOD.get(interval, "1y")
            )
            auto_risk = FinancialToolkit.assess_risk_profile(capm)
            if client.risk_profile_source != "manual":
                client.risk_profile = auto_risk
                client.risk_profile_source = "auto"

            # --- 2. Render UI (via Components) ---
            Navigator.clear()
            self.console.print(UIComponents.header(
                f"CLIENT: {client.name}", 
                subtitle=f"ID: {client.client_id} | Interval: {interval} | Risk: {client.risk_profile}",
                breadcrumbs="Clients > Dashboard"
            ))

            # Stack 1: AUM Summary
            self.console.print(UIComponents.portfolio_summary_panel(total_val, manual_total, spark_data))

            # Stack 2: Accounts
            self.console.print(UIComponents.account_list_panel(client, enriched_data))

            # Stack 3: Risk Profile
            self.console.print(UIComponents.risk_profile_full_width(capm))

            # Stack 4: Regime
            self._render_regime_section(history, interval, scope_label="Portfolio")

            # --- 3. Navigation ---
            options = {
                "1": "📝 Edit Profile",
                "2": "💰 Manage Accounts",
                "3": "🛠️ Financial Toolkit",
                "4": "⏱ Change Interval"
            }
            choice = Navigator.show_options(options)

            if choice == "MAIN_MENU":
                return "MAIN_MENU"
            if choice == "1": self.edit_client_workflow(client)
            elif choice == "2":
                if self.manage_accounts_router(client) == "MAIN_MENU":
                    return "MAIN_MENU"
            elif choice == "3": FinancialToolkit(client).run()
            elif choice == "4": self._change_interval_workflow(client)
            
            DataHandler.save_clients(self.clients)
        return None

    def _render_regime_section(self, history, interval, scope_label: str):
        """Helper to render regime snapshot if data exists."""
        returns = []
        if history and len(history) >= 8:
            for i in range(1, len(history)):
                prev = history[i-1]
                if prev > 0: returns.append((history[i] - prev)/prev)
        
        if len(returns) >= 8:
            scope_text = f"{scope_label} [dim]({interval})[/dim]"
            snap = RegimeModels.compute_markov_snapshot(
                returns,
                horizon=1,
                label=scope_text,
                interval=interval,
            )
            snap["scope_label"] = scope_label
            snap["interval"] = interval
            self.console.print(RegimeRenderer.render(snap))

    # =========================================================================
    # ACCOUNT MANAGEMENT CONTROLLER
    # =========================================================================

    def manage_accounts_router(self, client: Client):
        """Route user to specific account actions."""
        while True:
            Navigator.clear()
            self.console.print(UIComponents.header(f"ACCOUNTS: {client.name}", breadcrumbs="Dashboard > Accounts"))
            
            # Simple list for selection
            for i, acc in enumerate(client.accounts, 1):
                self.console.print(f"[{i}] {acc.account_name} ({acc.account_type})")
            
            self.console.print("\n[A] ➕ Add New Account")
            self.console.print("[R] ➖ Remove Account")
            self.console.print("[0] 🔙 Back")

            choice = InputSafe.get_string("[>] Select Account # or Action:").upper()

            if choice == "0": break
            elif choice == "A": self.add_account_workflow(client)
            elif choice == "R": self.remove_account_workflow(client)
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(client.accounts):
                    if self.manage_holdings_loop(client, client.accounts[idx]) == "MAIN_MENU":
                        return "MAIN_MENU"
        return None

    def manage_holdings_loop(self, client: Client, account: Account):
        """Detailed view for a single account."""
        while True:
            interval = str(getattr(client, "active_interval", "1M") or "1M").upper()
            account.active_interval = interval # Sync

            # 1. Fetch Data
            hp = HISTORY_PERIOD.get(interval, "1mo")
            hi = HISTORY_INTERVAL_MAP.get(interval, "1d")
            
            # Market Val
            total_val, enriched = self.valuation_engine.calculate_portfolio_value(
                account.holdings, history_period=hp, history_interval=hi
            )
            account.current_value = total_val

            manual_total, manual_list = self.valuation_engine.calculate_manual_holdings_value(
                account.manual_holdings
            )

            # Metrics for THIS account
            history = self.valuation_engine.generate_synthetic_portfolio_history(
                enriched, account.holdings, interval=interval, lot_map=account.lots
            )
            capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                account.holdings, benchmark_ticker="SPY", period=CAPM_PERIOD.get(interval, "1y")
            )

            n_points = INTERVAL_POINTS.get(interval, 22)
            spark_data = history[-n_points:] if history else []

            # --- 2. Render UI (Same components, scoped data) ---
            Navigator.clear()
            self.console.print(UIComponents.header(
                f"ACCOUNT: {account.account_name}", 
                subtitle=f"{client.name} | {account.account_type}",
                breadcrumbs=f"Clients > {client.name[:10]}... > Account"
            ))

            # Top: Account Specific Summary
            self.console.print(UIComponents.account_detail_overview(total_val, manual_total, history[-30:]))

            # Middle: Detailed Holdings
            self.console.print(UIComponents.holdings_table(account, enriched, total_val))
            if manual_list:
                self.console.print(UIComponents.manual_assets_table(manual_list))

            # Bottom: Risk and Regime parity
            self.console.print(UIComponents.risk_profile_full_width(capm))
            self._render_regime_section(history, interval, scope_label=f"Account: {account.account_name}")

            # --- 3. Navigation ---
            options = {
                "1": "➕ Add/Update Holding",
                "2": "➖ Remove Holding",
                "3": "📝 Edit Account Details"
            }
            choice = Navigator.show_options(options)

            if choice == "MAIN_MENU": return "MAIN_MENU"
            if choice == "1": self.add_holding_workflow(account)
            elif choice == "2": self.remove_holding_workflow(account)
            elif choice == "3": self.edit_account_workflow(account)
            
            DataHandler.save_clients(self.clients)
        return None

    # =========================================================================
    # WORKFLOWS (Logic Wrappers)
    # =========================================================================

    def add_client_workflow(self):
        name = InputSafe.get_string("Client Name:")
        if not name: return
        new_client = Client(name=name, risk_profile="Unassigned")
        new_client.accounts.append(Account(account_name="Primary Brokerage"))
        self.clients.append(new_client)
        self.console.print("[green]Client Added.[/green]")
        InputSafe.pause()

    def edit_client_workflow(self, client: Client):
        new_name = InputSafe.get_string(f"New Name [{client.name}]:")
        if new_name: client.name = new_name
        new_risk = InputSafe.get_string(
            f"Risk Profile [{client.risk_profile}] (free text, leave empty to keep):"
        )
        if new_risk:
            client.risk_profile = new_risk.strip()
            client.risk_profile_source = "manual"
        InputSafe.pause()

    def delete_client_workflow(self):
        cid = InputSafe.get_string("Client ID to DELETE:")
        client = next((c for c in self.clients if c.client_id == cid), None)
        if client and InputSafe.get_yes_no(f"Delete {client.name}?"):
            self.clients.remove(client)
            self.console.print("[green]Deleted.[/green]")
        InputSafe.pause()

    def _change_interval_workflow(self, client):
        opts = list(INTERVAL_POINTS.keys())
        self.console.print("[dim]Select Interval ([0] Back)[/dim]")
        choice = InputSafe.get_option(opts + ["0"], prompt_text="[>]")
        if choice == "0":
            return
        choice = str(choice).upper()
        client.active_interval = choice
        for acc in client.accounts: acc.active_interval = choice

    # --- Account CRUD ---
    def add_account_workflow(self, client):
        name = InputSafe.get_string("Account Name:")
        if not name: return
        self.console.print("[bold]Account Type[/bold] ([0] Back, Enter to skip)")
        self.console.print("[1] Taxable  [2] IRA  [3] 401k  [4] Trust  [5] Crypto  [M] Manual")
        choice = InputSafe.get_string("[>] Type:")
        if choice.strip() == "0":
            return
        if not choice.strip():
            account_type = "Unspecified"
        else:
            key = choice.strip().lower()
            if key == "m":
                manual = InputSafe.get_string("Custom Type:")
                if not manual:
                    account_type = "Unspecified"
                else:
                    account_type = manual.strip()
            else:
                type_map = {
                    "1": "Taxable",
                    "2": "IRA",
                    "3": "401k",
                    "4": "Trust",
                    "5": "Crypto",
                }
                account_type = type_map.get(key, choice.strip())
        client.accounts.append(Account(account_name=name, account_type=account_type))

    def remove_account_workflow(self, client):
        # Logic to remove account...
        pass

    def edit_account_workflow(self, account):
        name = InputSafe.get_string(f"New Name [{account.account_name}]:")
        if name: account.account_name = name

    # --- Holding CRUD ---
    def add_holding_workflow(self, account):
        # Logic largely remains the same as original, utilizing InputSafe
        # But relies on simple console prints for the interaction flow
        self.console.print("\n[dim]Enter Ticker or 'MANUAL'[/dim]")
        ticker = InputSafe.get_string("Ticker:").upper()
        if not ticker: return

        if ticker == "MANUAL":
            self._add_manual_holding_logic(account)
            return

        # Acquisition Logic
        self.console.print("[1] Current Price [2] Historical [3] Custom Basis [0] Back")
        method = InputSafe.get_option(["1", "2", "3", "0"])
        if method == "0":
            return
        
        qty = InputSafe.get_float("Quantity:")
        
        basis, ts_label, source = self._resolve_lot_basis(ticker, method)
        if basis is None:
            self.console.print("[red]Unable to resolve cost basis.[/red]")
            InputSafe.pause()
            return

        lot_entry = {
            "qty": qty,
            "basis": basis,
            "timestamp": ts_label
        }
        if source:
            lot_entry["source"] = source

        account.lots.setdefault(ticker, []).append(lot_entry)
        
        account.sync_holdings_from_lots()
        self.console.print("[green]Holding Updated.[/green]")
        InputSafe.pause()

    def _add_manual_holding_logic(self, account):
        name = InputSafe.get_string("Asset Name:")
        val = InputSafe.get_float("Estimated Value:")
        if not account.manual_holdings: account.manual_holdings = []
        account.manual_holdings.append({"name": name, "total_value": val})
        
    def remove_holding_workflow(self, account):
        ticker = InputSafe.get_string("Ticker to remove:").upper()
        if ticker in account.holdings:
            del account.holdings[ticker]
            if ticker in account.lots: del account.lots[ticker]
            self.console.print("[green]Removed.[/green]")
        InputSafe.pause()

    def _resolve_lot_basis(self, ticker: str, method: str) -> Tuple[Optional[float], str, str]:
        """Resolve lot basis based on user-selected method."""
        if method == "1":
            quote = self.valuation_engine.get_quote_data(ticker)
            price = float(quote.get("price", 0.0) or 0.0)
            if price <= 0:
                price = InputSafe.get_float("Enter current price ($):", min_val=0.01)
            return price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "MARKET"

        if method == "2":
            while True:
                ts_str = InputSafe.get_string("Timestamp (MM/DD/YY HH:MM:SS):")
                try:
                    ts = datetime.strptime(ts_str, "%m/%d/%y %H:%M:%S")
                except ValueError:
                    self.console.print("[red]Invalid format. Use MM/DD/YY HH:MM:SS[/red]")
                    continue

                price = self.valuation_engine.get_historical_price(ticker, ts)
                if price is None or price <= 0:
                    self.console.print("[yellow]Unable to fetch historical price. Enter manually.[/yellow]")
                    price = InputSafe.get_float("Enter historical price ($):", min_val=0.01)

                return price, ts.strftime("%Y-%m-%d %H:%M:%S"), "HISTORICAL"

        price = InputSafe.get_float("Enter custom cost basis ($):", min_val=0.01)
        return price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "CUSTOM"
