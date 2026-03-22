"""Fetch and parse Canvas iCal calendar feeds for assignment due dates."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from icalendar import Calendar

from src.models import AssignmentInfo

logger = logging.getLogger(__name__)

CANVAS_FEED_PATTERN = re.compile(r"https?://[^/]+/feeds/calendars/user_\w+\.ics")


def is_valid_ical_url(url: str) -> bool:
    return bool(CANVAS_FEED_PATTERN.match(url.strip()))


def fetch_upcoming_from_ical(ical_url: str, days: int = 7) -> list[AssignmentInfo]:
    """Fetch iCal feed and return upcoming assignments within the given window."""
    resp = httpx.get(ical_url.strip(), timeout=30)
    resp.raise_for_status()

    cal = Calendar.from_ical(resp.text)
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)

    items = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("SUMMARY", ""))
        dtstart = component.get("DTSTART")
        if not dtstart:
            continue

        due_at = dtstart.dt
        # icalendar may return date (not datetime) — convert to datetime
        if not isinstance(due_at, datetime):
            due_at = datetime.combine(due_at, datetime.min.time(), tzinfo=timezone.utc)
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)

        if not (now <= due_at <= cutoff):
            continue

        # Canvas iCal format: "Assignment Name [Course Name]" or "Course Name - Assignment Name"
        course_name = _extract_course_name(summary, str(component.get("DESCRIPTION", "")))
        assignment_name = _extract_assignment_name(summary)

        items.append(AssignmentInfo(
            id=hash(summary) & 0x7FFFFFFF,  # stable pseudo-ID from name
            name=assignment_name,
            due_at=due_at,
            course_name=course_name,
            course_id=0,
            submitted=False,  # iCal doesn't have submission status
        ))

    items.sort(key=lambda a: a.due_at or datetime.max.replace(tzinfo=timezone.utc))
    return items


def _extract_course_name(summary: str, description: str) -> str:
    """Extract course name from iCal event summary or description."""
    # Canvas format: "Assignment Name [Full Course Name]"
    # Use greedy match to capture full name including parentheses
    match = re.search(r"\[(.+)\]\s*$", summary)
    if match:
        return match.group(1).lstrip(".")
    # Fallback: check description for course info
    match = re.search(r"Course:\s*(.+)", description)
    if match:
        return match.group(1).strip()
    return "Unknown Course"


def _extract_assignment_name(summary: str) -> str:
    """Strip course tag from summary to get clean assignment name."""
    # Remove trailing "[Course Code]"
    return re.sub(r"\s*\[.+?\]\s*$", "", summary).strip()
