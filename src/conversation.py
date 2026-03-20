from __future__ import annotations

import logging

from datetime import timezone, timedelta

from src import canvas_service
from src.models import AssignmentInfo

CAIRO_TZ = timezone(timedelta(hours=2))

logger = logging.getLogger(__name__)

MAIN_MENU_BUTTONS = [
    {"id": "upcoming", "title": "Upcoming Due Dates"},
    {"id": "list_courses", "title": "My Courses"},
    {"id": "settings", "title": "Settings"},
]


def route(user_input: str, phone: str) -> dict:
    user_input = user_input.strip().lower()

    if user_input in ("menu", "hi", "hello", "start", "hey"):
        return handle_main_menu()
    if user_input == "upcoming":
        return handle_upcoming(phone)
    if user_input == "list_courses":
        return handle_list_courses(phone)
    if user_input == "settings":
        return handle_settings(phone)
    if user_input.startswith("settime_"):
        return handle_set_time(phone, user_input)
    if user_input.startswith("course_"):
        cid = _extract_id(user_input, "course_")
        if cid:
            return handle_course_menu(phone, cid)
    if user_input.startswith("assignments_"):
        cid = _extract_id(user_input, "assignments_")
        if cid:
            return handle_assignments(phone, cid)
    if user_input.startswith("quizzes_"):
        cid = _extract_id(user_input, "quizzes_")
        if cid:
            return handle_quizzes(phone, cid)
    if user_input.startswith("more_"):
        cid = _extract_id(user_input, "more_")
        if cid:
            return handle_more_menu(cid)
    if user_input.startswith("modules_"):
        cid = _extract_id(user_input, "modules_")
        if cid:
            return handle_modules(phone, cid)
    if user_input.startswith("announcements_"):
        cid = _extract_id(user_input, "announcements_")
        if cid:
            return handle_announcements(phone, cid)

    return handle_main_menu()


def handle_main_menu() -> dict:
    return {
        "body": "📚 *University Assignment Reminder*\n\nWhat would you like to check?",
        "buttons": MAIN_MENU_BUTTONS,
    }


def handle_upcoming(phone: str) -> dict:
    try:
        items = canvas_service.get_upcoming_items(phone)
    except Exception as e:
        logger.error("Failed to fetch upcoming items: %s", e)
        return {"body": "❌ Failed to fetch upcoming items. Your session may have expired.\nVisit the login page to reconnect.", "buttons": MAIN_MENU_BUTTONS}

    if not items:
        return {"body": "✅ No upcoming assignments in the next 7 days!", "buttons": MAIN_MENU_BUTTONS}

    grouped = _group_by_date(items)
    lines = ["📅 *Upcoming Due Dates*\n"]
    for date_str, assignments in grouped.items():
        lines.append(f"*{date_str}*")
        for a in assignments:
            cairo = a.due_at.astimezone(CAIRO_TZ) if a.due_at else None
            time_str = cairo.strftime("%I:%M %p") if cairo else ""
            lines.append(f"  • {a.name} ({a.course_name}) — {time_str}")
        lines.append("")

    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_list_courses(phone: str) -> dict:
    try:
        courses = canvas_service.get_active_courses(phone)
    except Exception as e:
        logger.error("Failed to fetch courses: %s", e)
        return {"body": "❌ Failed to fetch courses.", "buttons": MAIN_MENU_BUTTONS}

    if not courses:
        return {"body": "No active courses found.", "buttons": MAIN_MENU_BUTTONS}

    items = [{"id": f"course_{c.id}", "title": c.short_name()} for c in courses]
    return {"body": "📖 *Your Courses*\n\nSelect a course:", "items": items}


def handle_course_menu(phone: str, course_id: int) -> dict:
    try:
        course = next(c for c in canvas_service.get_active_courses(phone) if c.id == course_id)
        name = course.name
    except Exception:
        name = "Selected Course"

    buttons = [
        {"id": f"assignments_{course_id}", "title": "Assignments"},
        {"id": f"quizzes_{course_id}", "title": "Quizzes"},
        {"id": f"more_{course_id}", "title": "More..."},
    ]
    return {"body": f"📖 *{name}*\n\nWhat would you like to see?", "buttons": buttons}


def handle_assignments(phone: str, course_id: int) -> dict:
    try:
        assignments = canvas_service.get_assignments(phone, course_id)
    except Exception:
        return {"body": "❌ Failed to fetch assignments.", "buttons": MAIN_MENU_BUTTONS}

    if not assignments:
        body = "No assignments found."
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

    buttons = [{"id": f"course_{course_id}", "title": "Back to Course"}, {"id": "menu", "title": "Main Menu"}]
    return {"body": body, "buttons": buttons}


