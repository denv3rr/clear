from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.text import Text

import os

from typing import Optional, Tuple, Dict, Any, List

console = Console()

class InputSafe:
    """
    Static utility for handling user input safely and consistently.
    Wraps Rich's Prompt classes to ensure valid data types.
    """

    @staticmethod
    def format_key(key: str) -> str:
        """
        Formats a key (e.g., '1', '2', '0') with the standard blue brackets 
        and bold gold1 key color for consistent menu display.
        Example: "[1]" -> "[blue][[/blue][bold gold1]1[/bold gold1][blue]][/blue]"
        """
        return f"[blue][[/blue][bold gold1]{key}[/bold gold1][blue]][/blue]"

    @staticmethod
    def display_options(options: Dict[str, str], title: str = None):
        """
        Modular menu renderer. 
        Prints a list of options using the standardized application style.
        
        Args:
            options: Dict where Key is the input char and Value is the description.
                        e.g. {"1": "File Settings", "0": "Back"}
            title: Optional header text to print before options.
        """
        if title:
            console.print(f"\n[bold white]{title}[/bold white]")
        else:
            console.print("")

        for key, description in options.items():
            formatted_key = InputSafe.format_key(key)
            console.print(f"{formatted_key} [white]{description}[/white]")
        
        console.print("")

    @staticmethod
    def get_option(valid_choices: list, prompt_text: str = "SELECT MODULE") -> str:
        """
        Forces the user to pick one of the valid strings/numbers in the list.
        Case-insensitive.
        """
        # Convert all valid choices to string for comparison
        choices_str = [str(c).lower() for c in valid_choices]
        
        # Handle rich.text.Text for pre-formatted/padded prompts
        if isinstance(prompt_text, str):
            prompt = Text.from_markup(prompt_text)
        # If it's already a Text object (from menus.py), use it as is
        else:
            prompt = prompt_text
        
        while True:
            try:
                selection = Prompt.ask(prompt, choices=None)
                
                if selection.lower() in choices_str:
                    return selection.lower()
                
                formatted_keys = " / ".join([InputSafe.format_key(c) for c in valid_choices])
                console.print(f"[red]Invalid selection. Options: {formatted_keys}[/red]")
            
            except KeyboardInterrupt:
                if os.name == 'nt': os.system('cls')
                else: os.system('clear')
                console.print("\n\n[yellow]>> Interrupted. Exiting...[/yellow]")
                exit(0)

    @staticmethod
    def get_string(prompt_text: str = "") -> str:
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
        Prompts user for asset input with more flexible formats.
        
        Supported Formats:
        1. Ticker <Quantity> (e.g., 'NVDA 10', 'TSLA -5')
        2. Ticker (Asks for Quantity explicitly next)
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
                # Format: Custom:Label Value
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
            # User entered Ticker alone
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