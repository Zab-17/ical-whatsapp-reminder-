from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request

from src import conversation, whatsapp_service

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

scheduler = BackgroundScheduler()

# Tracks pending numbered selections per user phone number
_pending_selections: dict[str, list[dict[str, str]]] = {}


def _run_reminder():
    try:
        from src.reminder import send_daily_reminder
        send_daily_reminder()
    except Exception as e:
        logger.error("Scheduled reminder failed: %s", e)


def _run_detector():
    try:
        from src.detector import detect_changes
        detect_changes()
    except Exception as e:
        logger.error("Scheduled detector failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule reminders at 10 AM, 1 PM, 5 PM, 9 PM Cairo time (UTC+2)
    for hour_utc in [8, 11, 15, 19]:
        scheduler.add_job(
            _run_reminder,
            CronTrigger(hour=hour_utc, minute=0),
            id=f"reminder_{hour_utc}",
            replace_existing=True,
        )
        logger.info("Scheduled reminder at %d:00 UTC", hour_utc)

    scheduler.add_job(
        _run_detector,
        IntervalTrigger(hours=3),
        id="detector",
        replace_existing=True,
    )
    logger.info("Scheduled change detector every 3 hours")

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    yield
    scheduler.shutdown()


app = FastAPI(title="Canvas Reminder WhatsApp Bot", lifespan=lifespan)


@app.get("/health")
async def health():
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    return {"status": "ok", "scheduled_jobs": jobs}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages from Green API."""
    body = await request.json()

    try:
        msg_type = body.get("typeWebhook", "")

        if msg_type != "incomingMessageReceived":
            return {"status": "ignored"}

        msg_data = body.get("messageData", {})
        sender = body.get("senderData", {})
        from_number = sender.get("sender", "").replace("@c.us", "")

        # Extract text from message
        text_data = msg_data.get("textMessageData") or msg_data.get("extendedTextMessageData")
        if not text_data:
            return {"status": "no text"}

        user_input = text_data.get("textMessage") or text_data.get("text", "")
        user_input = user_input.strip()

        logger.info("Received from %s: %s", from_number, user_input)

        # Resolve numbered reply if pending
        resolved_input = _resolve_numbered_reply(from_number, user_input)

        # Route through conversation handler
        result = conversation.route(resolved_input)

        response_body = result["body"]
        buttons = result.get("buttons")
        items = result.get("items")

        if items:
            _pending_selections[from_number] = items
            whatsapp_service.send_list_message(response_body, items, to=from_number)
        elif buttons:
            _pending_selections[from_number] = buttons
            whatsapp_service.send_button_message(response_body, buttons, to=from_number)
        else:
            _pending_selections.pop(from_number, None)
            whatsapp_service.send_text(response_body, to=from_number)

    except Exception as e:
        logger.error("Error processing webhook: %s", e)

    return {"status": "ok"}


def _resolve_numbered_reply(phone: str, body: str) -> str:
    pending = _pending_selections.get(phone)
    if not pending:
        return body
    try:
        index = int(body) - 1
        if 0 <= index < len(pending):
            resolved = pending[index]["id"]
            logger.info("Resolved numbered reply %s -> %s", body, resolved)
            _pending_selections.pop(phone, None)
            return resolved
    except (ValueError, KeyError, IndexError):
        pass
    return body
