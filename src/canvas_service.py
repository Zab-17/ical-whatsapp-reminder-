from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from canvasapi import Canvas

from src.config import settings
from src.models import (
    AnnouncementInfo,
    AssignmentInfo,
    CourseInfo,
    ModuleInfo,
    QuizInfo,
)

logger = logging.getLogger(__name__)

# Auth mode: either use canvasapi with token, or httpx with cookies
_canvas: Canvas | None = None
_http_client: httpx.Client | None = None
_auth_mode: str = "none"


def _init_client() -> None:
    global _canvas, _http_client, _auth_mode
    from src.auth import get_canvas_token

    token = get_canvas_token()

    if token.startswith("cookies:"):
        # Cookie-based auth — use httpx directly
        cookies_dict = json.loads(token[len("cookies:"):])
        _http_client = httpx.Client(
            base_url=settings.canvas_api_url,
            cookies=cookies_dict,
            timeout=30.0,
        )
        _auth_mode = "cookies"
        logger.info("Using cookie-based authentication")
    else:
        # Token-based auth — use canvasapi
        _canvas = Canvas(settings.canvas_api_url, token)
        _auth_mode = "token"
        logger.info("Using token-based authentication")


def _ensure_client() -> None:
    if _auth_mode == "none":
        _init_client()


def _api_get(path: str, params: dict | None = None) -> list | dict:
    """Make a GET request to the Canvas API (cookie mode)."""
    _ensure_client()
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    results = []
    url = path
    while url:
        resp = _http_client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            results.extend(data)
        else:
            return data
        # Handle pagination
        links = _parse_link_header(resp.headers.get("link", ""))
        url = links.get("next")
        params = None  # params are in the next URL already
    return results


def _parse_link_header(header: str) -> dict[str, str]:
    links = {}
    for part in header.split(","):
        match = part.strip()
        if 'rel="next"' in match:
            url = match.split(";")[0].strip().strip("<>")
            # Convert absolute URL to relative path for httpx
            if url.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                url = parsed.path + ("?" + parsed.query if parsed.query else "")
            links["next"] = url
    return links


def get_active_courses() -> list[CourseInfo]:
    _ensure_client()
    result = []

    if _auth_mode == "token":
        courses = _canvas.get_courses(enrollment_state="active", include=["term"])
        for c in courses:
            try:
                result.append(
                    CourseInfo(
                        id=c.id,
                        name=getattr(c, "name", "Unknown"),
                        code=getattr(c, "course_code", ""),
                    )
                )
            except Exception:
                logger.warning("Skipping course %s", getattr(c, "id", "?"))
    else:
        courses = _api_get("/api/v1/courses", {"enrollment_state": "active", "include[]": "term"})
        for c in courses:
            try:
                result.append(
                    CourseInfo(
                        id=c["id"],
                        name=c.get("name", "Unknown"),
                        code=c.get("course_code", ""),
                    )
                )
            except Exception:
                logger.warning("Skipping course %s", c.get("id", "?"))

    return result


def get_assignments(course_id: int, upcoming_only: bool = False) -> list[AssignmentInfo]:
    _ensure_client()
    now = datetime.now(timezone.utc)
    result = []

    if _auth_mode == "token":
        course = _canvas.get_course(course_id)
        course_name = course.name
        assignments = course.get_assignments(order_by="due_at")
        for a in assignments:
            due_at = _parse_date(getattr(a, "due_at", None))
            if upcoming_only and (due_at is None or due_at < now):
                continue
            result.append(
                AssignmentInfo(
                    id=a.id, name=a.name, due_at=due_at,
                    course_name=course_name, course_id=course_id,
                    points=getattr(a, "points_possible", None),
                    submitted=getattr(a, "has_submitted_submissions", False),
                )
            )
    else:
        course_data = _api_get(f"/api/v1/courses/{course_id}")
        course_name = course_data.get("name", "Unknown")
        assignments = _api_get(f"/api/v1/courses/{course_id}/assignments", {"order_by": "due_at"})
        for a in assignments:
            due_at = _parse_date(a.get("due_at"))
            if upcoming_only and (due_at is None or due_at < now):
                continue
            result.append(
                AssignmentInfo(
                    id=a["id"], name=a["name"], due_at=due_at,
                    course_name=course_name, course_id=course_id,
                    points=a.get("points_possible"),
                    submitted=a.get("has_submitted_submissions", False),
                )
            )

    return result


