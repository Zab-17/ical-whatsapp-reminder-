from __future__ import annotations

import logging

from src import canvas_service
from src.models import AssignmentInfo

logger = logging.getLogger(__name__)

# Button IDs mapped to their text labels for the main menu
MAIN_MENU_BUTTONS = [
    {"id": "upcoming", "title": "Upcoming Due Dates"},
    {"id": "list_courses", "title": "My Courses"},
    {"id": "menu", "title": "Main Menu"},
]

COURSE_MENU_BUTTONS_TEMPLATE = [
    {"id": "assignments_{cid}", "title": "Assignments"},
    {"id": "quizzes_{cid}", "title": "Quizzes"},
    {"id": "more_{cid}", "title": "More..."},
]

MORE_MENU_BUTTONS_TEMPLATE = [
    {"id": "modules_{cid}", "title": "Modules"},
    {"id": "announcements_{cid}", "title": "Announcements"},
    {"id": "course_{cid}", "title": "Back to Course"},
]


def route(user_input: str) -> dict:
    """Route user input to the appropriate handler.

    Returns dict with 'body' (str) and optionally 'buttons' (list) or 'items' (list).
    """
    user_input = user_input.strip().lower()

    # Check if it's a numbered reply referencing a pending selection
    # This is handled by the webhook via session state

    if user_input in ("menu", "hi", "hello", "start", "hey"):
        return handle_main_menu()

    if user_input == "upcoming":
        return handle_upcoming()

    if user_input == "list_courses":
        return handle_list_courses()

    if user_input.startswith("course_"):
        course_id = _extract_id(user_input, "course_")
        if course_id:
            return handle_course_menu(course_id)

    if user_input.startswith("assignments_"):
        course_id = _extract_id(user_input, "assignments_")
        if course_id:
            return handle_assignments(course_id)

    if user_input.startswith("quizzes_"):
        course_id = _extract_id(user_input, "quizzes_")
        if course_id:
            return handle_quizzes(course_id)

    if user_input.startswith("more_"):
        course_id = _extract_id(user_input, "more_")
        if course_id:
            return handle_more_menu(course_id)

    if user_input.startswith("modules_"):
        course_id = _extract_id(user_input, "modules_")
        if course_id:
            return handle_modules(course_id)

    if user_input.startswith("announcements_"):
        course_id = _extract_id(user_input, "announcements_")
        if course_id:
            return handle_announcements(course_id)

    # Default: show main menu
    return handle_main_menu()


def handle_main_menu() -> dict:
    return {
        "body": "📚 *University Assignment Reminder*\n\nWhat would you like to check?",
        "buttons": MAIN_MENU_BUTTONS,
    }


def handle_upcoming() -> dict:
    try:
        items = canvas_service.get_upcoming_items()
    except Exception as e:
        logger.error("Failed to fetch upcoming items: %s", e)
        return {"body": "❌ Failed to fetch upcoming items. Please try again later.", "buttons": MAIN_MENU_BUTTONS}

    if not items:
        return {
            "body": "✅ No upcoming assignments in the next 7 days!",
            "buttons": MAIN_MENU_BUTTONS,
        }

    grouped = _group_by_date(items)
    lines = ["📅 *Upcoming Due Dates*\n"]
    for date_str, assignments in grouped.items():
        lines.append(f"*{date_str}*")
        for a in assignments:
            time_str = a.due_at.strftime("%I:%M %p") if a.due_at else ""
            lines.append(f"  • {a.name} ({a.course_name}) — {time_str}")
        lines.append("")

    return {
        "body": "\n".join(lines),
        "buttons": MAIN_MENU_BUTTONS,
    }


def handle_list_courses() -> dict:
    try:
        courses = canvas_service.get_active_courses()
    except Exception as e:
        logger.error("Failed to fetch courses: %s", e)
        return {"body": "❌ Failed to fetch courses. Please try again later.", "buttons": MAIN_MENU_BUTTONS}

    if not courses:
        return {"body": "No active courses found.", "buttons": MAIN_MENU_BUTTONS}

    items = [{"id": f"course_{c.id}", "title": c.short_name()} for c in courses]
    return {
        "body": "📖 *Your Courses*\n\nSelect a course:",
        "items": items,
    }


def handle_course_menu(course_id: int) -> dict:
    try:
        course = next(c for c in canvas_service.get_active_courses() if c.id == course_id)
        course_name = course.name
    except (StopIteration, Exception):
        course_name = "Selected Course"

    buttons = [
        {"id": f"assignments_{course_id}", "title": "Assignments"},
        {"id": f"quizzes_{course_id}", "title": "Quizzes"},
        {"id": f"more_{course_id}", "title": "More..."},
    ]
    return {
        "body": f"📖 *{course_name}*\n\nWhat would you like to see?",
        "buttons": buttons,
    }


