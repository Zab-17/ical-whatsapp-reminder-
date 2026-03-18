from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"https://api.green-api.com/waInstance{settings.green_api_instance_id}"


def _post(method: str, payload: dict) -> dict:
    url = f"{BASE_URL}/{method}/{settings.green_api_token}"
    resp = httpx.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    logger.info("Green API %s: %s", method, result.get("idMessage", "ok"))
    return result


def _chat_id(to: str | None = None) -> str:
    number = (to or settings.user_whatsapp_to).replace("whatsapp:", "").replace("+", "").strip()
    return f"{number}@c.us"


def send_text(body: str, to: str | None = None) -> dict:
    return _post("sendMessage", {
        "chatId": _chat_id(to),
        "message": body,
    })


def send_button_message(body: str, buttons: list[dict[str, str]], to: str | None = None) -> dict:
    """Send a message with numbered options (Green API free tier doesn't support interactive buttons)."""
    button_text = "\n".join(f"{i + 1}. {btn['title']}" for i, btn in enumerate(buttons))
    full_body = f"{body}\n\n{button_text}\n\nReply with the number of your choice."
    return _post("sendMessage", {
        "chatId": _chat_id(to),
        "message": full_body,
    })


def send_list_message(body: str, items: list[dict[str, str]], to: str | None = None) -> dict:
    """Send a message with numbered list items."""
    item_text = "\n".join(f"{i + 1}. {item['title']}" for i, item in enumerate(items))
    full_body = f"{body}\n\n{item_text}\n\nReply with the number of your choice."
    return _post("sendMessage", {
        "chatId": _chat_id(to),
        "message": full_body,
    })
