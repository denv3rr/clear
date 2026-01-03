import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any

from modules.client_mgr.holdings import normalize_ticker


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
    ownership_type: str = "Individual"
    custodian: str = ""
    tags: List[str] = field(default_factory=list)
    tax_settings: Dict[str, Any] = field(default_factory=lambda: {
        "jurisdiction": "",
        "account_currency": "USD",
        "withholding_rate": None,
        "tax_exempt": False,
    })
    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _normalize_lots(raw_lots: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        normalized: Dict[str, List[Dict[str, Any]]] = {}
        for raw_ticker, lot_list in (raw_lots or {}).items():
            ticker = normalize_ticker(raw_ticker)
            fixed_lots = []

            for lot in lot_list or []:
                if not isinstance(lot, dict):
                    continue
                if not lot.get("timestamp"):
                    lot["timestamp"] = "LEGACY"
                if not lot.get("kind"):
                    lot["kind"] = "lot"
                fixed_lots.append(lot)

            if fixed_lots:
                normalized[ticker] = fixed_lots

        return normalized

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
            ticker = normalize_ticker(raw_ticker)
            total_qty = 0.0
            if isinstance(lot_list, list):
                for lot in lot_list:
                    if not isinstance(lot, dict):
                        continue
                    try:
                        total_qty += float(lot.get("qty", 0.0) or 0.0)
                    except Exception:
                        continue
            new_holdings[ticker] = float(total_qty)
        self.holdings = new_holdings

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Account":
        lots = Account._normalize_lots(data.get("lots", {}) or {})

        holdings_raw = data.get("holdings", {}) or {}
        holdings: Dict[str, float] = {}
        for raw_ticker, qty in holdings_raw.items():
            ticker = normalize_ticker(raw_ticker)
            try:
                holdings[ticker] = holdings.get(ticker, 0.0) + float(qty or 0.0)
            except Exception:
                holdings[ticker] = holdings.get(ticker, 0.0)

        account = Account(
            account_id=data.get("account_id", str(uuid.uuid4())),
            account_name=data.get("account_name", "Brokerage Account"),
            account_type=data.get("account_type", "Taxable"),
            current_value=data.get("current_value", 0.0),
            holdings=holdings,
            manual_holdings=data.get("manual_holdings", []) or [],
            active_interval=str(data.get("active_interval", "1M") or "1M").upper(),
            lots=lots,
            ownership_type=data.get("ownership_type", "Individual"),
            custodian=data.get("custodian", ""),
            tags=data.get("tags", []) or [],
            tax_settings=data.get("tax_settings", {}) or {
                "jurisdiction": "",
                "account_currency": "USD",
                "withholding_rate": None,
                "tax_exempt": False,
            },
            extra=data.get("extra", {}) or {},
        )

        if lots:
            account.sync_holdings_from_lots()
        return account

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "account_name": self.account_name,
            "account_type": self.account_type,
            "current_value": self.current_value,
            "holdings": self.holdings,
            "lots": self.lots,
            "manual_holdings": self.manual_holdings,
            "active_interval": self.active_interval,
            "ownership_type": self.ownership_type,
            "custodian": self.custodian,
            "tags": self.tags,
            "tax_settings": self.tax_settings,
            "extra": self.extra,
        }


@dataclass
class Client:
    """Client model storing accounts and profile."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Client"
    risk_profile: str = "Not Assessed"
    risk_profile_source: str = "auto"
    active_interval: str = "1M"
    tax_profile: Dict[str, Any] = field(default_factory=lambda: {
        "residency_country": "",
        "tax_country": "",
        "reporting_currency": "USD",
        "treaty_country": "",
        "tax_id": "",
    })
    accounts: List[Account] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "client_id": self.client_id,
            "name": self.name,
            "risk_profile": self.risk_profile,
            "risk_profile_source": self.risk_profile_source,
            "active_interval": self.active_interval,
            "tax_profile": self.tax_profile,
            "accounts": [a.to_dict() for a in self.accounts],
            "extra": self.extra,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Client":
        raw_risk = data.get("risk_profile", "Not Assessed")
        raw_source = data.get("risk_profile_source", "auto")
        if (not raw_risk or raw_risk == "Unassigned") and raw_source != "manual":
            raw_risk = "Not Assessed"
        client = Client(
            client_id=data.get("client_id", str(uuid.uuid4())),
            name=data.get("name", "New Client"),
            risk_profile=raw_risk,
            risk_profile_source=raw_source,
            active_interval=str(data.get("active_interval", "1M") or "1M").upper(),
            tax_profile=data.get("tax_profile", {}) or {
                "residency_country": "",
                "tax_country": "",
                "reporting_currency": "USD",
                "treaty_country": "",
                "tax_id": "",
            },
            accounts=[],
            extra=data.get("extra", {}) or {},
        )

        for acc_data in data.get("accounts", []):
            account = Account.from_dict({
                **(acc_data or {}),
                "active_interval": acc_data.get("active_interval", data.get("active_interval", "1M"))
            })
            client.accounts.append(account)

        return client
