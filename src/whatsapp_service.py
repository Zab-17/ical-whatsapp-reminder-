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


def _send(to: str, message: str, retries: int = 2) -> dict:
    import time
    url = f"{settings.baileys_bridge_url}/send"
    last_err = None
    for attempt in range(1, retries + 2):
        try:
            resp = httpx.post(url, json={"to": to, "message": message}, timeout=30)
            result = resp.json()

            # Detect zombie connection
            if resp.status_code == 503 and result.get("zombie"):
                logger.critical("ZOMBIE DETECTED: Bridge reports WebSocket is dead.")
                raise ConnectionError("WhatsApp bridge zombie: messages not delivering")

            resp.raise_for_status()
            logger.info("Sent message to %s", to)
            return result
        except Exception as e:
            last_err = e
            if attempt <= retries:
                wait = 3 * attempt
                logger.warning("Send to %s failed (attempt %d/%d): %s — retrying in %ds",
                               to, attempt, retries + 1, e, wait)
                time.sleep(wait)
            else:
                raise last_err


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
