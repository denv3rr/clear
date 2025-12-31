from __future__ import annotations
import httpx
from fastapi import Request
from web_api.summarizer_rules import RULES, handle_clients, handle_news, handle_trackers

def get_clients(request: Request):
    """
    Fetches client data from the /api/clients endpoint.
    """
    base_url = str(request.base_url)
    api_key = request.headers.get("x-api-key")
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        response = httpx.get(f"{base_url}api/clients", headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error occurred: {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_news(request: Request):
    """
    Fetches news data from the /api/intel/news endpoint.
    """
    base_url = str(request.base_url)
    api_key = request.headers.get("x-api-key")
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        response = httpx.get(f"{base_url}api/intel/news", headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error occurred: {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_trackers(request: Request):
    """
    Fetches tracker data from the /api/trackers/snapshot endpoint.
    """
    base_url = str(request.base_url)
    api_key = request.headers.get("x-api-key")
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        response = httpx.get(f"{base_url}api/trackers/snapshot", headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP error occurred: {e.response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def summarize(request: Request, question: str, context: str, sources: list[str] | None = None) -> str:
    """
    Summarizes the data from the different sources based on a set of rules.
    """
    question_lower = question.lower()
    
    for rule_name, rule_details in RULES.items():
        for keyword in rule_details["keywords"]:
            if keyword in question_lower:
                handler_name = rule_details["handler"]
                if handler_name == "handle_clients":
                    clients = get_clients(request)
                    return handle_clients(clients)
                elif handler_name == "handle_news":
                    news = get_news(request)
                    return handle_news(news)
                elif handler_name == "handle_trackers":
                    trackers = get_trackers(request)
                    return handle_trackers(trackers)

    return "I'm sorry, I don't understand the question. Please try rephrasing it."
