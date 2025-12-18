import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Account:
    """A single investment account held by a client."""
    account_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_name: str = "Brokerage Account"
    account_type: str = "Taxable"
    current_value: float = 0.0

    active_interval: str = "1M"

    holdings: Dict[str, float] = field(default_factory=dict)

    # Manual/off-market holdings (estimated). Each item can contain:
    # name, quantity, unit_price, total_value, currency, notes
    manual_holdings: List[Dict[str, Any]] = field(default_factory=list)

    # Lot-based structure: { "TICKER": [ {"qty": float, "basis": float, "timestamp": "YYYY-MM-DD | H:M:S"}, ... ] }
    lots: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    def sync_holdings_from_lots(self):
        """Calculates aggregate holdings quantity from the sum of all lots.

        This function is intentionally conservative:
        - It recomputes quantities for any ticker present in self.lots.
        - It does not delete legacy holdings entries for tickers that have no lots yet.
        - It normalizes tickers to uppercase to prevent duplicate keys (e.g., 'aapl' vs 'AAPL').
        """
        
        new_holdings = dict(self.holdings or {})
        lots_map = self.lots if isinstance(self.lots, dict) else {}
        for raw_ticker, lot_list in lots_map.items():
            ticker = str(raw_ticker).strip().upper()
            total_qty = 0.0
            if isinstance(lot_list, list):
                for lot in lot_list:
                    if not isinstance(lot, dict):
                        continue
                    try:
                        total_qty += float(lot.get('qty', 0.0) or 0.0)
                    except Exception:
                        continue
            new_holdings[ticker] = float(total_qty)
        self.holdings = new_holdings

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Client":
        client = Client(
            client_id=data.get("client_id", str(uuid.uuid4())),
            name=data.get("name", "New Client"),
            risk_profile=data.get("risk_profile", "Moderate"),
            active_interval=data.get("active_interval", "1M"),
            accounts=[]
        )

        for acc_data in data.get("accounts", []):
            # -----------------------------
            # LOT MIGRATION
            # -----------------------------
            raw_lots = acc_data.get("lots", {}) or {}
            normalized_lots: Dict[str, List[Dict[str, Any]]] = {}

            for raw_ticker, lot_list in raw_lots.items():
                ticker = str(raw_ticker).strip().upper()
                fixed_lots = []

                for lot in lot_list or []:
                    if not isinstance(lot, dict):
                        continue

                    # Backfill missing timestamp
                    if not lot.get("timestamp"):
                        lot["timestamp"] = "LEGACY"

                    fixed_lots.append(lot)

                normalized_lots[ticker] = fixed_lots

            client.accounts.append(
                Account(
                    account_id=acc_data.get("account_id", str(uuid.uuid4())),
                    account_name=acc_data.get("account_name", "Brokerage Account"),
                    account_type=acc_data.get("account_type", "Taxable"),
                    current_value=acc_data.get("current_value", 0.0),
                    holdings=acc_data.get("holdings", {}) or {},
                    manual_holdings=acc_data.get("manual_holdings", []) or [],
                    active_interval=acc_data.get(
                        "active_interval",
                        data.get("active_interval", "1M")
                    ),
                    lots=normalized_lots,
                )
            )

        return client

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": self.account_type,
            "current_value": self.current_value,
            "holdings": self.holdings,
            "lots": self.lots,
            "manual_holdings": self.manual_holdings,
            "active_interval": self.active_interval
        }


@dataclass
class Client:
    """Client model storing accounts and profile."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Client"
    risk_profile: str = "Moderate"
    active_interval: str = "1M"
    accounts: List[Account] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "risk_profile": self.risk_profile,
            "active_interval": self.active_interval,
            "accounts": [a.to_dict() for a in self.accounts]
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Client":
        client = Client(
            client_id=data.get("client_id", str(uuid.uuid4())),
            name=data.get("name", "New Client"),
            risk_profile=data.get("risk_profile", "Moderate"),
            active_interval=data.get("active_interval", "1M"),
            accounts=[]
        )

        for acc_data in data.get("accounts", []):
            client.accounts.append(
                Account(
                    account_id=acc_data.get("account_id", str(uuid.uuid4())),
                    account_name=acc_data.get("account_name", "Brokerage Account"),
                    account_type=acc_data.get("account_type", "Taxable"),
                    current_value=acc_data.get("current_value", 0.0),
                    holdings=acc_data.get("holdings", {}) or {},
                    manual_holdings=acc_data.get("manual_holdings", []) or [],
                    active_interval=acc_data.get("active_interval", data.get("active_interval", "1M")),
                    lots=acc_data.get("lots", {}) or {},
                )
            )

        return client
