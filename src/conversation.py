from __future__ import annotations

import logging

from datetime import timezone, timedelta

from src import canvas_service, ical_service
from src.models import AssignmentInfo
from src.database import get_user_feeds

CAIRO_TZ = timezone(timedelta(hours=2))

logger = logging.getLogger(__name__)

MAIN_MENU_BUTTONS = [
    {"id": "upcoming", "title": "Upcoming Events"},
    {"id": "announcements", "title": "Announcements"},
    {"id": "feeds", "title": "My Feeds"},
    {"id": "settings", "title": "Settings"},
]


def route(user_input: str, phone: str) -> dict:
    raw_input = user_input.strip()
    user_input = raw_input.lower()

    # Detect iCal feed URL (case-sensitive check on raw input)
    if ical_service.is_valid_ical_url(raw_input):
        return handle_ical_registration(phone, raw_input)

    if user_input in ("menu", "hi", "hello", "start", "hey"):
        return handle_main_menu()
    if user_input == "upcoming":
        return handle_upcoming(phone)
    if user_input in ("announcements", "announce", "news"):
        return handle_announcements_feed(phone)
    if user_input in ("discussions", "discuss"):
        return handle_discussions_feed(phone)
    if user_input in ("pages", "wiki"):
        return handle_wiki_feed(phone)
    if user_input == "canvas" or user_input == "feed":
        return handle_full_feed(phone)
    if user_input == "list_courses":
        return handle_list_courses(phone)
    if user_input == "settings":
        return handle_settings(phone)
    if user_input.startswith("done ") or user_input.startswith("done"):
        return handle_done(phone, user_input)
    if user_input == "undone":
        return handle_undone(phone)
    if user_input.startswith("restore "):
        return handle_restore(phone, user_input)
    if user_input == "feeds" or user_input == "my feeds":
        return handle_list_feeds(phone)
    if user_input.startswith("remove feed "):
        return handle_remove_feed(phone, user_input)
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


def handle_ical_registration(phone: str, url: str) -> dict:
    from src.database import add_user_feed
    # Verify the URL works before saving
    try:
        items = ical_service.fetch_upcoming_from_ical(url)
    except Exception as e:
        logger.error("Invalid iCal URL for %s: %s", phone, e)
        return {
            "body": "❌ That URL didn't work. Make sure you copied a valid iCal (.ics) feed URL.",
            "buttons": MAIN_MENU_BUTTONS,
        }

    added = add_user_feed(phone, url.strip())
    count = len(items)
    feeds = get_user_feeds(phone)
    if not added:
        return {"body": "ℹ️ This feed is already connected!", "buttons": MAIN_MENU_BUTTONS}
    return {
        "body": f"✅ *Feed connected!* ({len(feeds)} total)\n\n"
                f"Found {count} upcoming events. Send *feeds* to manage your feeds.",
        "buttons": MAIN_MENU_BUTTONS,
    }


def handle_list_feeds(phone: str) -> dict:
    feeds = get_user_feeds(phone)
    if not feeds:
        return {"body": "No feeds connected yet.\n\nSend an iCal (.ics) URL to add one.", "buttons": MAIN_MENU_BUTTONS}

    lines = ["📡 *Your Feeds:*\n"]
    for i, feed in enumerate(feeds, 1):
        label = feed.get("label", f"Feed {i}")
        url_short = feed["url"][:50] + "..." if len(feed["url"]) > 50 else feed["url"]
        lines.append(f"  {i}. *{label}*")
        lines.append(f"    {url_short}")
    lines.append(f"\nSend an iCal URL to add another feed.")
    lines.append('Send *"remove feed 1"* to remove a feed.')
    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_remove_feed(phone: str, user_input: str) -> dict:
    from src.database import remove_user_feed
    parts = user_input.strip().split()
    if len(parts) != 3 or not parts[2].isdigit():
        return {"body": '💡 Usage: *remove feed 1*', "buttons": MAIN_MENU_BUTTONS}

    idx = int(parts[2])
    removed = remove_user_feed(phone, idx)
    if not removed:
        feeds = get_user_feeds(phone)
        return {"body": f"❌ Invalid number. Choose between 1 and {len(feeds)}.", "buttons": MAIN_MENU_BUTTONS}

    return {"body": f"✅ *{removed['label']}* removed!", "buttons": MAIN_MENU_BUTTONS}


