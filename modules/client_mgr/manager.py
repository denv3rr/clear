# modules/client_mgr/manager.py

from rich.console import Console, Group
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time

# --- Internal Modules ---
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.data_handler import DataHandler
from modules.client_mgr.valuation import ValuationEngine
from modules.client_mgr.toolkit import FinancialToolkit, RegimeModels, RegimeRenderer
from modules.client_mgr.tax import TaxEngine
from modules.market_data.trackers import GlobalTrackers, TrackerRelevance

# --- Interface & Utils ---
from interfaces.components import UIComponents
from interfaces.navigator import Navigator
from interfaces.shell import ShellRenderer
from interfaces.menu_layout import build_sidebar, build_status_header, compact_for_width
from utils.input import InputSafe

# --- Configuration Constants ---
HISTORY_PERIOD = {"1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
HISTORY_INTERVAL_MAP = {"1W": "60m", "1M": "1d", "3M": "1d", "6M": "1d", "1Y": "1d"}
INTERVAL_POINTS = {"1W": 40, "1M": 22, "3M": 66, "6M": 132, "1Y": 252}
CAPM_PERIOD = {"1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"}
CAPM_PERIOD_FALLBACK = {"1W": "1mo", "1M": "6mo", "3M": "1y", "6M": "2y", "1Y": "5y"}
REGIME_PERIOD_FALLBACK = {"1W": "1mo", "1M": "6mo", "3M": "1y", "6M": "2y", "1Y": "5y"}
REGIME_MIN_SAMPLES = 60

class ClientManager:
    """
    Controller for Client & Account Management.
    Orchestrates Data -> UI -> Input -> Action.
    """
    def __init__(self):
        self.console = Console()
        self.clients: List[Client] = DataHandler.load_clients()
        self.valuation_engine = ValuationEngine()
        self.tax_engine = TaxEngine()
        self.trackers = GlobalTrackers()
        self._list_val_cache = {}

    # =========================================================================
    # MAIN LOOP & LIST VIEW
    # =========================================================================

    def run(self):
        """Entry point for the Manager module."""
        while True:
            # 1. Prepare Data for List View
            val_map = {}
            for c in self.clients:
                val_map[c.client_id] = self._get_cached_list_value(c)

            # 2. Render List View
            cache_age = "-"
            if self._list_val_cache:
                last_ts = max(c.get("ts", 0) for c in self._list_val_cache.values())
                if last_ts:
                    cache_age = f"{int(time.time() - last_ts)}s"
            status_panel = build_status_header(
                "Status",
                [
                    ("Clients", str(len(self.clients))),
                    ("Val Cache", cache_age),
                ],
                compact=compact_for_width(self.console.width),
            )
            content = Group(
                status_panel,
                UIComponents.header("CLIENT MANAGER", breadcrumbs="Main > Clients"),
                UIComponents.client_list_table(self.clients, val_map),
            )
            options = {
                "1": "Add New Client",
                "2": "Select Client (ID)",
                "3": "Delete Client",
            }
            compact = compact_for_width(self.console.width)
            sidebar = build_sidebar(
                [("Clients", options)],
                show_main=True,
                show_back=False,
                show_exit=True,
                compact=compact,
            )
            choice = ShellRenderer.render_and_prompt(
                content,
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=False,
                show_exit=True,
                show_header=False,
                sidebar_override=sidebar,
            )

            # 3. Navigation
            if choice == "m":
                break
            if choice == "x":
                Navigator.exit_app()

            # 4. Handle Action
            if choice == "1": self.add_client_workflow()
            elif choice == "2":
                if self.select_client_workflow() == "MAIN_MENU":
                    break
            elif choice == "3": self.delete_client_workflow()
            
            # Save state on loop exit/action completion
            DataHandler.save_clients(self.clients)

    def _client_holdings_fingerprint(self, client: Client) -> tuple:
        holdings = {}
        for acc in client.accounts:
            for ticker, qty in (acc.holdings or {}).items():
                holdings[ticker] = holdings.get(ticker, 0.0) + float(qty or 0.0)
        return tuple(sorted((t, round(q, 6)) for t, q in holdings.items()))

    def _get_cached_list_value(self, client: Client, ttl_seconds: int = 30) -> float:
        cache = self._list_val_cache.get(client.client_id)
        now = time.time()
        fp = self._client_holdings_fingerprint(client)
        if cache:
            if cache.get("fp") == fp and (now - cache.get("ts", 0)) < ttl_seconds:
                return float(cache.get("value", 0.0) or 0.0)

        total = 0.0
        for acc in client.accounts:
            ShellRenderer.set_busy(0.8)
            v, _ = self.valuation_engine.calculate_portfolio_value(
                acc.holdings, history_period="1mo", history_interval="1d"
            )
            total += float(v or 0.0)
        self._list_val_cache[client.client_id] = {"fp": fp, "ts": now, "value": total}
        return total

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
            ShellRenderer.set_busy(1.0)
            total_val, enriched_data = self.valuation_engine.calculate_portfolio_value(
                all_holdings, history_period=hp, history_interval=hi
            )

            # Manual Valuation
            manual_total = 0.0
            for acc in client.accounts:
                m_val, _ = self.valuation_engine.calculate_manual_holdings_value(acc.manual_holdings)
                manual_total += m_val

            # History & Charts
            history_dates, history = self.valuation_engine.generate_portfolio_history_series(
                enriched_data=enriched_data,
                holdings=all_holdings,
                interval=interval,
                lot_map=all_lots,
            )
            n_points = INTERVAL_POINTS.get(interval, 22)
            spark_data = history[-n_points:] if history else []

            # CAPM Metrics
            ShellRenderer.set_busy(1.0)
            capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                all_holdings, benchmark_ticker="SPY", period=CAPM_PERIOD.get(interval, "1y")
            )
            if capm.get("error") or int(capm.get("points", 0) or 0) < 30:
                ShellRenderer.set_busy(1.0)
                capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                    all_holdings, benchmark_ticker="SPY", period=CAPM_PERIOD_FALLBACK.get(interval, "1y")
                )
            auto_risk = FinancialToolkit.assess_risk_profile(capm)
            if client.risk_profile_source != "manual":
                client.risk_profile = auto_risk
                client.risk_profile_source = "auto"

            # --- 2. Render UI (via Components) ---
            regime_panel = self._build_regime_section(
                history=history,
                history_dates=history_dates,
                interval=interval,
                scope_label="Portfolio",
                holdings=all_holdings,
                lots=all_lots,
            )
            tracker_panel = self._build_tracker_metrics_panel(client=client)
            status_panel = build_status_header(
                "Status",
                [
                    ("Interval", interval),
                    ("Accounts", str(len(client.accounts))),
                    ("Holdings", str(len(all_holdings))),
                ],
                compact=compact_for_width(self.console.width),
            )
            content = Group(
                status_panel,
                UIComponents.header(
                    f"CLIENT: {client.name}",
                    subtitle=f"ID: {client.client_id} | Interval: {interval} | Risk: {client.risk_profile}",
                    breadcrumbs="Clients > Dashboard"
                ),
                UIComponents.portfolio_summary_panel(total_val, manual_total, spark_data),
                UIComponents.account_list_panel(client, enriched_data),
                UIComponents.risk_profile_full_width(capm),
                tracker_panel if tracker_panel else Text(""),
                UIComponents.client_tax_profile_panel(client),
                UIComponents.tax_estimate_panel(
                    self.tax_engine.estimate_client_unrealized_tax(
                        client,
                        enriched_data,
                    ),
                    title="Portfolio Tax Estimate"
                ),
                regime_panel,
            )
            options = {
                "1": "Edit Profile",
                "2": "Manage Accounts",
                "3": "Financial Toolkit",
                "4": "Change Interval",
            }
            compact = compact_for_width(self.console.width)
            sidebar = build_sidebar(
                [("Client", options)],
                show_main=True,
                show_back=False,
                show_exit=True,
                compact=compact,
            )
            choice = ShellRenderer.render_and_prompt(
                content,
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=False,
                show_exit=True,
                show_header=False,
                sidebar_override=sidebar,
            )

            # --- 3. Navigation ---
            if choice == "m":
                return "MAIN_MENU"
            if choice == "x":
                Navigator.exit_app()
            if choice == "1": self.edit_client_workflow(client)
            elif choice == "2":
                if self.manage_accounts_router(client) == "MAIN_MENU":
                    return "MAIN_MENU"
            elif choice == "3": FinancialToolkit(client).run()
            elif choice == "4": self._change_interval_workflow(client)
            
            DataHandler.save_clients(self.clients)
        return None

    def _build_regime_section(self, history, history_dates, interval, scope_label: str, holdings: dict, lots: dict):
        """Helper to render regime snapshot if data exists."""
        returns, used_interval, used_dates = self._prepare_regime_returns(
            history=history,
            history_dates=history_dates,
            interval=interval,
            holdings=holdings,
            lots=lots,
        )
        
        if len(returns) >= 8:
            scope_text = self._format_regime_label(scope_label, interval, used_interval)
            snap = RegimeModels.compute_markov_snapshot(
                returns,
                horizon=1,
                label=scope_text,
                interval=used_interval,
                timestamps=used_dates,
            )
            snap["scope_label"] = scope_label
            snap["interval"] = interval
            snap["regime_window"] = used_interval
            return RegimeRenderer.render(snap)
        return Text("")

    def _format_regime_label(self, scope_label: str, view_interval: str, regime_interval: str) -> str:
        if view_interval == regime_interval:
            return f"{scope_label} [dim]({view_interval})[/dim]"
        return f"{scope_label} [dim](View {view_interval} | Regime {regime_interval})[/dim]"

    def _prepare_regime_returns(self, history, history_dates, interval, holdings, lots):
        returns = []
        dates = history_dates or []
        if history and len(history) >= 8:
            for i in range(1, len(history)):
                prev = history[i-1]
                if prev > 0:
                    returns.append((history[i] - prev) / prev)

        if len(returns) >= REGIME_MIN_SAMPLES or not holdings:
            return returns, interval, dates

        fallback_period = REGIME_PERIOD_FALLBACK.get(interval)
        if not fallback_period:
            return returns, interval, dates

        ShellRenderer.set_busy(1.0)
        _, extended_enriched = self.valuation_engine.calculate_portfolio_value(
            holdings,
            history_period=fallback_period,
            history_interval=HISTORY_INTERVAL_MAP.get(interval, "1d"),
        )
        ext_dates, ext_history = self.valuation_engine.generate_portfolio_history_series(
            enriched_data=extended_enriched,
            holdings=holdings,
            interval=interval,
            lot_map=lots,
        )

        ext_returns = []
        if ext_history and len(ext_history) >= 8:
            for i in range(1, len(ext_history)):
                prev = ext_history[i-1]
                if prev > 0:
                    ext_returns.append((ext_history[i] - prev) / prev)

        if len(ext_returns) > len(returns):
            return ext_returns, fallback_period, ext_dates

        return returns, interval, dates

    # =========================================================================
    # ACCOUNT MANAGEMENT CONTROLLER
    # =========================================================================

    def manage_accounts_router(self, client: Client):
        """Route user to specific account actions."""
        while True:
            rows = Table.grid(expand=True)
            rows.add_column()
            rows.add_row(UIComponents.header(f"ACCOUNTS: {client.name}", breadcrumbs="Dashboard > Accounts"))
            for i, acc in enumerate(client.accounts, 1):
                rows.add_row(f"[{i}] {acc.account_name} ({acc.account_type})")
            rows.add_row("")
            rows.add_row("[A] Add New Account")
            rows.add_row("[R] Remove Account")
            rows.add_row("[0] Back")

            valid_choices = [str(i) for i in range(1, len(client.accounts) + 1)]
            valid_choices += ["a", "r", "0", "m", "x"]
            choice = ShellRenderer.render_and_prompt(
                Group(rows),
                context_actions={
                    "A": "Add New Account",
                    "R": "Remove Account",
                    "0": "Back",
                },
                valid_choices=valid_choices,
                prompt_label=">",
                show_main=True,
                show_back=True,
                show_exit=True,
                show_header=False,
                sidebar_override=build_sidebar(
                    [("Accounts", {"A": "Add New Account", "R": "Remove Account"})],
                    show_main=True,
                    show_back=True,
                    show_exit=True,
                    compact=compact_for_width(self.console.width),
                ),
            )

            if choice == "0":
                break
            if choice == "m":
                return "MAIN_MENU"
            if choice == "x":
                Navigator.exit_app()
            elif choice == "a":
                self.add_account_workflow(client)
            elif choice == "r":
                self.remove_account_workflow(client)
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
            ShellRenderer.set_busy(1.0)
            total_val, enriched = self.valuation_engine.calculate_portfolio_value(
                account.holdings, history_period=hp, history_interval=hi
            )
            account.current_value = total_val

            manual_total, manual_list = self.valuation_engine.calculate_manual_holdings_value(
                account.manual_holdings
            )

            # Metrics for THIS account
            history_dates, history = self.valuation_engine.generate_portfolio_history_series(
                enriched_data=enriched,
                holdings=account.holdings,
                interval=interval,
                lot_map=account.lots,
            )
            ShellRenderer.set_busy(1.0)
            capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                account.holdings, benchmark_ticker="SPY", period=CAPM_PERIOD.get(interval, "1y")
            )
            if capm.get("error") or int(capm.get("points", 0) or 0) < 30:
                ShellRenderer.set_busy(1.0)
                capm = FinancialToolkit.compute_capm_metrics_from_holdings(
                    account.holdings, benchmark_ticker="SPY", period=CAPM_PERIOD_FALLBACK.get(interval, "1y")
                )

            n_points = INTERVAL_POINTS.get(interval, 22)
            spark_data = history[-n_points:] if history else []

            # --- 2. Render UI (Same components, scoped data) ---
            regime_panel = self._build_regime_section(
                history=history,
                history_dates=history_dates,
                interval=interval,
                scope_label=f"Account: {account.account_name}",
                holdings=account.holdings,
                lots=account.lots,
            )
            tracker_panel = self._build_tracker_metrics_panel(client=client, account=account)
            status_panel = build_status_header(
                "Status",
                [
                    ("Interval", interval),
                    ("Holdings", str(len(account.holdings))),
                    ("Manual", str(len(manual_list))),
                ],
                compact=compact_for_width(self.console.width),
            )
            content = Group(
                status_panel,
                UIComponents.header(
                    f"ACCOUNT: {account.account_name}",
                    subtitle=f"{client.name} | {account.account_type}",
                    breadcrumbs=f"Clients > {client.name[:10]}... > Account"
                ),
                UIComponents.account_detail_overview(total_val, manual_total, history[-30:]),
                UIComponents.holdings_table(account, enriched, total_val),
                UIComponents.manual_assets_table(manual_list) if manual_list else Text(""),
                UIComponents.risk_profile_full_width(capm),
                tracker_panel if tracker_panel else Text(""),
                UIComponents.account_tax_settings_panel(account),
                UIComponents.tax_estimate_panel(
                    self.tax_engine.estimate_account_unrealized_tax(
                        account,
                        enriched,
                        client.tax_profile,
                    ),
                    title="Account Tax Estimate"
                ),
                regime_panel,
            )
            options = {
                "1": "Add/Update Holding",
                "2": "Remove Holding",
                "3": "Edit Account Details",
            }
            compact = compact_for_width(self.console.width)
            sidebar = build_sidebar(
                [("Account", options)],
                show_main=True,
                show_back=False,
                show_exit=True,
                compact=compact,
            )
            choice = ShellRenderer.render_and_prompt(
                content,
                context_actions=options,
                valid_choices=list(options.keys()) + ["m", "x"],
                prompt_label=">",
                show_main=True,
                show_back=False,
                show_exit=True,
                show_header=False,
                sidebar_override=sidebar,
            )

            # --- 3. Navigation ---
            if choice == "m":
                return "MAIN_MENU"
            if choice == "x":
                Navigator.exit_app()
            if choice == "1": self.add_holding_workflow(account)
            elif choice == "2": self.remove_holding_workflow(account)
            elif choice == "3": self.edit_account_workflow(account)
            
            DataHandler.save_clients(self.clients)
        return None

    def _build_tracker_metrics_panel(self, client: Client, account: Optional[Account] = None):
        account_tags: Dict[str, List[str]] = {}
        if account:
            if account.tags:
                account_tags[account.account_name] = account.tags
        else:
            for acc in client.accounts:
                if acc.tags:
                    account_tags[acc.account_name] = acc.tags

        rules, matched_accounts = TrackerRelevance.match_rules(account_tags)
        if not rules:
            return None

        snapshot = self.trackers.get_snapshot(mode="combined", allow_refresh=False)
        points = snapshot.get("points", []) or []
        if not points:
            return UIComponents.tracker_metrics_panel({
                "status": "not_loaded",
                "accounts": matched_accounts,
                "tags": sorted({tag for tags in matched_accounts.values() for tag in tags}),
                "message": "Tracker data not cached. Open Global Trackers to fetch.",
            })

        filtered = TrackerRelevance.filter_points(points, rules)
        summary = TrackerRelevance.summarize(filtered)
        age = "-"
        if self.trackers._last_refresh:
            age = f"{int(time.time() - self.trackers._last_refresh)}s"
        return UIComponents.tracker_metrics_panel({
            "status": "ok",
            "accounts": matched_accounts,
            "tags": sorted({tag for tags in matched_accounts.values() for tag in tags}),
            "last_refresh_age": age,
            "summary": summary,
        })

    # =========================================================================
    # WORKFLOWS (Logic Wrappers)
    # =========================================================================

    def add_client_workflow(self):
        name = InputSafe.get_string("Client Name:")
        if not name: return
        new_client = Client(name=name, risk_profile="Not Assessed")
        new_client.accounts.append(Account(account_name="Primary Brokerage"))
        self.clients.append(new_client)
        self.console.print("[green]Client Added.[/green]")
        InputSafe.pause()

    def edit_client_workflow(self, client: Client):
        new_name = InputSafe.get_string(f"New Name [{client.name}]:")
        if new_name: client.name = new_name
        new_risk = InputSafe.get_string(
            f"Risk Profile [{client.risk_profile}] (auto/manual, Enter to keep):"
        )
        if new_risk:
            cleaned = new_risk.strip()
            if cleaned.lower() in ("auto", "automatic"):
                client.risk_profile = "Not Assessed"
                client.risk_profile_source = "auto"
            else:
                client.risk_profile = cleaned
                client.risk_profile_source = "manual"
        if InputSafe.get_yes_no("Update tax profile?"):
            self._edit_client_tax_profile(client)
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
        self.console.print("[1] Taxable  [2] Traditional IRA  [3] Roth IRA  [4] 401k  [5] 403b")
        self.console.print("[6] 457b  [7] SEP IRA  [8] SIMPLE IRA  [9] HSA  [10] 529")
        self.console.print("[11] Trust  [12] Joint  [13] Custodial  [14] Corporate  [15] Crypto  [M] Manual")
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
                    "2": "Traditional IRA",
                    "3": "Roth IRA",
                    "4": "401k",
                    "5": "403b",
                    "6": "457b",
                    "7": "SEP IRA",
                    "8": "SIMPLE IRA",
                    "9": "HSA",
                    "10": "529",
                    "11": "Trust",
                    "12": "Joint",
                    "13": "Custodial",
                    "14": "Corporate",
                    "15": "Crypto",
                }
                account_type = type_map.get(key, choice.strip())
        account = Account(account_name=name, account_type=account_type)
        tag_hint = ", ".join(sorted(TrackerRelevance.TAG_RULES.keys()))
        if tag_hint:
            self.console.print(f"[dim]Optional tracker tags (comma-separated): {tag_hint}[/dim]")
        tags = InputSafe.get_string("Tags (optional, comma-separated):")
        if tags:
            account.tags = [t.strip() for t in tags.split(",") if t.strip()]
        client.accounts.append(account)

    def remove_account_workflow(self, client):
        # Logic to remove account...
        pass

    def edit_account_workflow(self, account):
        name = InputSafe.get_string(f"New Name [{account.account_name}]:")
        if name: account.account_name = name
        acc_type = InputSafe.get_string(f"Account Type [{account.account_type}] (Enter to keep):")
        if acc_type:
            account.account_type = acc_type.strip()
        ownership = InputSafe.get_string(f"Ownership Type [{account.ownership_type}] (Enter to keep):")
        if ownership:
            account.ownership_type = ownership.strip()
        custodian = InputSafe.get_string(f"Custodian [{account.custodian}] (Enter to keep):")
        if custodian:
            account.custodian = custodian.strip()
        tag_hint = ", ".join(sorted(TrackerRelevance.TAG_RULES.keys()))
        if tag_hint:
            self.console.print(f"[dim]Tracker tags (comma-separated) for relevance: {tag_hint}[/dim]")
        tags = InputSafe.get_string("Tags (comma-separated, Enter to keep):")
        if tags:
            account.tags = [t.strip() for t in tags.split(",") if t.strip()]
        if InputSafe.get_yes_no("Update account tax settings?"):
            self._edit_account_tax_settings(account)

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

    def _edit_client_tax_profile(self, client: Client):
        profile = client.tax_profile or {}
        residency = InputSafe.get_string(
            f"Residency Country [{profile.get('residency_country', '')}] (Enter to keep):"
        )
        tax_country = InputSafe.get_string(
            f"Tax Country [{profile.get('tax_country', '')}] (Enter to keep):"
        )
        currency = InputSafe.get_string(
            f"Reporting Currency [{profile.get('reporting_currency', 'USD')}] (Enter to keep):"
        )
        treaty = InputSafe.get_string(
            f"Treaty Country [{profile.get('treaty_country', '')}] (Enter to keep):"
        )
        tax_id = InputSafe.get_string(
            f"Tax ID [{profile.get('tax_id', '')}] (Enter to keep):"
        )

        if residency:
            profile["residency_country"] = residency.strip()
        if tax_country:
            profile["tax_country"] = tax_country.strip()
        if currency:
            profile["reporting_currency"] = currency.strip().upper()
        if treaty:
            profile["treaty_country"] = treaty.strip()
        if tax_id:
            profile["tax_id"] = tax_id.strip()
        client.tax_profile = profile

    def _edit_account_tax_settings(self, account: Account):
        settings = account.tax_settings or {}
        jurisdiction = InputSafe.get_string(
            f"Jurisdiction [{settings.get('jurisdiction', '')}] (Enter to keep):"
        )
        currency = InputSafe.get_string(
            f"Account Currency [{settings.get('account_currency', 'USD')}] (Enter to keep):"
        )
        withhold = InputSafe.get_string(
            f"Withholding Rate % [{settings.get('withholding_rate', '')}] (Enter to keep):"
        )
        tax_exempt = InputSafe.get_yes_no(
            f"Tax Exempt? (current: {settings.get('tax_exempt', False)})"
        )

        if jurisdiction:
            settings["jurisdiction"] = jurisdiction.strip()
        if currency:
            settings["account_currency"] = currency.strip().upper()
        if withhold:
            try:
                rate = float(withhold)
                if rate < 0:
                    rate = 0.0
                if rate > 100:
                    rate = 100.0
                settings["withholding_rate"] = rate
            except Exception:
                pass
        settings["tax_exempt"] = bool(tax_exempt)
        account.tax_settings = settings
