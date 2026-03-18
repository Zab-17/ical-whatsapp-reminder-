from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, message: str) -> dict:
    url = f"{settings.baileys_bridge_url}/send"
    resp = httpx.post(url, json={"to": to, "message": message}, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    logger.info("Sent message to %s", to)
    return result


def send_text(body: str, to: str = "") -> dict:
    return _send(to, body)


def send_button_message(body: str, buttons: list[dict[str, str]], to: str = "") -> dict:
    button_text = "\n".join(f"{i + 1}. {btn['title']}" for i, btn in enumerate(buttons))
    full_body = f"{body}\n\n{button_text}\n\nReply with the number of your choice."
    return _send(to, full_body)


def send_list_message(body: str, items: list[dict[str, str]], to: str = "") -> dict:
    item_text = "\n".join(f"{i + 1}. {item['title']}" for i, item in enumerate(items))
    full_body = f"{body}\n\n{item_text}\n\nReply with the number of your choice."
    return _send(to, full_body)
