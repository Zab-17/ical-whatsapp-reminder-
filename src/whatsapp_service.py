from __future__ import annotations

import logging

from twilio.rest import Client
from twilio.request_validator import RequestValidator

from src.config import settings

logger = logging.getLogger(__name__)

_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
_validator = RequestValidator(settings.twilio_auth_token)


def send_text(body: str, to: str | None = None) -> str:
    to = to or settings.user_whatsapp_to
    message = _client.messages.create(
        from_=settings.twilio_whatsapp_from,
        body=body,
        to=to,
    )
    logger.info("Sent message %s to %s", message.sid, to)
    return message.sid


def send_button_message(body: str, buttons: list[dict[str, str]], to: str | None = None) -> str:
    """Send a message with quick-reply buttons.

    Each button dict should have 'id' and 'title' keys.
    WhatsApp supports up to 3 quick-reply buttons.
    For Twilio sandbox, buttons are sent as numbered text options.
    """
    to = to or settings.user_whatsapp_to

    # Twilio sandbox doesn't support interactive templates directly,
    # so we format buttons as numbered text options
    button_text = "\n".join(
        f"{i + 1}. {btn['title']}" for i, btn in enumerate(buttons)
    )
    full_body = f"{body}\n\n{button_text}\n\nReply with the number of your choice."

    message = _client.messages.create(
        from_=settings.twilio_whatsapp_from,
        body=full_body,
        to=to,
    )
    logger.info("Sent button message %s to %s", message.sid, to)
    return message.sid


def send_list_message(body: str, items: list[dict[str, str]], to: str | None = None) -> str:
    """Send a message with a list of selectable items.

    Each item dict should have 'id' and 'title' keys.
    Formatted as numbered options for Twilio sandbox compatibility.
    """
    to = to or settings.user_whatsapp_to

    item_text = "\n".join(
        f"{i + 1}. {item['title']}" for i, item in enumerate(items)
    )
    full_body = f"{body}\n\n{item_text}\n\nReply with the number of your choice."

    message = _client.messages.create(
        from_=settings.twilio_whatsapp_from,
        body=full_body,
        to=to,
    )
    logger.info("Sent list message %s to %s", message.sid, to)
    return message.sid


def validate_webhook(url: str, params: dict, signature: str) -> bool:
    return _validator.validate(url, params, signature)
