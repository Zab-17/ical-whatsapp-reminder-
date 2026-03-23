from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def check_health() -> dict:
    """Check WhatsApp bridge health. Returns health dict or raises."""
    try:
        resp = httpx.get(f"{settings.baileys_bridge_url}/health", timeout=5)
        return resp.json()
    except Exception as e:
        logger.error("Bridge health check failed: %s", e)
        return {"status": "down", "connected": False, "socketAlive": False}


def is_healthy() -> bool:
    """Quick check: is the bridge actually working?"""
    health = check_health()
    return health.get("status") == "ok"


def _send(to: str, message: str) -> dict:
    url = f"{settings.baileys_bridge_url}/send"
    resp = httpx.post(url, json={"to": to, "message": message}, timeout=180)
    result = resp.json()

    # Detect zombie connection
    if resp.status_code == 503 and result.get("zombie"):
        logger.critical("ZOMBIE DETECTED: Bridge reports WebSocket is dead. Messages are NOT being delivered!")
        raise ConnectionError("WhatsApp bridge zombie: messages not delivering")

    resp.raise_for_status()
    logger.info("Sent message to %s", to)
    return result


UNSUB_FOOTER = "\n\n_Reply *stop* to unsubscribe_"


def send_text(body: str, to: str = "") -> dict:
    return _send(to, body + UNSUB_FOOTER)


def send_button_message(body: str, buttons: list[dict[str, str]], to: str = "") -> dict:
    button_text = "\n".join(f"{i + 1}. {btn['title']}" for i, btn in enumerate(buttons))
    full_body = f"{body}\n\n{button_text}\n\nReply with the number of your choice.{UNSUB_FOOTER}"
    return _send(to, full_body)


def send_list_message(body: str, items: list[dict[str, str]], to: str = "") -> dict:
    item_text = "\n".join(f"{i + 1}. {item['title']}" for i, item in enumerate(items))
    full_body = f"{body}\n\n{item_text}\n\nReply with the number of your choice.{UNSUB_FOOTER}"
    return _send(to, full_body)