def handle_quizzes(phone: str, course_id: int) -> dict:
    try:
        quizzes = canvas_service.get_quizzes(phone, course_id)
    except Exception:
        return {"body": "❌ Failed to fetch quizzes.", "buttons": MAIN_MENU_BUTTONS}

    if not quizzes:
        body = "No quizzes found."
    else:
        lines = ["📝 *Quizzes*\n"]
        for q in quizzes[:10]:
            lines.append(f"• {q.title}")
            lines.append(f"  Due: {q.due_str()}")
            if q.time_limit:
                lines.append(f"  Time limit: {q.time_limit} min")
            lines.append("")
        body = "\n".join(lines)

    buttons = [{"id": f"course_{course_id}", "title": "Back to Course"}, {"id": "menu", "title": "Main Menu"}]
    return {"body": body, "buttons": buttons}


def handle_more_menu(course_id: int) -> dict:
    buttons = [
        {"id": f"modules_{course_id}", "title": "Modules"},
        {"id": f"announcements_{course_id}", "title": "Announcements"},
        {"id": f"course_{course_id}", "title": "Back to Course"},
    ]
    return {"body": "What else would you like to see?", "buttons": buttons}


def handle_modules(phone: str, course_id: int) -> dict:
    try:
        modules = canvas_service.get_modules(phone, course_id)
    except Exception:
        return {"body": "❌ Failed to fetch modules.", "buttons": MAIN_MENU_BUTTONS}

    if not modules:
        body = "No modules found."
    else:
        lines = ["📦 *Modules*\n"]
        for m in modules:
            lines.append(f"• {m.name} ({m.items_count} items)")
        body = "\n".join(lines)

    buttons = [{"id": f"course_{course_id}", "title": "Back to Course"}, {"id": "menu", "title": "Main Menu"}]
    return {"body": body, "buttons": buttons}


def handle_announcements(phone: str, course_id: int) -> dict:
    try:
        announcements = canvas_service.get_announcements(phone, course_id)
    except Exception:
        return {"body": "❌ Failed to fetch announcements.", "buttons": MAIN_MENU_BUTTONS}

    if not announcements:
        body = "No recent announcements."
    else:
        lines = ["📢 *Announcements*\n"]
        for a in announcements:
            lines.append(f"*{a.title}*")
            lines.append(f"  Posted: {a.posted_str()}")
            if a.message_preview:
                lines.append(f"  {a.message_preview}")
            lines.append("")
        body = "\n".join(lines)

    buttons = [{"id": f"course_{course_id}", "title": "Back to Course"}, {"id": "menu", "title": "Main Menu"}]
    return {"body": body, "buttons": buttons}


TIME_PRESETS = {
    "settime_morning": ("Morning only", [8]),
    "settime_default": ("Default (10am,1pm,5pm,9pm)", [8, 11, 15, 19]),
    "settime_busy": ("Busy schedule (1pm, 9pm)", [11, 19]),
    "settime_night": ("Night owl (5pm, 9pm, 12am)", [15, 19, 22]),
    "settime_all": ("Every 3 hours", [6, 9, 12, 15, 18, 21]),
}

UTC_TO_CAIRO = {6: "8am", 7: "9am", 8: "10am", 9: "11am", 10: "12pm", 11: "1pm",
                12: "2pm", 13: "3pm", 14: "4pm", 15: "5pm", 16: "6pm", 17: "7pm",
                18: "8pm", 19: "9pm", 20: "10pm", 21: "11pm", 22: "12am"}


def handle_settings(phone: str) -> dict:
    from src.database import get_user_reminder_hours
    current = get_user_reminder_hours(phone)
    current_str = ", ".join(UTC_TO_CAIRO.get(h, f"{h}:00") for h in current)

    body = f"⚙️ *Settings*\n\nCurrent reminder times: *{current_str}*\n\nChoose a schedule:"
    items = [{"id": k, "title": v[0]} for k, v in TIME_PRESETS.items()]
    return {"body": body, "items": items}


def handle_set_time(phone: str, user_input: str) -> dict:
    from src.database import set_user_reminder_hours
    preset = TIME_PRESETS.get(user_input)
    if not preset:
        return {"body": "Invalid option.", "buttons": MAIN_MENU_BUTTONS}

    name, hours = preset
    set_user_reminder_hours(phone, hours)
    times_str = ", ".join(UTC_TO_CAIRO.get(h, f"{h}:00") for h in hours)
    return {
        "body": f"✅ Reminder times updated to: *{times_str}*",
        "buttons": MAIN_MENU_BUTTONS,
    }


def _extract_id(text: str, prefix: str) -> int | None:
    try:
        return int(text[len(prefix):])
    except (ValueError, IndexError):
        return None


def _group_by_date(items: list[AssignmentInfo]) -> dict[str, list[AssignmentInfo]]:
    grouped: dict[str, list[AssignmentInfo]] = {}
    for item in items:
        cairo = item.due_at.astimezone(CAIRO_TZ) if item.due_at else None
        key = cairo.strftime("%A, %b %d") if cairo else "No due date"
        grouped.setdefault(key, []).append(item)
    return grouped
