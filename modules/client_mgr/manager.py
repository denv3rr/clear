from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.align import Align
from rich.text import Text
from typing import Optional, Tuple, List, Union

from utils.input import InputSafe
from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.data_handler import DataHandler
from modules.client_mgr.valuation import ValuationEngine

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
        total_value, _ = self.valuation_engine.calculate_portfolio_value(account.holdings)
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

    def _build_account_summary_table(self, client: Client) -> Tuple[Table, float]:
        summary_table = Table(
            title="\n\n\n[bold gold1]Portfolio Structure[/bold gold1]",
            box=box.SIMPLE_HEAD,
            expand=True,
            header_style="bold cyan"
        )
        summary_table.add_column("ID", style="dim", width=8)
        summary_table.add_column("Account Name")
        summary_table.add_column("Type")
        summary_table.add_column("Holdings", justify="center")
        summary_table.add_column("Market Value", style="green", justify="right")
        
        total_portfolio_value = 0.0
        
        for account in client.accounts:
            total_value = self._recalculate_account_value(account) 
            total_portfolio_value += total_value
            
            summary_table.add_row(
                account.account_id[:8],
                account.account_name,
                account.account_type,
                str(len(account.holdings)),
                f"${total_value:,.2f}"
            )
        
        return summary_table, total_portfolio_value

    def display_client_dashboard(self, client: Client):
        """Composes and displays the client's main dashboard."""
        
        # 1. Title
        title = Text(f"CLIENT DASHBOARD:", style="bold yellow")
        self.console.print(Align.center(title))
        self.console.print(Text(f"{client.name}", style="bold white underline"), "\n", justify="center")
        
        # 2. Details
        info_panel = self._build_client_details_panel(client)
        self.console.print(Align.center(info_panel))

        # 3. Accounts & Totals
        account_summary_table, total_portfolio_value = self._build_account_summary_table(client)
        
        total_panel = Panel(
            Align.center(f"[bold white]Total Assets Under Management (AUM):[/bold white] [bold green]${total_portfolio_value:,.2f}[/bold green]"), 
            border_style="green",
            box=box.ROUNDED,
            width=100
        )
        self.console.print(Align.center(total_panel))
        self.console.print(account_summary_table)
        self.console.print("\n\n\n")
        self.console.rule("[dim]ACTIONS[/dim]")

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
            self.display_client_dashboard(client)
            
            self.console.print(f"\n[bold gold1]CLIENT OPTIONS | {client.name}[/bold gold1]")
            self.console.print("[1] 📝 Edit Client Profile")
            self.console.print("[2] 💰 Manage Accounts & Holdings")
            self.console.print("[0] 🔙 Return to Client List")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="[>]")
            
            if choice == "0":
                DataHandler.save_clients(self.clients)
                break
            elif choice == "1":
                self.edit_client_workflow(client)
            elif choice == "2":
                self.manage_accounts_workflow(client)
                
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
        
        self.console.print(account_table)

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
            self.console.clear()
            
            # Header
            header = Panel(
                f"[bold white]Client:[/bold white] {client.name}\n"
                f"[bold white]Account:[/bold white] {account.account_name} ({account.account_type})",
                border_style="blue"
            )
            self.console.print(header)
            
            # Data Display
            self.display_account_holdings(account)

            self.console.print("\n[bold gold1]ACCOUNT ACTIONS:[/bold gold1]")
            self.console.print("[1] ➕ Add/Update Holding (Ticker & Qty)")
            self.console.print("[2] ➖ Remove Holding")
            self.console.print("[3] 📝 Edit Account Details")
            self.console.print("[0] 🔙 Return to Accounts")
            
            choice = InputSafe.get_option(["1", "2", "3", "0"], prompt_text="[>]")

            if choice == "0":
                break
            elif choice == "1":
                self.add_holding_workflow(account)
            elif choice == "2":
                self.remove_holding_workflow(account)
            elif choice == "3":
                self.edit_account_workflow(account)

    # --- HOLDINGS & DETAILS LOGIC ---

    def display_account_holdings(self, account: Account):
        """Renders the detailed holdings with robust pricing and trend data."""
        
        # Get enriched data from ValuationEngine
        total_val, enriched_data = self.valuation_engine.calculate_portfolio_value(account.holdings)
        
        table = Table(title=f"[bold gold1]Current Holdings[/bold gold1]", box=box.SIMPLE_HEAD, expand=True)
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Trend", justify="center", width=5) # New Trend Column
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
        
        # Summary footer
        self.console.print(Align.right(
            f"[bold white]Total Account Value: [/bold white][bold green]${total_val:,.2f}[/bold green]",
        ))

    def add_holding_workflow(self, account: Account):
        self.console.print("\n[dim]Enter Ticker alone OR 'Ticker Quantity' (e.g. 'NVDA 10')[/dim]")
        
        try:
            # Step 1: Input handling for space-separated values
            raw_input = self.console.input("[bold cyan]Ticker Input:[/bold cyan] ").strip()
            if not raw_input: return

            parts = raw_input.split()
            ticker = parts[0].upper()
            quantity = None

            if len(parts) >= 2:
                # User provided "TICKER QUANTITY"
                try:
                    quantity = float(parts[1])
                except ValueError:
                    self.console.print(f"[red]Could not parse quantity '{parts[1]}'.[/red]")
                    InputSafe.pause()
                    return
            
            # Step 2: Check current price (Feedback)
            quote = self.valuation_engine.get_quote_data(ticker)
            price = quote.get('price', 0.0)
            
            if price > 0:
                self.console.print(f"   [dim]Price: ${price:,.2f} | Trend: {quote.get('change_pct', 0):+.2f}%[/dim]")
            else:
                self.console.print(f"   [yellow]Warning: Could not fetch live price for '{ticker}'.[/yellow]")

            # Step 3: Prompt for quantity only if not already provided
            if quantity is None:
                qty_str = self.console.input(f"[bold cyan]Quantity for {ticker}:[/bold cyan] ").strip()
                if not qty_str: return 
                quantity = float(qty_str)
            
            if quantity < 0:
                self.console.print("[red]Quantity cannot be negative.[/red]")
                InputSafe.pause()
                return
            
            account.holdings[ticker] = quantity
            self.console.print(f"[green]Successfully set {ticker} to {quantity:,.4f} shares.[/green]")
            DataHandler.save_clients(self.clients) # Auto-save

        except ValueError:
            self.console.print("[red]Invalid input format.[/red]")
        
        InputSafe.pause()

    def remove_holding_workflow(self, account: Account):
        ticker = self.console.input("\n[bold cyan]Enter Ticker to Remove:[/bold cyan] ").strip().upper()
        if ticker in account.holdings:
            del account.holdings[ticker]
            self.console.print(f"[green]Removed {ticker}.[/green]")
            DataHandler.save_clients(self.clients)
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
        
        risk = InputSafe.get_option(["Conservative", "Moderate", "Aggressive"], prompt_text="Risk Profile:")
        
        new_client = Client(name=name, risk_profile=risk)
        new_client.accounts.append(Account(account_name="Primary Brokerage"))
        
        self.clients.append(new_client)
        DataHandler.save_clients(self.clients)
        self.console.print(f"[green]Client created with ID: {new_client.client_id[:8]}[/green]")
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