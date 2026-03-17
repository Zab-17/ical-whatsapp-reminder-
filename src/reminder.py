"""Daily reminder entry point. Run with: python -m src.reminder"""
from __future__ import annotations

import logging
import sys

from src import canvas_service, whatsapp_service
from src.conversation import MAIN_MENU_BUTTONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def send_daily_reminder() -> None:
    logger.info("Fetching upcoming assignments...")
    try:
        items = canvas_service.get_upcoming_items()
    except Exception as e:
        logger.error("Failed to fetch upcoming items: %s", e)
        whatsapp_service.send_text("❌ Daily reminder failed — could not reach Canvas.")
        return

    if not items:
        body = "☀️ *Good morning!*\n\n✅ No upcoming assignments in the next 7 days. Enjoy your day!"
    else:
        lines = [
            "☀️ *Good morning! Here's your assignment summary:*\n",
        ]
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

    whatsapp_service.send_button_message(body, MAIN_MENU_BUTTONS)
    logger.info("Daily reminder sent successfully (%d items)", len(items))


if __name__ == "__main__":
    try:
        send_daily_reminder()
    except Exception as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
