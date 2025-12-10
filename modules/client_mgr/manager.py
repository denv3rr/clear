from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.align import Align
from rich.text import Text
from typing import Optional, Tuple, List 

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
        # Case-insensitive partial matching (using startswith for user-friendliness)
        return next((c for c in self.clients if c.client_id.startswith(client_id)), None)

    # --- MAIN VIEW ---

    def run(self):
        """Main loop for the Client Management Module."""
        while True:
            self.console.clear()
            self.display_client_list()

            self.console.print("\n")
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
                self.delete_client_workflow() # NEW: Delete workflow

    # --- CLIENT LIST VIEW ---
    
    def display_client_list(self):
        """Renders the list of current clients with summary data."""
        table = Table(title="[bold gold1]Clients[/bold gold1]", box=box.ROUNDED, width=100, )
        table.add_column("Client ID", style="dim", width=10)
        table.add_column("Name", style="bold white")
        table.add_column("Risk Profile", style="yellow")
        table.add_column("Total Value", style="green", justify="right")
        table.add_column("# Accounts", style="dim", justify="right")
        
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

    # --- CLIENT DASHBOARD VIEW (Split into helpers) ---
    
    def _build_client_details_panel(self, client: Client) -> Panel:
        """Helper to build the client's name/risk profile panel."""
        details_grid = Table.grid(padding=(0,1))
        details_grid.add_column(style="bold yellow")
        details_grid.add_column(style="white")
        details_grid.add_row("Client ID:", client.client_id)
        details_grid.add_row("Name:", client.name)
        details_grid.add_row("Risk Profile:", client.risk_profile)
        
        return Panel(details_grid, title="[bold blue]CLIENT DETAILS[/bold blue]", box=box.ROUNDED)

    def _build_account_summary_table(self, client: Client) -> Tuple[Table, float]:
        """Helper to build the account summary table and return the total value."""
        summary_table = Table(
            title="[bold gold1]Account & Portfolio Summary[/bold gold1]",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        summary_table.add_column("ID", style="dim", width=10)
        summary_table.add_column("Account Name")
        summary_table.add_column("Type")
        summary_table.add_column("Market Value", style="green", justify="right")
        
        total_portfolio_value = 0.0
        
        for account in client.accounts:
            # Recalculate value before displaying
            total_value = self._recalculate_account_value(account) 
            total_portfolio_value += total_value

            summary_table.add_row(
                account.account_id[:8],
                account.account_name,
                account.account_type,
                f"${total_value:,.2f}"
            )
        
        return summary_table, total_portfolio_value

    def display_client_dashboard(self, client: Client):
        """
        Composes and displays the client's main dashboard with sequential, centered layout.
        """
        
        # 1. Title Bar
        title = Text(f"CLIENT DASHBOARD: {client.name} (ID: {client.client_id[:8]})", style="bold yellow")
        self.console.print(Align.center(title), "\n")
        
        # 2. Client Details Panel
        info_panel = self._build_client_details_panel(client)
        self.console.print(Align.center(info_panel))

        # 3. Account Summary Table and Total Value Calculation
        account_summary_table, total_portfolio_value = self._build_account_summary_table(client)
        
        # 4. Total Portfolio Value Panel
        total_panel = Panel(
            f"[bold white]Total Portfolio Value: [/bold white][bold green]${total_portfolio_value:,.2f}[/bold green]", 
            border_style="green", 
            padding=(0,1)
        )
        self.console.print(Align.center(total_panel), "\n")
        
        # 5. Account Summary Table
        self.console.print(Align.center(account_summary_table), "\n")
        
        # 6. Divider 
        self.console.rule("[dim]DASHBOARD ACTIONS[/dim]")

    # --- WORKFLOW METHODS ---

    def select_client_workflow(self):
        """Prompts for client ID and launches the dashboard if found."""
        client_id_input = self.console.input("[bold cyan]Enter Client ID (partial match allowed):[/bold cyan] ").strip()
        client = self._get_client_by_id(client_id_input)
        
        if client:
            self.client_dashboard_loop(client)
        else:
            self.console.print(f"[red]Error: Client with ID starting '{client_id_input}' not found.[/red]")
            InputSafe.pause()

    def delete_client_workflow(self):
        """Prompts for client ID and deletes the client after confirmation."""
        self.console.clear()
        self.console.print("[bold red]WARNING: THIS ACTION IS PERMANENT.[/bold red]")
        client_id_input = self.console.input("[bold cyan]Enter Client ID (partial match allowed) to DELETE:[/bold cyan] ").strip()
        client_to_delete = self._get_client_by_id(client_id_input)
        
        if not client_to_delete:
            self.console.print(f"[red]Error: Client with ID starting '{client_id_input}' not found.[/red]")
            InputSafe.pause()
            return
            
        confirm_text = f"Are you sure you want to PERMANENTLY delete client '{client_to_delete.name}' ({client_to_delete.client_id[:8]})? (y/n)"
        if InputSafe.get_yes_no(prompt_text=confirm_text, default="n"):
            self.clients = [c for c in self.clients if c.client_id != client_to_delete.client_id]
            DataHandler.save_clients(self.clients)
            self.console.print(f"\n[green]Client '{client_to_delete.name}' deleted successfully.[/green]")
        else:
            self.console.print("\n[yellow]Client deletion aborted.[/yellow]")
            
        InputSafe.pause()

    def add_client_workflow(self):
        """Prompts for new client details and adds them to the list."""
        name = self.console.input("[bold cyan]Enter Client Name:[/bold cyan] ").strip()
        if not name:
            self.console.print("[red]Client name cannot be empty. Aborting.[/red]")
            InputSafe.pause()
            return

        risk_profile = InputSafe.get_option(
            ["Conservative", "Moderate", "Aggressive"], 
            prompt_text="[bold cyan]Select Risk Profile (Conservative/Moderate/Aggressive):[/bold cyan] "
        )

        new_client = Client(name=name, risk_profile=risk_profile)
        new_client.accounts.append(Account(account_name=f"Primary"))
        self.clients.append(new_client)
        
        self.console.print(f"\n[green]Client '{name}' added with ID: {new_client.client_id[:8]}[/green]")
        DataHandler.save_clients(self.clients)
        InputSafe.pause()

    def edit_client_workflow(self, client: Client):
        """Allows editing of client's name and risk profile."""
        
        new_name = self.console.input(f"[bold cyan]Enter New Name (Current: {client.name}, Leave blank to skip):[/bold cyan] ").strip()
        if new_name:
            client.name = new_name
            self.console.print(f"[green]Name updated to: {client.name}[/green]")
        
        valid_options = ["Conservative", "Moderate", "Aggressive"]
        valid_options_lower = [r.lower() for r in valid_options]
        
        new_risk_input = self.console.input(
            f"[bold cyan]Enter New Risk Profile ({'/'.join(valid_options)}) [Current: {client.risk_profile}, Leave blank to skip]:[/bold cyan] "
        ).strip()
        
        if new_risk_input:
            if new_risk_input.lower() in valid_options_lower:
                canonical_risk = valid_options[valid_options_lower.index(new_risk_input.lower())]
                client.risk_profile = canonical_risk
                self.console.print(f"[green]Risk Profile updated to: {client.risk_profile}[/green]")
            else:
                self.console.print(f"[red]Error: '{new_risk_input}' is not a valid risk profile. Profile was not updated.[/red]")
            
        DataHandler.save_clients(self.clients)
        InputSafe.pause()

    def client_dashboard_loop(self, client: Client):
        """Displays a specific client's portfolio dashboard and manages client actions."""
        while True:
            self.console.clear()
            self.display_client_dashboard(client)
            
            self.console.print(f"\n[bold gold1]CLIENT | {client.name}[/bold gold1]")
            self.console.print("[1] 📝 Edit Client Details (Name, Risk Profile)")
            self.console.print("[2] 💰 Manage Accounts (Select/Add/Edit Holdings)")
            self.console.print("[0] 🔙 Return to Clients")
            
            choice = InputSafe.get_option(["1", "2", "0"], prompt_text="[>]")
            
            if choice == "0":
                DataHandler.save_clients(self.clients)
                break
            elif choice == "1":
                self.edit_client_workflow(client)
            elif choice == "2":
                self.manage_accounts_workflow(client)
                
    # --- ACCOUNT MANAGEMENT HELPERS ---
    
    def _select_account(self, client: Client) -> Optional[Account]:
        """Helper to display accounts and prompt for selection/account list actions."""
        options = []
        
        self.console.print(f"\n[bold gold1]ALL ACCOUNTS | {client.name}[/bold gold1]")
        
        account_table = Table(box=box.SIMPLE, show_header=True)
        account_table.add_column("#", style="bold yellow")
        account_table.add_column("ID", style="dim")
        account_table.add_column("Account Name", style="white")
        account_table.add_column("Type", style="cyan")
        account_table.add_column("Value", justify="right", style="green")
        
        for i, acc in enumerate(client.accounts, 1):
            # Recalculate value before listing
            self._recalculate_account_value(acc)
            options.append(str(i))
            account_table.add_row(
                str(i),
                acc.account_id[:8],
                acc.account_name,
                acc.account_type,
                f"${acc.current_value:,.2f}"
            )
            
        self.console.print(Align.center(account_table))

        self.console.print("\n\n[bold gold1]MENU[/bold gold1]")
        self.console.print(f"[1] 📝 Select Account")
        self.console.print(f"[2] ➕ Add Account")
        self.console.print(f"[3] ➖ Remove Account [bold red]![/bold red]")
        self.console.print("[0] 🔙 Return to Client Dashboard")

        valid_options = options + ["1", "2", "3", "0"]
        choice = InputSafe.get_option(valid_options, prompt_text="[>]").upper()
        
        InputSafe.set_last_choice(choice) # Store choice for manage_accounts_workflow to check

        if choice == "1":
            self.console.print("[yellow][ TO ADD | SELECT ACCOUNT TO MANAGE BY NAME OR CLIENT ACCOUNT INDEX [1-accounts] ][/yellow]")
            return None
        elif choice == "2":
            self.add_account_workflow(client)
            return None
        elif choice == "3":
            self.remove_account_workflow(client)
            return None
        elif choice == "0":
            self.console.print("[yellow][ TO ADD | RETURN TO DASHBOARD ][/yellow]")
            return None
        else: # Selected an account index
            try:
                account_index = int(choice) - 1
                return client.accounts[account_index]
            except:
                self.console.print("[red]Invalid account selection. Try again.[/red]")
                InputSafe.pause()
                return None
                
    def manage_accounts_workflow(self, client: Client):
        """Allows selection of an account to manage its holdings/details, or manage the account list."""
        while True:
            self.console.clear()

            # Display and select account, or choose account list actions
            selected_account = self._select_account(client)
            
            if selected_account is None:
                # If selection was '0', break the loop
                if InputSafe.last_choice().upper() == "0":
                    break
                else: # Was 'A' or 'R' or invalid selection, continue the loop
                    continue
            
            # Account was selected, now manage holdings for it
            self.manage_holdings_loop(client, selected_account)

    def manage_holdings_loop(self, client: Client, account: Account):
        """Dedicated loop for managing holdings and editing account details for a single selected account."""
        while True:
            self.console.clear()
            # FIX: Title now uses the current account name
            self.console.print(f"[bold blue]Client:[/bold blue] {client.name} | [bold blue]Account:[/bold blue] {account.account_name}") 
            self.display_account_holdings(account)

            self.console.print("\n[bold gold1]HOLDING/ACCOUNT ACTIONS:[/bold gold1]")
            self.console.print("[1] 📝 Edit Account Name/Type") # NEW: Edit Account Details
            self.console.print("[2] ➕ Add/Update Holding")
            self.console.print("[3] ➖ Remove Holding")
            self.console.print("[0] 🔙 Return to Account List")
            
            choice = InputSafe.get_option(["1", "2", "3", "0"], prompt_text="SELECT ACTION >")

            if choice == "0":
                break
            elif choice == "1":
                self.edit_account_workflow(account) # New workflow
            elif choice == "2":
                self.add_holding_workflow(account)
            elif choice == "3":
                self.remove_holding_workflow(account)


    def add_account_workflow(self, client: Client):
        """Prompts for new account details and adds it to the client."""
        self.console.clear()
        self.console.print(f"[bold blue]Adding New Account for: {client.name}[/bold blue]\n")
        
        account_name = self.console.input("[bold cyan]Enter Account Name (e.g., IRA, Second Brokerage):[/bold cyan] ").strip()
        if not account_name:
            self.console.print("[red]Account name cannot be empty. Aborting.[/red]")
            InputSafe.pause()
            return
            
        account_type = InputSafe.get_option(
            ["Taxable", "IRA", "401k", "Trust"], 
            prompt_text="[bold cyan]Select Account Type (Taxable/IRA/401k/Trust):[/bold cyan] "
        )

        new_account = Account(account_name=account_name, account_type=account_type)
        client.accounts.append(new_account)
        
        self.console.print(f"\n[green]Account '{account_name}' added successfully.[/green]")
        DataHandler.save_clients(self.clients)
        InputSafe.pause()

    def edit_account_workflow(self, account: Account):
        """Allows editing of account name and type."""
        self.console.clear()
        self.console.print(f"[bold blue]Editing Account: {account.account_name}[/bold blue]\n")

        # Edit Name
        new_name = self.console.input(f"[bold cyan]Enter New Name (Current: {account.account_name}, Leave blank to skip):[/bold cyan] ").strip()
        if new_name:
            account.account_name = new_name
            self.console.print(f"[green]Account Name updated to: {account.account_name}[/green]")
        
        # Edit Type
        valid_types = ["Taxable", "IRA", "401k", "Trust"]
        valid_types_lower = [t.lower() for t in valid_types]
        
        new_type_input = self.console.input(
            f"[bold cyan]Enter New Account Type ({'/'.join(valid_types)}) [Current: {account.account_type}, Leave blank to skip]:[/bold cyan] "
        ).strip()
        
        if new_type_input:
            if new_type_input.lower() in valid_types_lower:
                canonical_type = valid_types[valid_types_lower.index(new_type_input.lower())]
                account.account_type = canonical_type
                self.console.print(f"[green]Account Type updated to: {account.account_type}[/green]")
            else:
                self.console.print(f"[red]Error: '{new_type_input}' is not a valid account type. Type was not updated.[/red]")
            
        DataHandler.save_clients(self.clients)
        InputSafe.pause()

    def remove_account_workflow(self, client: Client):
        """Prompts for an account index and removes it after confirmation."""
        
        self.console.clear()
        if not client.accounts:
            self.console.print("[red]No accounts to remove.[/red]")
            InputSafe.pause()
            return

        self.console.print(f"[bold red]Removing Account for: {client.name}[/bold red]")
        
        # Build options table
        options = []
        account_table = Table(box=box.SIMPLE, show_header=True)
        account_table.add_column("#", style="bold yellow")
        account_table.add_column("Account Name", style="white")
        account_table.add_column("Holdings", justify="right", style="dim")
        
        for i, acc in enumerate(client.accounts, 1):
            options.append(str(i))
            holdings_count = len(acc.holdings)
            account_table.add_row(
                str(i),
                acc.account_name,
                f"{holdings_count} item{'s' if holdings_count != 1 else ''}"
            )
        self.console.print(Align.center(account_table))
        
        
        choice = InputSafe.get_option(options, prompt_text="[bold cyan]Select account number to PERMANENTLY DELETE (or 'b' to cancel):[/bold cyan]", allow_back=True)
        
        if choice.lower() == 'b':
            return

        try:
            account_index = int(choice) - 1
            account_to_delete = client.accounts[account_index]
        except (ValueError, IndexError):
            self.console.print("[red]Invalid selection. Aborting removal.[/red]")
            InputSafe.pause()
            return
            
        confirm_text = f"Are you sure you want to PERMANENTLY delete account '{account_to_delete.account_name}'? This cannot be undone. (y/n)"
        if InputSafe.get_yes_no(prompt_text=confirm_text, default="n"):
            del client.accounts[account_index]
            DataHandler.save_clients(self.clients)
            self.console.print(f"\n[green]Account '{account_to_delete.account_name}' deleted successfully.[/green]")
        else:
            self.console.print("\n[yellow]Account deletion aborted.[/yellow]")
            
        InputSafe.pause()

                
    def display_account_holdings(self, account: Account):
        """Renders the detailed holdings for a specific account."""
        
        # FIX: Ensure holdings table title uses the current account name
        holdings_table = Table(title=f"[bold gold1]Holdings for {account.account_name}[/bold gold1]", box=box.SIMPLE)
        holdings_table.add_column("Ticker", style="bold white", width=10)
        holdings_table.add_column("Quantity", justify="right")
        holdings_table.add_column("Market Value", style="green", justify="right")
        
        # Ensure we have the latest valuation data
        total_value, valued_holdings = self.valuation_engine.calculate_portfolio_value(account.holdings)
        
        for ticker, quantity in account.holdings.items():
            market_value = valued_holdings.get(ticker, 0.0)
            
            holdings_table.add_row(
                ticker,
                f"{quantity:,.4f}",
                f"${market_value:,.2f}"
            )
            
        self.console.print(Align.center(holdings_table))
        
        # Print the total value separately for emphasis
        self.console.print(Align.center(Panel(
            f"[bold white]Account Value:[/bold white] [bold green]${total_value:,.2f}[/bold green]",
            border_style="cyan",
            padding=(0,1)
        )))

    def add_holding_workflow(self, account: Account):
        """Prompts for a ticker and quantity to add or update a holding."""
        self.console.print("\n[dim]Enter Ticker and Quantity (e.g., AAPL, 10.5)[/dim]")
        
        try:
            raw_input = self.console.input("[bold cyan]Ticker, Quantity:[/bold cyan] ").strip()
            ticker, quantity_str = [x.strip() for x in raw_input.split(',')]
            
            ticker = ticker.upper()
            quantity = float(quantity_str)
            if quantity < 0: raise ValueError
            
            account.holdings[ticker] = quantity
            
            # Recalculate value immediately after successful holding update
            self._recalculate_account_value(account)
            
            self.console.print(f"[green]Holding updated: {ticker} to {quantity:,.4f} shares. Account value recalculated.[/green]")

        except ValueError:
            self.console.print("[red]Invalid format. Use 'TICKER, QUANTITY' where quantity is a positive number.[/red]")
        except Exception as e:
            self.console.print(f"[red]An unexpected error occurred: {e}[/red]")
            
        InputSafe.pause()

    def remove_holding_workflow(self, account: Account):
        """Prompts for a ticker to remove a holding."""
        self.console.print("\n[dim]Enter the Ticker to remove (e.g., AAPL)[/dim]")
        ticker = self.console.input("[bold cyan]Ticker to Remove:[/bold cyan] ").strip().upper()
        
        if ticker in account.holdings:
            del account.holdings[ticker]
            
            # Recalculate value immediately after successful holding update
            self._recalculate_account_value(account)
            
            self.console.print(f"[green]Holding {ticker} removed successfully. Account value recalculated.[/green]")
        else:
            self.console.print(f"[red]Ticker '{ticker}' not found in this account's holdings.[/red]")
        
        InputSafe.pause()