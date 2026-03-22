"""Daily reminder — sends to all registered users."""
from __future__ import annotations

import json
import logging
import sys

from datetime import datetime, timezone, timedelta

from src import canvas_service, ical_service, whatsapp_service
from src.conversation import MAIN_MENU_BUTTONS
from src.database import (
    get_active_users, get_user_reminder_hours, get_user_ical_url,
    get_dismissed_items, get_user, _conn,
)
from src.models import AssignmentInfo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _item_key(a: AssignmentInfo) -> str:
    """Stable key for an assignment — used to track dismissals."""
    return f"{a.name}|{a.course_name}"


def _save_last_reminder_items(phone: str, items: list[AssignmentInfo]) -> None:
    """Store the numbered item list so 'done N' can reference it."""
    data = [{"name": a.name, "course_name": a.course_name, "key": _item_key(a)} for a in items]
    with _conn() as conn:
        conn.execute("UPDATE users SET snapshot = ? WHERE phone = ?", (json.dumps({"last_reminder": data}), phone))


def get_last_reminder_items(phone: str) -> list[dict]:
    """Retrieve the last reminder's numbered items."""
    user = get_user(phone)
    if not user:
        return []
    snapshot = json.loads(user.get("snapshot") or "{}")
    return snapshot.get("last_reminder", [])


def send_all_reminders() -> None:
    current_hour = datetime.now(timezone.utc).hour
    users = get_active_users()
    logger.info("Reminder check at %d:00 UTC for %d active users", current_hour, len(users))
    for user in users:
        try:
            user_hours = get_user_reminder_hours(user["phone"])
            if current_hour in user_hours:
                send_reminder_for_user(user["phone"], user.get("name", ""))
            else:
                logger.info("Skipping %s — not in their schedule (%s)", user["phone"], user_hours)
        except Exception as e:
            logger.error("Reminder failed for %s: %s", user["phone"], e)


def send_reminder_for_user(phone: str, name: str = "") -> None:
    ical_url = get_user_ical_url(phone)
    try:
        if ical_url:
            items = ical_service.fetch_upcoming_from_ical(ical_url)
        else:
            items = [a for a in canvas_service.get_upcoming_items(phone) if not a.submitted]
    except Exception as e:
        logger.error("Failed to fetch items for %s: %s", phone, e)
        if ical_url:
            whatsapp_service.send_text("❌ Failed to fetch your calendar feed. The URL may be invalid.", to=phone)
        else:
            whatsapp_service.send_text("❌ Your Canvas session may have expired. Please re-login.", to=phone)
        return

    # Filter out dismissed items
    dismissed = get_dismissed_items(phone)
    items = [a for a in items if _item_key(a) not in dismissed]

    greeting = f"Hey {name}! " if name else ""
    if not items:
        body = f"☀️ *{greeting}No upcoming assignments in the next 7 days!*"
        whatsapp_service.send_button_message(body, MAIN_MENU_BUTTONS, to=phone)
    else:
        # Save numbered list for "done N" lookups
        _save_last_reminder_items(phone, items)

        lines = [f"☀️ *{greeting}Assignment Reminder:*\n"]
        current_date = None
        for i, a in enumerate(items, 1):
            cairo = a.due_at.astimezone(timezone(timedelta(hours=2))) if a.due_at else None
            date_str = cairo.strftime("%A, %b %d") if cairo else "No date"
            if date_str != current_date:
                current_date = date_str
                lines.append(f"\n📅 *{date_str}*")
            time_str = cairo.strftime("%I:%M %p") if cairo else ""
            lines.append(f"  {i}. {a.name}")
            lines.append(f"    📖 {a.course_name} — {time_str}")
        lines.append(f"\n📊 Total: {len(items)} upcoming items")
        lines.append('\n_Reply "done 1" to mark an item as submitted_')
        body = "\n".join(lines)
        whatsapp_service.send_text(body, to=phone)

    logger.info("Reminder sent to %s (%d items)", phone, len(items))


def send_migration_message() -> None:
    """One-time message to existing users asking them to switch to iCal feed."""
    users = get_active_users()
    for user in users:
        if get_user_ical_url(user["phone"]):
            continue  # already migrated
        try:
            name = user.get("name", "")
            greeting = f"Hey {name}! " if name else "Hey! "
            body = (
                f"🔔 *{greeting}Quick upgrade for your reminders!*\n\n"
                "We now support Canvas Calendar Feeds — a permanent link that *never expires*. "
                "No more re-logging every 2 days!\n\n"
                "*How to set it up (30 seconds):*\n"
                "1. Open Canvas on your phone or laptop\n"
                "2. Go to *Calendar* (left sidebar)\n"
                "3. Tap *Calendar Feed* (bottom right)\n"
                "4. Copy the URL and send it here\n\n"
                "That's it — one time, works forever! 🎉"
            )
            whatsapp_service.send_text(body, to=user["phone"])
            logger.info("Migration message sent to %s", user["phone"])
        except Exception as e:
            logger.error("Failed to send migration msg to %s: %s", user["phone"], e)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        send_migration_message()
    else:
        send_all_reminders()
