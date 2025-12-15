from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
import os
from typing import Optional, Tuple, Dict, Any, List

console = Console()

class InputSafe:
    """
    Static utility for handling user input safely and consistently.
    Wraps Rich's Prompt classes to ensure valid data types.
    """

    @staticmethod
    def get_option(valid_choices: list, prompt_text: str = "SELECT MODULE") -> str:
        """
        Forces the user to pick one of the valid strings/numbers in the list.
        Case-insensitive.
        """
        # Convert all valid choices to string for comparison
        choices_str = [str(c).lower() for c in valid_choices]
        
        while True:
            try:
                selection = Prompt.ask(f"[bold gold1]{prompt_text}[/bold gold1]", choices=None)
                
                # Check against valid list
                if selection.lower() in choices_str:
                    return selection.lower()
                
                console.print(f"[red]Invalid selection. Options: {valid_choices}[/red]")
            
            except KeyboardInterrupt:
                # For Windows
                if os.name == 'nt':
                    _ = os.system('cls')
                # For macOS and Linux
                else:
                    _ = os.system('clear')
                console.print("\n\n[yellow]>> Interrupted. Exiting for safety...[/yellow]")
                console.print("[dim]   Data saved.\n   Connections terminated.\n   Logs cleared from terminal.[/dim]\n")
                exit(0)

    @staticmethod
    def get_string(prompt_text: str = "") -> str: # <-- New method added
        """Gets a safe, free-form string input from the user."""
        try:
            # Using Prompt.ask for Rich formatting consistency
            return Prompt.ask(f"[cyan]{prompt_text}[/cyan]")
        except KeyboardInterrupt:
            console.print("\nInput cancelled.")
            return ""


    @staticmethod
    def get_float(prompt_text: str, min_val: float = None, max_val: float = None) -> float:
        """Gets a safe float (money, percentages)."""
        while True:
            try:
                val = float(Prompt.ask(f"[cyan]{prompt_text}[/cyan]"))
                if min_val is not None and val < min_val:
                    console.print(f"[red]Value must be at least {min_val}[/red]")
                    continue
                if max_val is not None and val > max_val:
                    console.print(f"[red]Value must be under {max_val}[/red]")
                    continue
                return val
            except ValueError:
                console.print("[red]Please enter a valid number (e.g. 10.50)[/red]")

    @staticmethod
    def get_yes_no(prompt_text: str, default: Optional[bool] = None) -> bool:
        """
        Prompts the user for a Yes/No input.
        Returns True for Yes, False for No.
        """
        console = Console()
        while True:
            # Append [y/n] to the prompt for clarity
            response = console.input(f"{prompt_text} [bold yellow](y/n):[/bold yellow] ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                console.print("[red]Invalid input. Please enter 'y' or 'n'.[/red]")

    @staticmethod
    def pause(message: str = "Press Enter to continue..."):
        """Standard 'Wait' block."""
        console.print(f"\n[dim]{message}[/dim]")
        input("")

    @staticmethod
    def get_asset_input() -> Optional[Dict[str, Any]]:
        """
        Prompts user for robust asset input with flexible formats.
        
        Supported Formats:
        1. Ticker <Quantity> (e.g., 'NVDA 10', 'TSLA -5')
        2. Ticker (Asks for Quantity next - fulfilling user request)
        3. Custom:<Label> <Value> (e.g., 'Custom:GoldBar 50000', 'Custom:House 500000')
        
        Returns: {ticker, quantity, asset_type, manual_value} or None (if cancelled)
        """
        asset_input = Prompt.ask(
            "[bold cyan]Enter Ticker alone, 'Ticker Quantity', or 'Custom:Label Value'[/bold cyan] (Press Enter to Cancel)"
        ).strip()
        
        if not asset_input:
            return None

        # --- 1. Custom Asset Parsing ---
        if asset_input.lower().startswith("custom:"):
            try:
                # Format: Custom:Label Value (e.g. 'Custom:House 500000')
                parts = asset_input.split(":", 1)[1].strip().split()
                label = parts[0]
                value = InputSafe.get_float(f"Enter Manual Value for '{label}' (USD):", min_val=0.01)
                
                return {
                    "ticker": label.upper(),
                    "quantity": 1.0, 
                    "asset_type": "Custom",
                    "manual_value": value
                }
            except Exception:
                console.print("[red]Invalid custom asset format. Use 'Custom:Label'.[/red]")
                return InputSafe.get_asset_input()
        
        # --- 2. Ticker & Quantity Parsing ---
        parts = asset_input.split()
        
        if len(parts) == 2:
            ticker = parts[0].strip().upper()
            try:
                quantity = float(parts[1].strip())
            except ValueError:
                console.print("[red]Invalid quantity entered. Must be a number.[/red]")
                return InputSafe.get_asset_input()
        
        elif len(parts) == 1:
            # User entered Ticker alone (Request: Ticker alone)
            ticker = parts[0].strip().upper()
            console.print(f"[dim]You entered Ticker: {ticker}[/dim]")
            
            # Prompt for quantity
            quantity = InputSafe.get_float("Enter Quantity (e.g. 10 or -5 for short):", min_val=None)
            
        else:
            console.print("[red]Invalid format. Try 'NVDA 10' or 'Custom:House'.[/red]")
            return InputSafe.get_asset_input()

        # Determine Asset Type (Basic logic)
        asset_type = "Equity"
        if ticker.endswith(('P', 'C', 'p', 'c')) and len(ticker) > 2:
             asset_type = "Derivative:Option"
        
        # Handle Shorting (Request: Shorts)
        if quantity < 0 and asset_type == "Equity": 
            asset_type = "Equity:Short" 
            
        return {
            "ticker": ticker,
            "quantity": quantity,
            "asset_type": asset_type,
            "manual_value": None
        }