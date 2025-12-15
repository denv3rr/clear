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

    holdings: Dict[str, float] = field(default_factory=dict)

    # Manual/off-market holdings (estimated). Each item can contain:
    # name, quantity, unit_price, total_value, currency, notes
    manual_holdings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": self.account_type,
            "current_value": self.current_value,
            "holdings": self.holdings,
            "manual_holdings": self.manual_holdings,
        }


@dataclass
class Client:
    """A single client record with one or more accounts."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Client"
    risk_profile: str = "Moderate"
    calculated_risk: str = "N/A"
    accounts: List[Account] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "risk_profile": self.risk_profile,
            "calculated_risk": self.calculated_risk,
            "accounts": [a.to_dict() for a in self.accounts],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Client":
        client = Client(
            client_id=data.get("client_id", str(uuid.uuid4())),
            name=data.get("name", "New Client"),
            risk_profile=data.get("risk_profile", "Moderate"),
            calculated_risk=data.get("calculated_risk", "N/A"),
            accounts=[],
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
                )
            )

        return client
