from __future__ import annotations

from typing import Any, Dict, Iterable, List

from modules.client_mgr.client_model import Client, Account
from modules.client_mgr.toolkit import FinancialToolkit, TOOLKIT_PERIOD, TOOLKIT_INTERVAL
from modules.client_mgr.valuation import ValuationEngine
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


def _aggregate_holdings(accounts: Iterable[Account]) -> Dict[str, float]:
    consolidated: Dict[str, float] = {}
    for account in accounts:
        for ticker, qty in (account.holdings or {}).items():
            try:
                consolidated[ticker] = consolidated.get(ticker, 0.0) + float(qty or 0.0)
            except Exception:
                consolidated[ticker] = consolidated.get(ticker, 0.0)
    return consolidated


def _aggregate_lots(accounts: Iterable[Account]) -> Dict[str, List[Dict[str, Any]]]:
    lots: Dict[str, List[Dict[str, Any]]] = {}
    for account in accounts:
        for ticker, entries in (account.lots or {}).items():
            lots.setdefault(ticker, []).extend(entries or [])
    return lots


def _aggregate_manual_holdings(accounts: Iterable[Account]) -> List[Dict[str, Any]]:
    manual: List[Dict[str, Any]] = []
    for account in accounts:
        manual.extend(list(account.manual_holdings or []))
    return manual


def _history_payload(dates: List[Any], values: List[float]) -> List[Dict[str, Any]]:
    if not values:
        return []
    series = []
    for idx, value in enumerate(values):
        ts = None
        if idx < len(dates):
            try:
                ts = int(getattr(dates[idx], "timestamp")())
            except Exception:
                ts = None
        series.append({"ts": ts, "value": float(value or 0.0)})
    return series