def handle_assignments(course_id: int) -> dict:
    try:
        assignments = canvas_service.get_assignments(course_id, upcoming_only=False)
    except Exception as e:
        logger.error("Failed to fetch assignments: %s", e)
        return {"body": "❌ Failed to fetch assignments.", "buttons": MAIN_MENU_BUTTONS}

    if not assignments:
        body = "No assignments found for this course."
    else:
        lines = ["📝 *Assignments*\n"]
        for a in assignments[:15]:
            status = "✅" if a.submitted else "⏳"
            lines.append(f"{status} {a.name}")
            lines.append(f"   Due: {a.due_str()}")
            if a.points:
                lines.append(f"   Points: {a.points}")
            lines.append("")
        body = "\n".join(lines)

    buttons = [
        {"id": f"course_{course_id}", "title": "Back to Course"},
        {"id": "menu", "title": "Main Menu"},
    ]
    return {"body": body, "buttons": buttons}


def handle_quizzes(course_id: int) -> dict:
    try:
        quizzes = canvas_service.get_quizzes(course_id)
    except Exception as e:
        logger.error("Failed to fetch quizzes: %s", e)
        return {"body": "❌ Failed to fetch quizzes.", "buttons": MAIN_MENU_BUTTONS}

    if not quizzes:
        body = "No quizzes found for this course."
    else:
        lines = ["📝 *Quizzes*\n"]
        for q in quizzes[:10]:
            lines.append(f"• {q.title}")
            lines.append(f"  Due: {q.due_str()}")
            if q.time_limit:
                lines.append(f"  Time limit: {q.time_limit} min")
            lines.append("")
        body = "\n".join(lines)

    buttons = [
        {"id": f"course_{course_id}", "title": "Back to Course"},
        {"id": "menu", "title": "Main Menu"},
    ]
    return {"body": body, "buttons": buttons}


def handle_more_menu(course_id: int) -> dict:
    buttons = [
        {"id": f"modules_{course_id}", "title": "Modules"},
        {"id": f"announcements_{course_id}", "title": "Announcements"},
        {"id": f"course_{course_id}", "title": "Back to Course"},
    ]
    return {
        "body": "What else would you like to see?",
        "buttons": buttons,
    }


def handle_modules(course_id: int) -> dict:
    try:
        modules = canvas_service.get_modules(course_id)
    except Exception as e:
        logger.error("Failed to fetch modules: %s", e)
        return {"body": "❌ Failed to fetch modules.", "buttons": MAIN_MENU_BUTTONS}

    if not modules:
        body = "No modules found for this course."
    else:
        lines = ["📦 *Modules*\n"]
        for m in modules:
            lines.append(f"• {m.name} ({m.items_count} items)")
        body = "\n".join(lines)

    buttons = [
        {"id": f"course_{course_id}", "title": "Back to Course"},
        {"id": "menu", "title": "Main Menu"},
    ]
    return {"body": body, "buttons": buttons}


def handle_announcements(course_id: int) -> dict:
    try:
        announcements = canvas_service.get_announcements(course_id)
    except Exception as e:
        logger.error("Failed to fetch announcements: %s", e)
        return {"body": "❌ Failed to fetch announcements.", "buttons": MAIN_MENU_BUTTONS}

    if not announcements:
        body = "No recent announcements for this course."
    else:
        lines = ["📢 *Announcements*\n"]
        for a in announcements:
            lines.append(f"*{a.title}*")
            lines.append(f"  Posted: {a.posted_str()}")
            if a.message_preview:
                lines.append(f"  {a.message_preview}")
            lines.append("")
        body = "\n".join(lines)

    buttons = [
        {"id": f"course_{course_id}", "title": "Back to Course"},
        {"id": "menu", "title": "Main Menu"},
    ]
    return {"body": body, "buttons": buttons}


def _extract_id(text: str, prefix: str) -> int | None:
    try:
        return int(text[len(prefix):])
    except (ValueError, IndexError):
        return None


def _group_by_date(items: list[AssignmentInfo]) -> dict[str, list[AssignmentInfo]]:
    grouped: dict[str, list[AssignmentInfo]] = {}
    for item in items:
        if item.due_at:
            date_key = item.due_at.strftime("%A, %b %d")
        else:
            date_key = "No due date"
        grouped.setdefault(date_key, []).append(item)
    return grouped
