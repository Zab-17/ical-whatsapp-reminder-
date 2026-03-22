from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

_db_path = Path(settings.database_path)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                cookies TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT NOT NULL,
                snapshot TEXT DEFAULT '{}',
                reminder_hours TEXT DEFAULT '8,20',
                active INTEGER DEFAULT 1
            )
        """)
    # Migrate existing users from old 4x/day schedule to new 2x/day default
    with _conn() as conn:
        conn.execute("UPDATE users SET reminder_hours = '8,20' WHERE reminder_hours = '8,11,15,19'")
    # Add ical_url column if missing (migration for existing databases)
    with _conn() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN ical_url TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
    # Add dismissed_items column if missing
    with _conn() as conn:
        try:
            conn.execute("ALTER TABLE users ADD COLUMN dismissed_items TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # column already exists
    logger.info("Database initialized at %s", _db_path)


def add_user(phone: str, cookies: list[dict], name: str = "") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (phone, name, cookies, created_at, last_login) VALUES (?, ?, ?, ?, ?)",
            (phone, name, json.dumps(cookies), now, now),
        )
    logger.info("User %s registered", phone)


def get_user(phone: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if row:
        return dict(row)
    return None


def get_all_users() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    return [dict(r) for r in rows]


def get_user_cookies(phone: str) -> list[dict] | None:
    user = get_user(phone)
    if not user:
        return None
    return json.loads(user["cookies"])


def update_cookies(phone: str, cookies: list[dict]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET cookies = ?, last_login = ? WHERE phone = ?",
            (json.dumps(cookies), now, phone),
        )


def get_user_snapshot(phone: str) -> dict:
    user = get_user(phone)
    if not user:
        return {}
    return json.loads(user.get("snapshot") or "{}")


def save_user_snapshot(phone: str, snapshot_data: dict) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET snapshot = ? WHERE phone = ?",
            (json.dumps(snapshot_data), phone),
        )


def delete_user(phone: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM users WHERE phone = ?", (phone,))
    logger.info("User %s deleted", phone)


def deactivate_user(phone: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET active = 0 WHERE phone = ?", (phone,))
    logger.info("User %s unsubscribed", phone)


def reactivate_user(phone: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET active = 1 WHERE phone = ?", (phone,))
    logger.info("User %s resubscribed", phone)


def get_active_users() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM users WHERE active = 1").fetchall()
    return [dict(r) for r in rows]


def get_user_reminder_hours(phone: str) -> list[int]:
    user = get_user(phone)
    if not user:
        return [8, 20]
    return [int(h) for h in (user.get("reminder_hours") or "8,20").split(",")]


def get_user_ical_url(phone: str) -> str:
    user = get_user(phone)
    if not user:
        return ""
    return user.get("ical_url") or ""


def set_user_ical_url(phone: str, url: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET ical_url = ? WHERE phone = ?", (url, phone))
    logger.info("iCal URL set for %s", phone)


def get_dismissed_items(phone: str) -> set[str]:
    """Get set of dismissed assignment name hashes."""
    user = get_user(phone)
    if not user:
        return set()
    return set(json.loads(user.get("dismissed_items") or "[]"))


def add_dismissed_item(phone: str, item_key: str) -> None:
    items = get_dismissed_items(phone)
    items.add(item_key)
    with _conn() as conn:
        conn.execute("UPDATE users SET dismissed_items = ? WHERE phone = ?", (json.dumps(list(items)), phone))


def remove_dismissed_item(phone: str, item_key: str) -> None:
    items = get_dismissed_items(phone)
    items.discard(item_key)
    with _conn() as conn:
        conn.execute("UPDATE users SET dismissed_items = ? WHERE phone = ?", (json.dumps(list(items)), phone))


def clear_dismissed_items(phone: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET dismissed_items = '[]' WHERE phone = ?", (phone,))


def set_user_reminder_hours(phone: str, hours: list[int]) -> None:
    hours_str = ",".join(str(h) for h in sorted(hours))
    with _conn() as conn:
        conn.execute("UPDATE users SET reminder_hours = ? WHERE phone = ?", (hours_str, phone))


# Initialize on import
init_db()
