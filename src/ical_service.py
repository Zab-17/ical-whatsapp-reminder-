"""Fetch and parse iCal calendar feeds for upcoming events/tasks."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from icalendar import Calendar

from src.models import AssignmentInfo, CAIRO_TZ

logger = logging.getLogger(__name__)


def is_valid_ical_url(url: str) -> bool:
    """Accept any URL that looks like an iCal feed. Blocks internal/private IPs."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    # Block internal/private hostnames
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False
    blocked = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]")
    if hostname in blocked:
        return False
    # Block private IP ranges
    if hostname.startswith(("10.", "192.168.", "172.")):
        return False
    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return False
    # Accept .ics extension or known calendar feed paths
    if parsed.path.endswith(".ics"):
        return True
    if "/feeds/calendars/" in parsed.path:
        return True
    if "calendar" in parsed.path.lower() and ("ical" in url.lower() or "ics" in url.lower()):
        return True
    return False


def fetch_upcoming_from_ical(ical_url: str, days: int = 10) -> list[AssignmentInfo]:
    """Fetch iCal feed and return upcoming events within the given window."""
    if not is_valid_ical_url(ical_url):
        raise ValueError("Invalid or blocked iCal URL")
    resp = httpx.get(ical_url.strip(), timeout=30, follow_redirects=False)
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
        is_date_only = not isinstance(due_at, datetime)
        # icalendar may return date (not datetime) — convert to datetime
        if is_date_only:
            # Date-only event (e.g., Canvas assignments) — set to 11:59 PM Cairo
            due_at = datetime.combine(due_at, datetime.min.time(), tzinfo=CAIRO_TZ)
            due_at = due_at.replace(hour=23, minute=59)
        elif due_at.tzinfo is not None:
            due_at = due_at.astimezone(timezone.utc)
        else:
            due_at = due_at.replace(tzinfo=timezone.utc)

        if not (now <= due_at <= cutoff):
            continue

        event_name, source_name = _parse_summary(summary, str(component.get("DESCRIPTION", "")))
        location = str(component.get("LOCATION", "")) if component.get("LOCATION") else ""

        items.append(AssignmentInfo(
            id=hash(summary) & 0x7FFFFFFF,
            name=event_name,
            due_at=due_at,
            course_name=source_name or location or "",
            course_id=0,
            submitted=False,
            date_only=is_date_only,
        ))

    items.sort(key=lambda a: a.due_at or datetime.max.replace(tzinfo=timezone.utc))
    return items


def fetch_all_from_feeds(feeds: list[dict], days: int = 10) -> list[AssignmentInfo]:
    """Fetch and merge upcoming items from multiple feeds."""
    all_items = []
    for feed in feeds:
        url = feed.get("url", "")
        label = feed.get("label", "")
        try:
            items = fetch_upcoming_from_ical(url, days)
            # Tag items with feed label if they have no source
            for item in items:
                if not item.course_name and label:
                    item.course_name = label
            all_items.extend(items)
        except Exception as e:
            logger.warning("Failed to fetch feed '%s' (%s): %s", label, url[:50], e)

    # Sort and deduplicate by name+date
    all_items.sort(key=lambda a: a.due_at or datetime.max.replace(tzinfo=timezone.utc))
    seen = set()
    deduped = []
    for item in all_items:
        key = f"{item.name}|{item.due_at}"
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _parse_summary(summary: str, description: str) -> tuple[str, str]:
    """Parse event summary into (event_name, source_name).

    Handles multiple formats:
    - Canvas: "Assignment Name [Course Name]"
    - Generic: "Event Name" (no source)
    - Google Calendar: just the event title
    """
    # Canvas format: "Assignment Name [Course Name]"
    match = re.search(r"\[(.+)\]\s*$", summary)
    if match:
        source = match.group(1).lstrip(".")
        name = re.sub(r"\s*\[.+\]\s*$", "", summary).strip()
        return name, source

    # Check description for course/source info
    for pattern in [r"Course:\s*(.+)", r"Calendar:\s*(.+)", r"Source:\s*(.+)"]:
        match = re.search(pattern, description)
        if match:
            return summary.strip(), match.group(1).strip()

    # Generic: just use summary as-is
    return summary.strip(), ""
