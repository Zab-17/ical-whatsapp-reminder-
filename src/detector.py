"""Change detector — checks all users for new calendar events."""
from __future__ import annotations

import json
import logging
import sys
from datetime import timezone, timedelta

from src import canvas_service, ical_service, whatsapp_service
from src.database import get_active_users, get_user_snapshot, save_user_snapshot, get_user_feeds
from src.models import CAIRO_TZ

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_all_changes() -> None:
    users = get_active_users()
    logger.info("Running change detection for %d users", len(users))
    for user in users:
        try:
            detect_changes_for_user(user["phone"])
        except Exception as e:
            logger.error("Detection failed for %s: %s", user["phone"], e)


def detect_changes_for_user(phone: str) -> None:
    feeds = get_user_feeds(phone)

    if feeds:
        _detect_ical_changes(phone, feeds)
    else:
        _detect_canvas_changes(phone)


def _detect_ical_changes(phone: str, feeds: list[dict]) -> None:
    """Detect new events in iCal feeds by comparing event keys."""
    snapshot = get_user_snapshot(phone)
    known_events = set(snapshot.get("ical_event_keys", []))

    try:
        items = ical_service.fetch_all_from_feeds(feeds, days=14)
    except Exception as e:
        logger.warning("Failed to fetch feeds for %s: %s", phone, e)
        return

    current_keys = set()
    new_items = []

    for item in items:
        key = f"{item.name}|{item.due_at.isoformat() if item.due_at else ''}"
        current_keys.add(key)
        if key not in known_events and known_events:
            cairo = item.due_at.astimezone(CAIRO_TZ) if item.due_at else None
            date_str = cairo.strftime("%b %d, %I:%M %p") if cairo else "No date"
            source = f" — {item.course_name}" if item.course_name else ""
            new_items.append(f"📝 *{item.name}*{source}\n   Due: {date_str}")

    # Merge into snapshot (preserve other keys like last_reminder)
    snapshot["ical_event_keys"] = list(current_keys)
    save_user_snapshot(phone, snapshot)

    if new_items:
        header = f"🔔 *{len(new_items)} new event(s) detected!*\n"
        body = header + "\n\n".join(new_items[:10])  # cap at 10 to avoid huge messages
        whatsapp_service.send_text(body, to=phone)
        logger.info("Sent %d new items to %s", len(new_items), phone)
    else:
        logger.info("No new items for %s", phone)


def _detect_canvas_changes(phone: str) -> None:
    """Legacy Canvas cookie-based detection."""
    snapshot = get_user_snapshot(phone)
    known_assignments = set(snapshot.get("assignment_ids", []))
    known_quizzes = set(snapshot.get("quiz_ids", []))
    known_announcements = set(snapshot.get("announcement_ids", []))

    try:
        courses = canvas_service.get_active_courses(phone)
    except Exception:
        logger.warning("Skipping %s — Canvas session may be expired", phone)
        return

    new_items: list[str] = []
    all_assignment_ids = []
    all_quiz_ids = []
    all_announcement_ids = []

    for course in courses:
        cid = course.id
        cname = course.short_name()

        try:
            assignments = canvas_service.get_assignments(phone, cid)
            for a in assignments:
                all_assignment_ids.append(a.id)
                if a.id not in known_assignments and known_assignments:
                    new_items.append(f"📝 *New Assignment* — {cname}\n   {a.name} (Due: {a.due_str()})")
        except Exception:
            pass

        try:
            quizzes = canvas_service.get_quizzes(phone, cid)
            for q in quizzes:
                all_quiz_ids.append(q.id)
                if q.id not in known_quizzes and known_quizzes:
                    new_items.append(f"❓ *New Quiz* — {cname}\n   {q.title} (Due: {q.due_str()})")
        except Exception:
            pass

        try:
            announcements = canvas_service.get_announcements(phone, cid, recent=20)
            for a in announcements:
                all_announcement_ids.append(a.id)
                if a.id not in known_announcements and known_announcements:
                    new_items.append(f"📢 *New Announcement* — {cname}\n   {a.title}")
        except Exception:
            pass

    snapshot["assignment_ids"] = all_assignment_ids
    snapshot["quiz_ids"] = all_quiz_ids
    snapshot["announcement_ids"] = all_announcement_ids
    save_user_snapshot(phone, snapshot)

    if new_items:
        header = f"🔔 *{len(new_items)} new item(s) detected!*\n"
        body = header + "\n\n".join(new_items)
        whatsapp_service.send_text(body, to=phone)
        logger.info("Sent %d new items to %s", len(new_items), phone)
    else:
        logger.info("No new items for %s", phone)


if __name__ == "__main__":
    detect_all_changes()
