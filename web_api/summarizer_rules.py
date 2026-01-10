from __future__ import annotations

RULES = {
    "clients": {
        "keywords": ["client", "clients", "customer", "customers"],
        "handler": "handle_clients",
    },
    "news": {
        "keywords": ["news", "headlines", "latest"],
        "handler": "handle_news",
    },
    "trackers": {
        "keywords": ["tracker", "trackers", "tracking"],
        "handler": "handle_trackers",
    },
}

def handle_clients(clients: dict) -> str:
    """
    Handles the summarization of client data.
    """
    if not clients or "error" in clients:
        return "Could not retrieve client data."

    client_count = len(clients.get("clients", []))
    return f"You have {client_count} clients."


def handle_client_detail(client: dict) -> str:
    if not client or "error" in client:
        return "Could not retrieve client detail."
    client_id = client.get("client_id") or "unknown"
    name = client.get("name") or "Unnamed client"
    accounts = client.get("accounts") or []
    holdings_count = 0
    for account in accounts:
        holdings = account.get("holdings") or {}
        holdings_count += len(holdings)
    return (
        f"Client {client_id} ({name}) has "
        f"{len(accounts)} accounts and {holdings_count} holdings."
    )

def handle_news(news: dict) -> str:
    """
    Handles the summarization of news data.
    """
    if not news or "error" in news:
        return "Could not retrieve news data."

    news_count = len(news.get("items", []))
    return f"There are {news_count} news articles available."

def handle_trackers(trackers: dict) -> str:
    """
    Handles the summarization of tracker data.
    """
    if not trackers or "error" in trackers:
        return "Could not retrieve tracker data."

    tracker_count = trackers.get("count", 0)
    return f"There are {tracker_count} active trackers."


def handle_account_detail(account: dict, client_label: str | None = None) -> str:
    if not account or "error" in account:
        return "Could not retrieve account detail."
    account_id = account.get("account_id") or "unknown"
    account_name = account.get("account_name") or "Account"
    holdings_count = len(account.get("holdings") or {})
    prefix = f"{client_label}: " if client_label else ""
    return (
        f"{prefix}Account {account_id} ({account_name}) "
        f"has {holdings_count} holdings."
    )
