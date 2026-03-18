from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Query, Request, Response

from src import conversation, whatsapp_service
from src.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

scheduler = BackgroundScheduler()

# Webhook verify token — set this to any string you choose
VERIFY_TOKEN = "canvas_reminder_verify"


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


@app.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info("Webhook verified")
        return Response(content=hub_challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Handle incoming WhatsApp messages from Meta."""
    body = await request.json()

    try:
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no messages"}

        msg = messages[0]
        from_number = msg.get("from", "")
        msg_type = msg.get("type", "")

        # Extract the user's input based on message type
        if msg_type == "text":
            user_input = msg["text"]["body"]
        elif msg_type == "interactive":
            interactive = msg["interactive"]
            if interactive["type"] == "button_reply":
                user_input = interactive["button_reply"]["id"]
            elif interactive["type"] == "list_reply":
                user_input = interactive["list_reply"]["id"]
            else:
                user_input = "menu"
        else:
            user_input = "menu"

        logger.info("Received from %s: %s (type: %s)", from_number, user_input, msg_type)

        # Route through conversation handler
        result = conversation.route(user_input)

        response_body = result["body"]
        buttons = result.get("buttons")
        items = result.get("items")

        if items:
            whatsapp_service.send_list_message(response_body, items, to=from_number)
        elif buttons:
            whatsapp_service.send_button_message(response_body, buttons, to=from_number)
        else:
            whatsapp_service.send_text(response_body, to=from_number)

    except Exception as e:
        logger.error("Error processing webhook: %s", e)

    return {"status": "ok"}
