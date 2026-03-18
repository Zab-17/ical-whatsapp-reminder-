"""Change detector — checks all users for new Canvas content."""
from __future__ import annotations

import json
import logging
import sys

from src import canvas_service, whatsapp_service
from src.database import get_all_users, get_user_snapshot, save_user_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_all_changes() -> None:
    users = get_all_users()
    logger.info("Running change detection for %d users", len(users))
    for user in users:
        try:
            detect_changes_for_user(user["phone"])
        except Exception as e:
            logger.error("Detection failed for %s: %s", user["phone"], e)


def detect_changes_for_user(phone: str) -> None:
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

    # Save updated snapshot
    save_user_snapshot(phone, {
        "assignment_ids": all_assignment_ids,
        "quiz_ids": all_quiz_ids,
        "announcement_ids": all_announcement_ids,
    })

    if new_items:
        header = f"🔔 *{len(new_items)} new item(s) detected!*\n"
        body = header + "\n\n".join(new_items)
        whatsapp_service.send_text(body, to=phone)
        logger.info("Sent %d new items to %s", len(new_items), phone)
    else:
        logger.info("No new items for %s", phone)


if __name__ == "__main__":
    detect_all_changes()
