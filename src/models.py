from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CourseInfo:
    id: int
    name: str
    code: str

    def short_name(self) -> str:
        return self.code or self.name[:30]


@dataclass
class AssignmentInfo:
    id: int
    name: str
    due_at: datetime | None
    course_name: str
    course_id: int
    points: float | None = None
    submitted: bool = False

    def due_str(self) -> str:
        if self.due_at is None:
            return "No due date"
        return self.due_at.strftime("%b %d, %I:%M %p")


@dataclass
class QuizInfo:
    id: int
    title: str
    due_at: datetime | None
    course_name: str
    course_id: int
    time_limit: int | None = None

    def due_str(self) -> str:
        if self.due_at is None:
            return "No due date"
        return self.due_at.strftime("%b %d, %I:%M %p")


@dataclass
class ModuleInfo:
    id: int
    name: str
    course_id: int
    items_count: int = 0


@dataclass
class AnnouncementInfo:
    id: int
    title: str
    posted_at: datetime | None
    course_name: str
    message_preview: str = ""

    def posted_str(self) -> str:
        if self.posted_at is None:
            return "Unknown date"
        return self.posted_at.strftime("%b %d, %I:%M %p")


@dataclass
class Snapshot:
    """Tracks known item IDs per course for change detection."""
    assignment_ids: dict[int, list[int]] = field(default_factory=dict)
    quiz_ids: dict[int, list[int]] = field(default_factory=dict)
    announcement_ids: dict[int, list[int]] = field(default_factory=dict)
    module_ids: dict[int, list[int]] = field(default_factory=dict)
