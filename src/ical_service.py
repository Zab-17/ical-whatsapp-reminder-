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


def get_announcements_feed_url(feeds: list[dict]) -> str | None:
    """Derive the user Atom feed URL from a Canvas iCal feed URL.

    Canvas calendar feeds:      /feeds/calendars/user_XXXXX.ics
    Canvas user feeds (Atom):   /feeds/users/user_XXXXX.atom
    The user feed includes announcements from ALL enrolled courses.
    """
    for feed in feeds:
        url = feed.get("url", "")
        match = re.search(r"/feeds/calendars/(user_[^/.]+)", url)
        if match:
            user_code = match.group(1)
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.hostname}/feeds/users/{user_code}.atom"
    return None


def _fetch_user_atom_feed(feeds: list[dict]) -> list[dict]:
    """Fetch and parse ALL entries from the Canvas user Atom feed."""
    atom_url = get_announcements_feed_url(feeds)
    if not atom_url:
        return []

    try:
        resp = httpx.get(atom_url, timeout=30, follow_redirects=False)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch Atom feed: %s", e)
        return []

    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        logger.warning("Failed to parse Atom feed: %s", e)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)

    items = []
    for entry in entries:
        title = entry.findtext("atom:title", "", ns).strip()
        entry_id = entry.findtext("atom:id", "", ns)
        content_el = entry.find("atom:content", ns)
        content = content_el.text if content_el is not None and content_el.text else ""
        updated = entry.findtext("atom:updated", "", ns)
        author = entry.findtext("atom:author/atom:name", "", ns)
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""

        # Strip HTML, preserve line breaks
        full_text = re.sub(r"<br\s*/?>", "\n", content)
        full_text = re.sub(r"<p[^>]*>", "\n", full_text)
        full_text = re.sub(r"</p>", "", full_text)
        full_text = re.sub(r"<[^>]+>", "", full_text)
        full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()

        # Determine type from title prefix and entry_id
        entry_id_lower = entry_id.lower()
        title_lower = title.lower()
        if "announcement" in title_lower or "announcement" in entry_id_lower:
            item_type = "announcement"
        elif "discussion" in title_lower or "discussion_topic" in entry_id_lower:
            item_type = "discussion"
        elif "assignment" in title_lower or "assignment" in entry_id_lower:
            item_type = "assignment"
        elif "wiki" in title_lower or "wiki_page" in entry_id_lower:
            item_type = "wiki"
        elif "calendar" in title_lower or "calendar_event" in entry_id_lower:
            item_type = "calendar"
        else:
            item_type = "other"

        # Clean title: remove type prefix (e.g. "Assignment, CourseName: Title" -> "Title")
        clean_title = title
        if ": " in title:
            clean_title = title.split(": ", 1)[1]

        # Extract course name from prefix (e.g. "Assignment, CourseName: Title")
        course_name = ""
        if ", " in title and ": " in title:
            prefix = title.split(": ", 1)[0]
            if ", " in prefix:
                course_name = prefix.split(", ", 1)[1]

        posted_at = None
        if updated:
            try:
                posted_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            except ValueError:
                pass

        items.append({
            "id": entry_id,
            "type": item_type,
            "title": clean_title,
            "course": course_name,
            "content": full_text,
            "author": author,
            "link": link,
            "posted_at": posted_at,
        })

    return items


def fetch_announcements_from_atom(feeds: list[dict], max_items: int = 20) -> list[dict]:
    """Fetch announcements from the Canvas user Atom feed."""
    items = _fetch_user_atom_feed(feeds)
    return [i for i in items if i["type"] == "announcement"][:max_items]


def fetch_discussions_from_atom(feeds: list[dict], max_items: int = 20) -> list[dict]:
    """Fetch discussions from the Canvas user Atom feed."""
    items = _fetch_user_atom_feed(feeds)
    return [i for i in items if i["type"] == "discussion"][:max_items]


def fetch_wiki_pages_from_atom(feeds: list[dict], max_items: int = 20) -> list[dict]:
    """Fetch wiki page updates from the Canvas user Atom feed."""
    items = _fetch_user_atom_feed(feeds)
    return [i for i in items if i["type"] == "wiki"][:max_items]


def fetch_all_from_atom(feeds: list[dict]) -> dict[str, list[dict]]:
    """Fetch all items from the user Atom feed, grouped by type."""
    items = _fetch_user_atom_feed(feeds)
    grouped = {"announcement": [], "discussion": [], "wiki": [], "assignment": [], "calendar": []}
    for item in items:
        if item["type"] in grouped:
            grouped[item["type"]].append(item)
    return grouped


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
