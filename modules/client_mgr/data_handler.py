import json
import os
from typing import List, Dict, Any
from rich.console import Console

from modules.client_mgr.client_model import Client
from modules.client_mgr.payloads import normalize_clients_payload
from modules.client_store import DbClientStore, bootstrap_clients_from_json

class DataHandler:
    """Handles persistence for client data (saving and loading)."""
    
    CLIENT_FILE = os.path.join("data", "clients.json")
    console = Console()


    @staticmethod
    def _migrate_clients_payload(payload: Any):
        return normalize_clients_payload(payload)
    
    @staticmethod
    def _create_initial_files():
        """Creates the data directory and an empty client file if they don't exist."""
        data_dir = os.path.dirname(DataHandler.CLIENT_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        if not os.path.exists(DataHandler.CLIENT_FILE):
            try:
                with open(DataHandler.CLIENT_FILE, 'w') as f:
                    json.dump([], f)
                DataHandler.console.print(f"[dim]Initial client data file created at {DataHandler.CLIENT_FILE}[/dim]")
            except Exception as e:
                DataHandler.console.print(f"[red]CRITICAL: Could not create data file. {e}[/red]")

    @staticmethod
    def load_clients() -> List[Client]:
        """Loads all clients from the database."""
        try:
            bootstrap_clients_from_json()
            store = DbClientStore()
            payloads = store.fetch_all_clients()
            return [Client.from_dict(d) for d in payloads]
        except Exception as e:
            DataHandler.console.print(f"[red]Error loading client data: {e}[/red]")
            return []

    @staticmethod
    def save_clients(clients: List[Client]):
        """Saves the current list of Client objects to the database."""
        try:
            store = DbClientStore()
            store.sync_clients([c.to_dict() for c in clients])
            DataHandler.console.print("[dim green]Client data saved successfully.[/dim green]")
        except Exception as e:
            DataHandler.console.print(f"[red]CRITICAL: Could not save client data. {e}[/red]")

    @staticmethod
    def export_clients_json(clients: List[Client]):
        """Exports the current list of Client objects to JSON."""
        DataHandler._create_initial_files()
        data_to_save = [c.to_dict() for c in clients]
        with open(DataHandler.CLIENT_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=4)