def get_quizzes(course_id: int) -> list[QuizInfo]:
    _ensure_client()
    result = []

    if _auth_mode == "token":
        course = _canvas.get_course(course_id)
        course_name = course.name
        quizzes = course.get_quizzes()
        for q in quizzes:
            result.append(
                QuizInfo(
                    id=q.id, title=getattr(q, "title", "Untitled Quiz"),
                    due_at=_parse_date(getattr(q, "due_at", None)),
                    course_name=course_name, course_id=course_id,
                    time_limit=getattr(q, "time_limit", None),
                )
            )
    else:
        course_data = _api_get(f"/api/v1/courses/{course_id}")
        course_name = course_data.get("name", "Unknown")
        quizzes = _api_get(f"/api/v1/courses/{course_id}/quizzes")
        for q in quizzes:
            result.append(
                QuizInfo(
                    id=q["id"], title=q.get("title", "Untitled Quiz"),
                    due_at=_parse_date(q.get("due_at")),
                    course_name=course_name, course_id=course_id,
                    time_limit=q.get("time_limit"),
                )
            )

    return result


def get_upcoming_items(days: int | None = None) -> list[AssignmentInfo]:
    if days is None:
        days = settings.upcoming_days
    courses = get_active_courses()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)
    upcoming = []
    for course in courses:
        try:
            assignments = get_assignments(course.id, upcoming_only=False)
            for a in assignments:
                if a.due_at and now <= a.due_at <= cutoff:
                    upcoming.append(a)
        except Exception:
            logger.warning("Failed to fetch assignments for %s", course.name)
    upcoming.sort(key=lambda a: a.due_at or datetime.max.replace(tzinfo=timezone.utc))
    return upcoming


def get_modules(course_id: int) -> list[ModuleInfo]:
    _ensure_client()
    result = []

    if _auth_mode == "token":
        course = _canvas.get_course(course_id)
        modules = course.get_modules()
        for m in modules:
            result.append(
                ModuleInfo(
                    id=m.id, name=m.name, course_id=course_id,
                    items_count=getattr(m, "items_count", 0),
                )
            )
    else:
        modules = _api_get(f"/api/v1/courses/{course_id}/modules")
        for m in modules:
            result.append(
                ModuleInfo(
                    id=m["id"], name=m["name"], course_id=course_id,
                    items_count=m.get("items_count", 0),
                )
            )

    return result


def get_announcements(course_id: int, recent: int = 5) -> list[AnnouncementInfo]:
    _ensure_client()
    result = []

    if _auth_mode == "token":
        course = _canvas.get_course(course_id)
        course_name = course.name
        context_code = f"course_{course_id}"
        announcements = _canvas.get_announcements(context_codes=[context_code])
        count = 0
        for a in announcements:
            if count >= recent:
                break
            msg = getattr(a, "message", "")
            preview = _clean_preview(msg)
            result.append(
                AnnouncementInfo(
                    id=a.id, title=a.title,
                    posted_at=_parse_date(getattr(a, "posted_at", None)),
                    course_name=course_name, message_preview=preview,
                )
            )
            count += 1
    else:
        course_data = _api_get(f"/api/v1/courses/{course_id}")
        course_name = course_data.get("name", "Unknown")
        announcements = _api_get(
            "/api/v1/announcements",
            {"context_codes[]": f"course_{course_id}", "per_page": str(recent)},
        )
        for a in announcements[:recent]:
            msg = a.get("message", "")
            preview = _clean_preview(msg)
            result.append(
                AnnouncementInfo(
                    id=a["id"], title=a["title"],
                    posted_at=_parse_date(a.get("posted_at")),
                    course_name=course_name, message_preview=preview,
                )
            )

    return result


def _clean_preview(msg: str) -> str:
    preview = msg[:150].replace("<p>", "").replace("</p>", "")
    return preview + ("..." if len(msg) > 150 else "")


def get_all_assignment_ids(course_id: int) -> list[int]:
    return [a.id for a in get_assignments(course_id)]


def get_all_quiz_ids(course_id: int) -> list[int]:
    return [q.id for q in get_quizzes(course_id)]


def get_all_announcement_ids(course_id: int) -> list[int]:
    return [a.id for a in get_announcements(course_id, recent=50)]


def get_all_module_ids(course_id: int) -> list[int]:
    return [m.id for m in get_modules(course_id)]


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
