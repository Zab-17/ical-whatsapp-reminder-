from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src import conversation, whatsapp_service
from src.config import settings
from src.database import get_user

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

scheduler = BackgroundScheduler()
_pending_selections: dict[str, list[dict[str, str]]] = {}

LOGIN_URL = None  # Set after app starts


def _run_reminder():
    try:
        from src.reminder import send_all_reminders
        send_all_reminders()
    except Exception as e:
        logger.error("Scheduled reminder failed: %s", e)


def _run_detector():
    try:
        from src.detector import detect_all_changes
        detect_all_changes()
    except Exception as e:
        logger.error("Scheduled detector failed: %s", e)


def _run_health_check():
    """Periodic health check — logs warnings if bridge is degraded or dead."""
    try:
        health = whatsapp_service.check_health()
        status = health.get("status", "unknown")
        if status == "down":
            logger.critical("BRIDGE DOWN: WhatsApp bridge is not responding!")
        elif status == "degraded":
            logger.warning("BRIDGE DEGRADED: %s", health)
        elif health.get("sendFailCount", 0) > 0:
            logger.warning("BRIDGE FLAKY: %d consecutive send failures", health["sendFailCount"])
        else:
            logger.info("Bridge healthy: connected=%s, socketAlive=%s", health.get("connected"), health.get("socketAlive"))
    except Exception as e:
        logger.critical("BRIDGE UNREACHABLE: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run every hour — send_all_reminders checks each user's custom schedule
    scheduler.add_job(_run_reminder, CronTrigger(minute=0),
                      id="reminder_hourly", replace_existing=True)

    scheduler.add_job(_run_detector, IntervalTrigger(hours=3),
                      id="detector", replace_existing=True)

    # Health check every 5 minutes
    scheduler.add_job(_run_health_check, IntervalTrigger(minutes=5),
                      id="health_check", replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    yield
    scheduler.shutdown()


app = FastAPI(title="Canvas Reminder WhatsApp Bot", lifespan=lifespan)

# Import and include login routes
from src.web import router as web_router
app.include_router(web_router)


@app.get("/health")
async def health():
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in scheduler.get_jobs()]
    bridge = whatsapp_service.check_health()
    overall = "ok" if bridge.get("status") == "ok" else "degraded"
    return {"status": overall, "bridge": bridge, "scheduled_jobs": jobs}


@app.get("/qr")
async def qr_proxy():
    """Proxy the WhatsApp bridge QR page."""
    import httpx
    from fastapi.responses import HTMLResponse
    try:
        r = httpx.get(f"{settings.baileys_bridge_url}/qr", timeout=10)
        return HTMLResponse(r.text)
    except Exception:
        return HTMLResponse("<h1>WhatsApp bridge not responding. Try again in a moment.</h1>")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    body = await request.json()
    from_number = body.get("from", "")
    text = body.get("text", "").strip()

    if not from_number or not text:
        return {"status": "ignored"}

    logger.info("Received from %s: %s", from_number, text)

    # Handle unsubscribe
    if text.lower() in ("stop", "unsubscribe", "quit"):
        from src.database import deactivate_user
        deactivate_user(from_number)
        whatsapp_service.send_text(
            "You've been unsubscribed. No more reminders.\n\nSend *start* anytime to resubscribe.",
            to=from_number,
        )
        return {"status": "unsubscribed"}

    # Handle resubscribe
    if text.lower() in ("start", "subscribe", "resume"):
        from src.database import reactivate_user
        user = get_user(from_number)
        if user:
            reactivate_user(from_number)
            whatsapp_service.send_text(
                "Welcome back! Reminders are active again.\n\nSend *hi* to see the menu.",
                to=from_number,
            )
            return {"status": "resubscribed"}

    # Check if user is registered
    user = get_user(from_number)
    if not user:
        whatsapp_service.send_text(
            "👋 Welcome! You're not registered yet.\n\n"
            "Visit the login page to connect your Canvas account.",
            to=from_number,
        )
        return {"status": "unregistered"}

    # Resolve numbered reply
    resolved = _resolve_numbered_reply(from_number, text)

    # Route through conversation
    result = conversation.route(resolved, from_number)

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

    return {"status": "ok"}


def _resolve_numbered_reply(phone: str, body: str) -> str:
    pending = _pending_selections.get(phone)
    if not pending:
        return body
    try:
        index = int(body) - 1
        if 0 <= index < len(pending):
            resolved = pending[index]["id"]
            _pending_selections.pop(phone, None)
            return resolved
    except (ValueError, KeyError, IndexError):
        pass
    return body
