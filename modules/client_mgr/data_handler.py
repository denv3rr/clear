import json
import os
from typing import List, Dict, Any
from rich.console import Console

from modules.client_mgr.client_model import Client

class DataHandler:
    """Handles persistence for client data (saving and loading)."""
    
    CLIENT_FILE = os.path.join("data", "clients.json")
    console = Console()


    @staticmethod
    def _migrate_clients_payload(payload: Any):
        if not isinstance(payload, list):
            return payload, False
        changed = False
        for client in payload:
            if not isinstance(client, dict):
                continue
            accounts = client.get("accounts", [])
            if not isinstance(accounts, list):
                continue
            for account in accounts:
                if not isinstance(account, dict):
                    continue
                lots = account.get("lots", {})
                if not isinstance(lots, dict):
                    continue
                for lot_list in lots.values():
                    if not isinstance(lot_list, list):
                        continue
                    for lot in lot_list:
                        if not isinstance(lot, dict):
                            continue
                        ts = lot.get("timestamp")
                        date_val = lot.get("date")
                        ts_clean = ts.strip() if isinstance(ts, str) else ""
                        new_ts = None
                        if not ts_clean or ts_clean.upper() == "LEGACY":
                            if isinstance(date_val, str) and date_val.strip():
                                new_ts = date_val.strip()
                        else:
                            new_ts = ts_clean
                        if isinstance(new_ts, str) and new_ts:
                            if " " in new_ts and "T" not in new_ts:
                                parts = new_ts.split()
                                if len(parts) >= 2:
                                    new_ts = parts[0] + "T" + parts[1]
                            if len(new_ts) == 10 and "-" in new_ts:
                                new_ts = new_ts + "T00:00:00"
                            if ts != new_ts:
                                lot["timestamp"] = new_ts
                                changed = True
        return payload, changed
    
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
            data, migrated = DataHandler._migrate_clients_payload(data)
            if migrated:
                with open(DataHandler.CLIENT_FILE, 'w') as wf:
                    json.dump(data, wf, indent=4)
                DataHandler.console.print("[dim]Normalized legacy lot timestamps to ISO-8601.[/dim]")
            
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