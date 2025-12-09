import json
import os
from typing import List
from rich.console import Console

from modules.client_mgr.client_model import Client

class DataHandler:
    """Handles persistence for client data (saving and loading)."""
    
    CLIENT_FILE = os.path.join("data", "clients.json")
    console = Console()
    
    @staticmethod
    def _create_initial_files():
        """Creates the data directory and an empty client file if they don't exist."""
        data_dir = os.path.dirname(DataHandler.CLIENT_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        if not os.path.exists(DataHandler.CLIENT_FILE):
            try:
                with open(DataHandler.CLIENT_FILE, 'w') as f:
                    json.dump([], f) # Start with an empty list
                DataHandler.console.print(f"[dim]Initial client data file created at {DataHandler.CLIENT_FILE}[/dim]")
            except Exception as e:
                DataHandler.console.print(f"[red]CRITICAL: Could not create data file. {e}[/red]")

    @staticmethod
    def load_clients() -> List[Client]:
        """Loads all clients from the JSON file."""
        DataHandler._create_initial_files()
        
        try:
            with open(DataHandler.CLIENT_FILE, 'r') as f:
                data = json.load(f)
            
            # Reconstruct Client objects from the list of dictionaries
            clients = [Client.from_dict(d) for d in data]
            return clients
            
        except FileNotFoundError:
            return []
        except json.JSONDecodeError:
            DataHandler.console.print("[red]Warning: Client data file is corrupt. Starting fresh.[/red]")
            return []
        except Exception as e:
            DataHandler.console.print(f"[red]Error loading client data: {e}[/red]")
            return []

    @staticmethod
    def save_clients(clients: List[Client]):
        """Saves the current list of Client objects to the JSON file."""
        DataHandler._create_initial_files()
        
        try:
            # Convert list of Client objects back to a list of serializable dictionaries
            data_to_save = [c.to_dict() for c in clients]
            
            with open(DataHandler.CLIENT_FILE, 'w') as f:
                # Use indent for readability in the data folder
                json.dump(data_to_save, f, indent=4)
            
            DataHandler.console.print("[dim green]Client data saved successfully.[/dim green]")
            
        except Exception as e:
            DataHandler.console.print(f"[red]CRITICAL: Could not save client data. {e}[/red]")