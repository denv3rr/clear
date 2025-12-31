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
