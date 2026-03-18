"""Daily reminder — sends to all registered users."""
from __future__ import annotations

import logging
import sys

from src import canvas_service, whatsapp_service
from src.conversation import MAIN_MENU_BUTTONS
from src.database import get_all_users

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def send_all_reminders() -> None:
    users = get_all_users()
    logger.info("Sending reminders to %d users", len(users))
    for user in users:
        try:
            send_reminder_for_user(user["phone"])
        except Exception as e:
            logger.error("Reminder failed for %s: %s", user["phone"], e)


def send_reminder_for_user(phone: str) -> None:
    try:
        items = canvas_service.get_upcoming_items(phone)
    except Exception as e:
        logger.error("Failed to fetch items for %s: %s", phone, e)
        whatsapp_service.send_text("❌ Your Canvas session may have expired. Please re-login.", to=phone)
        return

    if not items:
        body = "☀️ *Good morning!*\n\n✅ No upcoming assignments in the next 7 days."
    else:
        lines = ["☀️ *Assignment Reminder:*\n"]
        current_date = None
        for a in items:
            date_str = a.due_at.strftime("%A, %b %d") if a.due_at else "No date"
            if date_str != current_date:
                current_date = date_str
                lines.append(f"\n📅 *{date_str}*")
            time_str = a.due_at.strftime("%I:%M %p") if a.due_at else ""
            lines.append(f"  • {a.name}")
            lines.append(f"    📖 {a.course_name} — {time_str}")
        lines.append(f"\n📊 Total: {len(items)} upcoming items")
        body = "\n".join(lines)

    whatsapp_service.send_button_message(body, MAIN_MENU_BUTTONS, to=phone)
    logger.info("Reminder sent to %s (%d items)", phone, len(items))


if __name__ == "__main__":
    send_all_reminders()