def handle_done(phone: str, user_input: str) -> dict:
    from src.database import add_dismissed_item
    from src.reminder import get_last_reminder_items

    # Parse "done 1" or "done 2"
    parts = user_input.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return {"body": '💡 Usage: *done 1* to mark item #1 as submitted.\nSend *undone* to see dismissed items.', "buttons": MAIN_MENU_BUTTONS}

    idx = int(parts[1])
    items = get_last_reminder_items(phone)
    if not items or idx < 1 or idx > len(items):
        return {"body": f"❌ Invalid number. Choose between 1 and {len(items)}.", "buttons": MAIN_MENU_BUTTONS}

    item = items[idx - 1]
    add_dismissed_item(phone, item["key"])
    return {
        "body": f'✅ *{item["name"]}* marked as done!\n\nYou won\'t be reminded about it anymore.\nSend *undone* to undo.',
        "buttons": MAIN_MENU_BUTTONS,
    }


def handle_undone(phone: str) -> dict:
    from src.database import get_dismissed_items

    dismissed = get_dismissed_items(phone)
    if not dismissed:
        return {"body": "No dismissed items. Everything is active!", "buttons": MAIN_MENU_BUTTONS}

    lines = ["📋 *Dismissed items:*\n"]
    for i, key in enumerate(sorted(dismissed), 1):
        name = key.split("|")[0]  # extract name from "name|course" key
        lines.append(f"  {i}. {name}")
    lines.append('\n_Reply "restore 1" to get reminders again, or "restore all" to restore everything._')
    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_restore(phone: str, user_input: str) -> dict:
    from src.database import get_dismissed_items, remove_dismissed_item, clear_dismissed_items

    parts = user_input.strip().split()
    if len(parts) != 2:
        return {"body": '💡 Usage: *restore 1* or *restore all*', "buttons": MAIN_MENU_BUTTONS}

    if parts[1] == "all":
        clear_dismissed_items(phone)
        return {"body": "✅ All items restored! You'll be reminded about everything again.", "buttons": MAIN_MENU_BUTTONS}

    if not parts[1].isdigit():
        return {"body": '💡 Usage: *restore 1* or *restore all*', "buttons": MAIN_MENU_BUTTONS}

    idx = int(parts[1])
    dismissed = sorted(get_dismissed_items(phone))
    if idx < 1 or idx > len(dismissed):
        return {"body": f"❌ Invalid number. Choose between 1 and {len(dismissed)}.", "buttons": MAIN_MENU_BUTTONS}

    key = dismissed[idx - 1]
    name = key.split("|")[0]
    remove_dismissed_item(phone, key)
    return {"body": f"✅ *{name}* restored! You'll be reminded about it again.", "buttons": MAIN_MENU_BUTTONS}


def handle_main_menu() -> dict:
    return {
        "body": "📅 *Reminder Bot*\n\nWhat would you like to check?",
        "buttons": MAIN_MENU_BUTTONS,
    }


def _format_feed_item(item: dict, emoji: str = "📢") -> str:
    """Format a single feed item for display."""
    lines = [f"{emoji} *{item['title']}*"]
    meta = []
    if item.get("course"):
        meta.append(item["course"])
    if item.get("author") and item["author"] != "Wiki Page":
        meta.append(f"By: {item['author']}")
    if item.get("posted_at"):
        cairo = item["posted_at"].astimezone(CAIRO_TZ)
        meta.append(cairo.strftime("%b %d, %I:%M %p"))
    if meta:
        lines.append("_" + " · ".join(meta) + "_")
    if item.get("content"):
        lines.append(item["content"])
    return "\n".join(lines)


def _no_canvas_feed_msg() -> dict:
    return {"body": "This feature is only available for Canvas calendar feeds.", "buttons": MAIN_MENU_BUTTONS}