def portfolio_dashboard(client: Client, interval: str = "1M") -> Dict[str, Any]:
    valuation = ValuationEngine()
    holdings = _aggregate_holdings(client.accounts)
    lots = _aggregate_lots(client.accounts)
    manual_entries = _aggregate_manual_holdings(client.accounts)
    warnings: List[str] = []

    total_value = 0.0
    enriched: Dict[str, Any] = {}
    if holdings:
        total_value, enriched = valuation.calculate_portfolio_value(
            holdings,
            history_period=TOOLKIT_PERIOD.get(interval, "1y"),
            history_interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
    else:
        warnings.append("No holdings available for valuation.")

    manual_total, manual_holdings = valuation.calculate_manual_holdings_value(manual_entries)
    history_dates, history_values = valuation.generate_portfolio_history_series(
        enriched_data=enriched,
        holdings=holdings,
        interval=interval,
        lot_map=lots,
    )
    toolkit = FinancialToolkit(client)
    risk_payload = toolkit.build_risk_dashboard_payload(
        holdings=holdings,
        interval=interval,
        label=client.name,
        scope="Portfolio",
    )
    regime_payload = toolkit.build_regime_snapshot_payload(
        holdings=holdings,
        lot_map=lots,
        interval=interval,
        label=client.name,
        scope="Portfolio",
    )

    holdings_list = sorted(
        enriched.values(),
        key=lambda entry: float(entry.get("market_value", 0.0) or 0.0),
        reverse=True,
    )
    holdings_list = holdings_list[:25]

    sector_totals: Dict[str, float] = {}
    for entry in enriched.values():
        sector = str(entry.get("sector", "N/A") or "N/A")
        value = float(entry.get("market_value", 0.0) or 0.0)
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value
    sector_rows = sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    hhi = 0.0
    for _, value in sector_rows:
        if total_value > 0:
            pct = value / total_value
            hhi += pct * pct

    movers = sorted(
        enriched.values(),
        key=lambda entry: float(entry.get("pct", 0.0) or 0.0),
        reverse=True,
    )
    gainers = movers[:5]
    losers = list(reversed(movers[-5:])) if len(movers) > 5 else []

    return {
        "client": client_summary(client),
        "interval": interval,
        "totals": {
            "market_value": float(total_value),
            "manual_value": float(manual_total),
            "total_value": float(total_value + manual_total),
            "holdings_count": len(holdings),
            "manual_count": len(manual_holdings),
        },
        "holdings": holdings_list,
        "manual_holdings": manual_holdings,
        "history": _history_payload(history_dates, history_values),
        "risk": risk_payload,
        "regime": regime_payload,
        "diagnostics": {
            "sectors": [
                {
                    "sector": sector,
                    "value": float(value),
                    "pct": float(value / total_value) if total_value > 0 else 0.0,
                }
                for sector, value in sector_rows[:8]
            ],
            "hhi": float(hhi),
            "gainers": [
                {
                    "ticker": row.get("ticker"),
                    "pct": float(row.get("pct", 0.0) or 0.0),
                    "change": float(row.get("change", 0.0) or 0.0),
                }
                for row in gainers
            ],
            "losers": [
                {
                    "ticker": row.get("ticker"),
                    "pct": float(row.get("pct", 0.0) or 0.0),
                    "change": float(row.get("change", 0.0) or 0.0),
                }
                for row in losers
            ],
        },
        "warnings": warnings,
    }


def account_dashboard(client: Client, account: Account, interval: str = "1M") -> Dict[str, Any]:
    valuation = ValuationEngine()
    holdings = dict(account.holdings or {})
    lots = dict(account.lots or {})
    warnings: List[str] = []

    total_value = 0.0
    enriched: Dict[str, Any] = {}
    if holdings:
        total_value, enriched = valuation.calculate_portfolio_value(
            holdings,
            history_period=TOOLKIT_PERIOD.get(interval, "1y"),
            history_interval=TOOLKIT_INTERVAL.get(interval, "1d"),
        )
    else:
        warnings.append("No holdings available for valuation.")

    manual_total, manual_holdings = valuation.calculate_manual_holdings_value(account.manual_holdings or [])
    history_dates, history_values = valuation.generate_portfolio_history_series(
        enriched_data=enriched,
        holdings=holdings,
        interval=interval,
        lot_map=lots,
    )
    toolkit = FinancialToolkit(client)
    risk_payload = toolkit.build_risk_dashboard_payload(
        holdings=holdings,
        interval=interval,
        label=account.account_name,
        scope="Account",
    )
    regime_payload = toolkit.build_regime_snapshot_payload(
        holdings=holdings,
        lot_map=lots,
        interval=interval,
        label=account.account_name,
        scope="Account",
    )

    holdings_list = sorted(
        enriched.values(),
        key=lambda entry: float(entry.get("market_value", 0.0) or 0.0),
        reverse=True,
    )
    holdings_list = holdings_list[:20]

    sector_totals: Dict[str, float] = {}
    for entry in enriched.values():
        sector = str(entry.get("sector", "N/A") or "N/A")
        value = float(entry.get("market_value", 0.0) or 0.0)
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value
    sector_rows = sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    hhi = 0.0
    for _, value in sector_rows:
        if total_value > 0:
            pct = value / total_value
            hhi += pct * pct

    movers = sorted(
        enriched.values(),
        key=lambda entry: float(entry.get("pct", 0.0) or 0.0),
        reverse=True,
    )
    gainers = movers[:5]
    losers = list(reversed(movers[-5:])) if len(movers) > 5 else []

    return {
        "client": client_summary(client),
        "account": account_detail(account),
        "interval": interval,
        "totals": {
            "market_value": float(total_value),
            "manual_value": float(manual_total),
            "total_value": float(total_value + manual_total),
            "holdings_count": _holdings_count(account.holdings),
            "manual_count": len(manual_holdings),
        },
        "holdings": holdings_list,
        "manual_holdings": manual_holdings,
        "history": _history_payload(history_dates, history_values),
        "risk": risk_payload,
        "regime": regime_payload,
        "diagnostics": {
            "sectors": [
                {
                    "sector": sector,
                    "value": float(value),
                    "pct": float(value / total_value) if total_value > 0 else 0.0,
                }
                for sector, value in sector_rows[:8]
            ],
            "hhi": float(hhi),
            "gainers": [
                {
                    "ticker": row.get("ticker"),
                    "pct": float(row.get("pct", 0.0) or 0.0),
                    "change": float(row.get("change", 0.0) or 0.0),
                }
                for row in gainers
            ],
            "losers": [
                {
                    "ticker": row.get("ticker"),
                    "pct": float(row.get("pct", 0.0) or 0.0),
                    "change": float(row.get("change", 0.0) or 0.0),
                }
                for row in losers
            ],
        },
        "warnings": warnings,
    }


def client_patterns(client: Client, interval: str = "1M") -> Dict[str, Any]:
    holdings = _aggregate_holdings(client.accounts)
    toolkit = FinancialToolkit(client)
    return toolkit.build_pattern_payload(
        holdings=holdings,
        interval=interval,
        label=client.name,
        scope="Portfolio",
    )


def account_patterns(client: Client, account: Account, interval: str = "1M") -> Dict[str, Any]:
    holdings = dict(account.holdings or {})
    toolkit = FinancialToolkit(client)
    return toolkit.build_pattern_payload(
        holdings=holdings,
        interval=interval,
        label=account.account_name,
        scope="Account",
    )
