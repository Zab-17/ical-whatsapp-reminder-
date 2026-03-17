"""Change detector entry point. Run with: python -m src.detector"""
from __future__ import annotations

import logging
import sys

from src import canvas_service, whatsapp_service
from src.snapshot import load_snapshot, save_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_changes() -> None:
    logger.info("Loading snapshot...")
    snapshot = load_snapshot()
    courses = canvas_service.get_active_courses()

    new_items: list[str] = []

    for course in courses:
        cid = course.id
        cname = course.short_name()

        # Check assignments
        try:
            current_assignments = canvas_service.get_all_assignment_ids(cid)
            known = set(snapshot.assignment_ids.get(cid, []))
            new_ids = [aid for aid in current_assignments if aid not in known]
            if new_ids:
                assignments = canvas_service.get_assignments(cid)
                for a in assignments:
                    if a.id in new_ids:
                        new_items.append(f"📝 *New Assignment* — {cname}\n   {a.name} (Due: {a.due_str()})")
            snapshot.assignment_ids[cid] = current_assignments
        except Exception as e:
            logger.warning("Failed to check assignments for %s: %s", cname, e)

        # Check quizzes
        try:
            current_quizzes = canvas_service.get_all_quiz_ids(cid)
            known = set(snapshot.quiz_ids.get(cid, []))
            new_ids = [qid for qid in current_quizzes if qid not in known]
            if new_ids:
                quizzes = canvas_service.get_quizzes(cid)
                for q in quizzes:
                    if q.id in new_ids:
                        new_items.append(f"❓ *New Quiz* — {cname}\n   {q.title} (Due: {q.due_str()})")
            snapshot.quiz_ids[cid] = current_quizzes
        except Exception as e:
            logger.warning("Failed to check quizzes for %s: %s", cname, e)

        # Check announcements
        try:
            current_announcements = canvas_service.get_all_announcement_ids(cid)
            known = set(snapshot.announcement_ids.get(cid, []))
            new_ids = [aid for aid in current_announcements if aid not in known]
            if new_ids:
                announcements = canvas_service.get_announcements(cid, recent=50)
                for a in announcements:
                    if a.id in new_ids:
                        new_items.append(f"📢 *New Announcement* — {cname}\n   {a.title}")
            snapshot.announcement_ids[cid] = current_announcements
        except Exception as e:
            logger.warning("Failed to check announcements for %s: %s", cname, e)

        # Check modules
        try:
            current_modules = canvas_service.get_all_module_ids(cid)
            known = set(snapshot.module_ids.get(cid, []))
            new_ids = [mid for mid in current_modules if mid not in known]
            if new_ids:
                modules = canvas_service.get_modules(cid)
                for m in modules:
                    if m.id in new_ids:
                        new_items.append(f"📦 *New Module* — {cname}\n   {m.name}")
            snapshot.module_ids[cid] = current_modules
        except Exception as e:
            logger.warning("Failed to check modules for %s: %s", cname, e)

    # Save updated snapshot
    save_snapshot(snapshot)

    if new_items:
        header = f"🔔 *{len(new_items)} new item(s) detected!*\n"
        body = header + "\n\n".join(new_items)
        whatsapp_service.send_text(body)
        logger.info("Sent change alert with %d new items", len(new_items))
    else:
        logger.info("No new items detected")


if __name__ == "__main__":
    try:
        detect_changes()
    except Exception as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
