"""Daily reminder — sends to all registered users."""
from __future__ import annotations

import logging
import sys

from datetime import datetime, timezone, timedelta

from src import canvas_service, whatsapp_service
from src.conversation import MAIN_MENU_BUTTONS
from src.database import get_active_users, get_user_reminder_hours

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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
    try:
        items = canvas_service.get_upcoming_items(phone)
    except Exception as e:
        logger.error("Failed to fetch items for %s: %s", phone, e)
        whatsapp_service.send_text("❌ Your Canvas session may have expired. Please re-login.", to=phone)
        return

    greeting = f"Hey {name}! " if name else ""
    if not items:
        body = f"☀️ *{greeting}No upcoming assignments in the next 7 days!*"
    else:
        lines = [f"☀️ *{greeting}Assignment Reminder:*\n"]
        current_date = None
        for a in items:
            cairo = a.due_at.astimezone(timezone(timedelta(hours=2))) if a.due_at else None
            date_str = cairo.strftime("%A, %b %d") if cairo else "No date"
            if date_str != current_date:
                current_date = date_str
                lines.append(f"\n📅 *{date_str}*")
            time_str = cairo.strftime("%I:%M %p") if cairo else ""
            lines.append(f"  • {a.name}")
            lines.append(f"    📖 {a.course_name} — {time_str}")
        lines.append(f"\n📊 Total: {len(items)} upcoming items")
        body = "\n".join(lines)

    whatsapp_service.send_button_message(body, MAIN_MENU_BUTTONS, to=phone)
    logger.info("Reminder sent to %s (%d items)", phone, len(items))


if __name__ == "__main__":
    send_all_reminders()
