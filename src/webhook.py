from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request, Response

from src import conversation, whatsapp_service

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

scheduler = BackgroundScheduler()


def _run_reminder():
    """Scheduled job: send daily reminder."""
    try:
        from src.reminder import send_daily_reminder
        send_daily_reminder()
    except Exception as e:
        logger.error("Scheduled reminder failed: %s", e)


def _run_detector():
    """Scheduled job: run change detector."""
    try:
        from src.detector import detect_changes
        detect_changes()
    except Exception as e:
        logger.error("Scheduled detector failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schedule reminders at 10 AM, 1 PM, 5 PM, 9 PM Cairo time (UTC+2)
    # = 8 AM, 11 AM, 3 PM, 7 PM UTC
    for hour_utc in [8, 11, 15, 19]:
        scheduler.add_job(
            _run_reminder,
            CronTrigger(hour=hour_utc, minute=0),
            id=f"reminder_{hour_utc}",
            replace_existing=True,
        )
        logger.info("Scheduled reminder at %d:00 UTC", hour_utc)

    # Schedule change detector every 3 hours
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
    logger.info("Scheduler shut down")


app = FastAPI(title="Canvas Reminder WhatsApp Bot", lifespan=lifespan)

# Tracks pending numbered selections per user phone number
_pending_selections: dict[str, list[dict[str, str]]] = {}


@app.get("/health")
async def health():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run": str(job.next_run_time),
        })
    return {"status": "ok", "scheduled_jobs": jobs}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = str(form.get("Body", "")).strip()
    from_number = str(form.get("From", ""))

    logger.info("Received message from %s: %s", from_number, body)

    # Check if this is a numbered reply to a pending selection
    resolved_input = _resolve_numbered_reply(from_number, body)

    # Route the input through the conversation handler
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

    # Return empty TwiML so Twilio doesn't send a duplicate
    return Response(
        content='<Response></Response>',
        media_type="application/xml",
    )


def _resolve_numbered_reply(phone: str, body: str) -> str:
    """If the user replied with a number, look up the corresponding button/item ID."""
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
