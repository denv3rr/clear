from __future__ import annotations

from typing import Any, Dict, Iterable, List

from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.holdings import normalize_ticker


def _holdings_count(holdings: Dict[str, float]) -> int:
    return len([t for t, qty in (holdings or {}).items() if float(qty or 0.0) != 0.0])


def _manual_value(manual_holdings: List[Dict[str, Any]]) -> float:
    total = 0.0
    for entry in manual_holdings or []:
        try:
            total += float(entry.get("total_value", 0.0) or 0.0)
        except Exception:
            continue
    return total


def account_summary(account: Account) -> Dict[str, Any]:
    return {
        "account_id": account.account_id,
        "account_name": account.account_name,
        "account_type": account.account_type,
        "holdings_count": _holdings_count(account.holdings),
        "manual_value": _manual_value(account.manual_holdings),
        "tags": list(account.tags or []),
    }


def account_detail(account: Account) -> Dict[str, Any]:
    holdings = {
        normalize_ticker(ticker): float(qty or 0.0)
        for ticker, qty in (account.holdings or {}).items()
    }
    return {
        **account_summary(account),
        "holdings": holdings,
        "manual_holdings": list(account.manual_holdings or []),
        "tax_settings": dict(account.tax_settings or {}),
        "custodian": account.custodian,
        "ownership_type": account.ownership_type,
    }


def client_summary(client: Client) -> Dict[str, Any]:
    holdings_count = sum(_holdings_count(acc.holdings) for acc in client.accounts)
    return {
        "client_id": client.client_id,
        "name": client.name,
        "risk_profile": client.risk_profile,
        "accounts_count": len(client.accounts),
        "holdings_count": holdings_count,
        "reporting_currency": (client.tax_profile or {}).get("reporting_currency", "USD"),
    }


def client_detail(client: Client) -> Dict[str, Any]:
    return {
        **client_summary(client),
        "tax_profile": dict(client.tax_profile or {}),
        "accounts": [account_detail(account) for account in client.accounts],
    }


def list_clients(clients: Iterable[Client]) -> List[Dict[str, Any]]:
    return [client_summary(client) for client in clients]
