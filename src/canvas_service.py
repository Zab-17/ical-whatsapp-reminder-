from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from src.config import settings
from src.database import get_user_cookies
from src.models import (
    AnnouncementInfo,
    AssignmentInfo,
    CourseInfo,
    ModuleInfo,
    QuizInfo,
)

logger = logging.getLogger(__name__)

# Cache clients per user to avoid recreating on every call
_clients: dict[str, httpx.Client] = {}


def _get_client(phone: str) -> httpx.Client:
    if phone in _clients:
        return _clients[phone]

    cookies_list = get_user_cookies(phone)
    if not cookies_list:
        raise ValueError(f"No cookies found for user {phone}")

    cookie_dict = {c["name"]: c["value"] for c in cookies_list}
    client = httpx.Client(
        base_url=settings.canvas_api_url,
        cookies=cookie_dict,
        timeout=30.0,
    )
    _clients[phone] = client
    return client


def invalidate_client(phone: str) -> None:
    _clients.pop(phone, None)


def check_cookies_valid(phone: str) -> bool:
    """Quick check if user's Canvas cookies still work."""
    try:
        client = _get_client(phone)
        resp = client.get("/api/v1/users/self")
        return resp.status_code == 200
    except Exception:
        return False


def _api_get(phone: str, path: str, params: dict | None = None) -> list | dict:
    client = _get_client(phone)
    results = []
    url = path
    while url:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            results.extend(data)
        else:
            return data
        links = _parse_link_header(resp.headers.get("link", ""))
        url = links.get("next")
        params = None
    return results


def _parse_link_header(header: str) -> dict[str, str]:
    links = {}
    for part in header.split(","):
        match = part.strip()
        if 'rel="next"' in match:
            url = match.split(";")[0].strip().strip("<>")
            if url.startswith("http"):
                parsed = urlparse(url)
                url = parsed.path + ("?" + parsed.query if parsed.query else "")
            links["next"] = url
    return links


def get_active_courses(phone: str) -> list[CourseInfo]:
    courses = _api_get(phone, "/api/v1/courses", {"enrollment_state": "active", "include[]": "term"})
    return [
        CourseInfo(id=c["id"], name=c.get("name", "Unknown"), code=c.get("course_code", ""))
        for c in courses
    ]


def get_assignments(phone: str, course_id: int, upcoming_only: bool = False) -> list[AssignmentInfo]:
    now = datetime.now(timezone.utc)
    course_data = _api_get(phone, f"/api/v1/courses/{course_id}")
    course_name = course_data.get("name", "Unknown")
    assignments = _api_get(phone, f"/api/v1/courses/{course_id}/assignments", {"order_by": "due_at"})
    result = []
    for a in assignments:
        due_at = _parse_date(a.get("due_at"))
        if upcoming_only and (due_at is None or due_at < now):
            continue
        result.append(AssignmentInfo(
            id=a["id"], name=a["name"], due_at=due_at,
            course_name=course_name, course_id=course_id,
            points=a.get("points_possible"),
            submitted=a.get("has_submitted_submissions", False),
        ))
    return result


def get_quizzes(phone: str, course_id: int) -> list[QuizInfo]:
    course_data = _api_get(phone, f"/api/v1/courses/{course_id}")
    course_name = course_data.get("name", "Unknown")
    quizzes = _api_get(phone, f"/api/v1/courses/{course_id}/quizzes")
    return [
        QuizInfo(
            id=q["id"], title=q.get("title", "Untitled Quiz"),
            due_at=_parse_date(q.get("due_at")),
            course_name=course_name, course_id=course_id,
            time_limit=q.get("time_limit"),
        )
        for q in quizzes
    ]


def get_upcoming_items(phone: str, days: int | None = None) -> list[AssignmentInfo]:
    if days is None:
        days = settings.upcoming_days
    courses = get_active_courses(phone)
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)
    upcoming = []
    for course in courses:
        try:
            for a in get_assignments(phone, course.id):
                if a.due_at and now <= a.due_at <= cutoff:
                    upcoming.append(a)
        except Exception:
            logger.warning("Failed to fetch assignments for %s", course.name)
    upcoming.sort(key=lambda a: a.due_at or datetime.max.replace(tzinfo=timezone.utc))
    return upcoming


def get_modules(phone: str, course_id: int) -> list[ModuleInfo]:
    modules = _api_get(phone, f"/api/v1/courses/{course_id}/modules")
    return [
        ModuleInfo(id=m["id"], name=m["name"], course_id=course_id, items_count=m.get("items_count", 0))
        for m in modules
    ]


def get_announcements(phone: str, course_id: int, recent: int = 5) -> list[AnnouncementInfo]:
    course_data = _api_get(phone, f"/api/v1/courses/{course_id}")
    course_name = course_data.get("name", "Unknown")
    announcements = _api_get(phone, "/api/v1/announcements", {"context_codes[]": f"course_{course_id}", "per_page": str(recent)})
    result = []
    for a in announcements[:recent]:
        msg = a.get("message", "")
        preview = msg[:150].replace("<p>", "").replace("</p>", "") + ("..." if len(msg) > 150 else "")
        result.append(AnnouncementInfo(
            id=a["id"], title=a["title"],
            posted_at=_parse_date(a.get("posted_at")),
            course_name=course_name, message_preview=preview,
        ))
    return result


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
