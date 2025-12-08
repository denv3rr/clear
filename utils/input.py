from rich.console import Console
from rich.prompt import Prompt, IntPrompt, Confirm

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
                # We use specific styling for the input prompt
                selection = Prompt.ask(f"[bold gold1]{prompt_text}[/bold gold1]", choices=None)
                
                # Check against valid list
                if selection.lower() in choices_str:
                    return selection.lower()
                
                console.print(f"[red]Invalid selection. Options: {valid_choices}[/red]")
            
            except KeyboardInterrupt:
                console.print("\n[yellow]Navigation Interrupted. Returning...[/yellow]")
                return "back"

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
    def pause(message: str = "Press Enter to continue..."):
        """Standard 'Wait' block."""
        console.print(f"\n[dim]{message}[/dim]")
        input("")