def handle_announcements_feed(phone: str) -> dict:
    """Show announcements from Canvas Atom feed."""
    feeds = get_user_feeds(phone)
    if not feeds:
        return {"body": "No feeds connected. Send an iCal URL to get started.", "buttons": MAIN_MENU_BUTTONS}
    if not ical_service.get_announcements_feed_url(feeds):
        return _no_canvas_feed_msg()

    announcements = ical_service.fetch_announcements_from_atom(feeds)
    if not announcements:
        return {"body": "📢 No recent announcements.", "buttons": MAIN_MENU_BUTTONS}

    lines = [f"📢 *Announcements* ({len(announcements)})\n"]
    for a in announcements:
        lines.append(_format_feed_item(a, "📢"))
        lines.append("─" * 20)

    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_discussions_feed(phone: str) -> dict:
    """Show discussions from Canvas Atom feed."""
    feeds = get_user_feeds(phone)
    if not feeds:
        return {"body": "No feeds connected. Send an iCal URL to get started.", "buttons": MAIN_MENU_BUTTONS}
    if not ical_service.get_announcements_feed_url(feeds):
        return _no_canvas_feed_msg()

    discussions = ical_service.fetch_discussions_from_atom(feeds)
    if not discussions:
        return {"body": "💬 No recent discussions.", "buttons": MAIN_MENU_BUTTONS}

    lines = [f"💬 *Discussions* ({len(discussions)})\n"]
    for d in discussions:
        lines.append(_format_feed_item(d, "💬"))
        lines.append("─" * 20)

    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_wiki_feed(phone: str) -> dict:
    """Show wiki page updates from Canvas Atom feed."""
    feeds = get_user_feeds(phone)
    if not feeds:
        return {"body": "No feeds connected. Send an iCal URL to get started.", "buttons": MAIN_MENU_BUTTONS}
    if not ical_service.get_announcements_feed_url(feeds):
        return _no_canvas_feed_msg()

    pages = ical_service.fetch_wiki_pages_from_atom(feeds)
    if not pages:
        return {"body": "📄 No recent page updates.", "buttons": MAIN_MENU_BUTTONS}

    lines = [f"📄 *Page Updates* ({len(pages)})\n"]
    for p in pages:
        lines.append(_format_feed_item(p, "📄"))
        lines.append("─" * 20)

    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_full_feed(phone: str) -> dict:
    """Show everything from Canvas Atom feed — announcements, discussions, wiki pages."""
    feeds = get_user_feeds(phone)
    if not feeds:
        return {"body": "No feeds connected. Send an iCal URL to get started.", "buttons": MAIN_MENU_BUTTONS}
    if not ical_service.get_announcements_feed_url(feeds):
        return _no_canvas_feed_msg()

    grouped = ical_service.fetch_all_from_atom(feeds)
    lines = ["📋 *Canvas Feed* (last 14 days)\n"]
    total = 0

    type_config = [
        ("announcement", "📢", "Announcements"),
        ("discussion", "💬", "Discussions"),
        ("wiki", "📄", "Page Updates"),
    ]

    for type_key, emoji, label in type_config:
        items = grouped.get(type_key, [])
        if not items:
            continue
        total += len(items)
        lines.append(f"\n*{emoji} {label}* ({len(items)})")
        lines.append("")
        for item in items:
            lines.append(_format_feed_item(item, emoji))
            lines.append("─" * 20)

    if total == 0:
        return {"body": "📋 No recent Canvas activity.", "buttons": MAIN_MENU_BUTTONS}

    return {"body": "\n".join(lines), "buttons": MAIN_MENU_BUTTONS}


def handle_upcoming(phone: str) -> dict:
    from src.database import get_dismissed_items
    from src.reminder import _item_key, _save_last_reminder_items

    feeds = get_user_feeds(phone)
    try:
        if feeds:
            items = ical_service.fetch_all_from_feeds(feeds)
        else:
            items = canvas_service.get_upcoming_items(phone)
    except Exception as e:
        logger.error("Failed to fetch upcoming items: %s", e)
        return {"body": "❌ Failed to fetch upcoming items. Your session may have expired.\nVisit the login page to reconnect.", "buttons": MAIN_MENU_BUTTONS}

    # Filter out dismissed items
    dismissed = get_dismissed_items(phone)
    items = [a for a in items if _item_key(a) not in dismissed]

    if not items:
        return {"body": "✅ No upcoming events in the next 14 days!", "buttons": MAIN_MENU_BUTTONS}

    # Save for "done N" reference
    _save_last_reminder_items(phone, items)

    lines = ["📅 *Upcoming Events*\n"]
    current_date = None
    for i, a in enumerate(items, 1):
        cairo = a.due_at.astimezone(CAIRO_TZ) if a.due_at else None
        date_str = cairo.strftime("%A, %b %d") if cairo else "No date"
        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n*{date_str}*")
        time_str = cairo.strftime("%I:%M %p") if cairo else ""
        source = f" ({a.course_name})" if a.course_name else ""
        lines.append(f"  {i}. {a.name}{source} — {time_str}")
    lines.append(f'\n_Reply "done 1" to mark as submitted_')

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
    "settime_default": ("Default (10am, 10pm)", [8, 20]),
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
