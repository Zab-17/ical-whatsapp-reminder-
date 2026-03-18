from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

API_URL = f"https://graph.facebook.com/v23.0/{settings.whatsapp_phone_id}/messages"
HEADERS = {
    "Authorization": f"Bearer {settings.whatsapp_access_token}",
    "Content-Type": "application/json",
}


def send_text(body: str, to: str | None = None) -> dict:
    to = _clean_number(to or settings.user_whatsapp_to)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    resp = httpx.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    logger.info("Sent text message to %s: %s", to, result.get("messages", [{}])[0].get("id", "?"))
    return result


def send_button_message(body: str, buttons: list[dict[str, str]], to: str | None = None) -> dict:
    """Send a message with quick-reply buttons (max 3).

    Each button dict should have 'id' and 'title' keys.
    """
    to = _clean_number(to or settings.user_whatsapp_to)

    # Meta supports max 3 interactive buttons
    meta_buttons = [
        {"type": "reply", "reply": {"id": btn["id"], "title": btn["title"][:20]}}
        for btn in buttons[:3]
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": meta_buttons},
        },
    }
    resp = httpx.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    logger.info("Sent button message to %s", to)
    return result


def send_list_message(body: str, items: list[dict[str, str]], to: str | None = None) -> dict:
    """Send a message with a list picker (max 10 items).

    Each item dict should have 'id' and 'title' keys.
    """
    to = _clean_number(to or settings.user_whatsapp_to)

    rows = [
        {"id": item["id"], "title": item["title"][:24]}
        for item in items[:10]
    ]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": "Select",
                "sections": [{"title": "Options", "rows": rows}],
            },
        },
    }
    resp = httpx.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    logger.info("Sent list message to %s", to)
    return result


def _clean_number(number: str) -> str:
    """Strip 'whatsapp:' prefix and '+' for Meta API compatibility."""
    return number.replace("whatsapp:", "").replace("+", "").strip()
