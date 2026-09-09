"""Лёгкий журнал событий на SQLite — для статистики использования.

Не публичный API: цифры читаются локально через backend/scripts/stats.py,
владельцем, а не выставляются наружу — это данные о бизнесе, а не то, что
можно случайно раздать любому, кто найдёт URL. Если понадобится дашборд для
кого-то ещё — потребуется отдельная авторизация, не добавлять эндпоинт молча.

SQLite, а не Postgres: на объёме одного процесса и тестовой стадии продукта
это полностью достаточно. Переезжать стоит, когда появится реальная
параллельная нагрузка, а не заранее.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "storage" / "stats.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            case_id TEXT,
            user_id TEXT,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT,
            user_id TEXT,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    return conn


def log_event(event_type: str, *, case_id: str | None = None, user_id: str | None = None) -> None:
    """user_id — идентификатор пользователя Telegram, если событие пришло из
    бота (см. X-User-Id в bot/app/api_client.py). У веба своей identity пока
    нет (дело живёт в анонимной сессии, см. ROADMAP.md) — для веб-событий
    user_id всегда None, и это осознанно, а не недоработка."""
    source = "bot" if user_id else "web"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events (event_type, case_id, user_id, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_type, case_id, user_id, source, datetime.now(timezone.utc).isoformat()),
        )


def save_review(*, rating: int, case_id: str | None = None, user_id: str | None = None, comment: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO reviews (case_id, user_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (case_id, user_id, rating, comment, datetime.now(timezone.utc).isoformat()),
        )
