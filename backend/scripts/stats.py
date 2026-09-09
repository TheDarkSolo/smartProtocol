#!/usr/bin/env python3
"""Печатает статистику использования Smart Protocol.

Не веб-эндпоинт и не для показа кому-либо кроме владельца — эти цифры не
выставлены наружу намеренно (см. app/db.py). Запускать локально:

    python backend/scripts/stats.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import DB_PATH  # noqa: E402


def main() -> None:
    if not DB_PATH.exists():
        print("События ещё не записаны — база появится после первого обращения к API.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    def count(event_type: str) -> int:
        cur.execute(
            "SELECT COUNT(DISTINCT case_id) FROM events WHERE event_type = ?",
            (event_type,),
        )
        return cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT user_id) FROM events WHERE user_id IS NOT NULL")
    unique_bot_users = cur.fetchone()[0]

    total_cases = count("case_created")
    rejected = count("protocol_rejected")
    extracted = count("extracted")
    drafts = count("draft_created")

    print("Smart Protocol — статистика")
    print("=" * 40)
    print(f"Уникальных пользователей бота:      {unique_bot_users}")
    print(f"Создано дел (загружен файл):        {total_cases}")
    print(f"  из них отклонено (не протокол):   {rejected}")
    print(f"  из них успешно разобрано:         {extracted}")
    print(f"Сгенерировано черновиков жалоб:      {drafts}")

    if total_cases:
        conv = drafts / total_cases * 100
        print(f"\nКонверсия загрузка → черновик: {conv:.0f}%")

    print("\nПо источникам и типам событий:")
    cur.execute(
        "SELECT source, event_type, COUNT(*) FROM events GROUP BY source, event_type ORDER BY source, event_type"
    )
    for source, event_type, cnt in cur.fetchall():
        print(f"  {source:6s} {event_type:20s} {cnt}")

    cur.execute("SELECT MIN(created_at), MAX(created_at) FROM events")
    first, last = cur.fetchone()
    if first:
        print(f"\nПериод: {first} — {last}")

    cur.execute("SELECT COUNT(*), AVG(rating) FROM reviews")
    review_count, avg_rating = cur.fetchone()
    print("\nОтзывы:")
    if review_count:
        print(f"  Всего: {review_count}, средняя оценка: {avg_rating:.1f}")
        cur.execute(
            "SELECT rating, comment, created_at FROM reviews ORDER BY created_at DESC LIMIT 10"
        )
        for rating, comment, created_at in cur.fetchall():
            comment_part = f' — "{comment}"' if comment else ""
            print(f"  [{created_at}] {rating}/5{comment_part}")
    else:
        print("  Пока нет.")

    cur.execute("SELECT COUNT(*) FROM missed_grounds")
    (missed_count,) = cur.fetchone()
    print("\nНе нашли основания (рассказ пользователя своими словами):")
    if missed_count:
        print(f"  Всего: {missed_count} — сырьё для kz-legal-researcher, какие основания добавлять следующими")
        cur.execute(
            "SELECT article_code, offense_description, note, created_at "
            "FROM missed_grounds ORDER BY created_at DESC LIMIT 15"
        )
        for article_code, offense_description, note, created_at in cur.fetchall():
            print(f"  [{created_at}] {article_code or '—'} ({offense_description or '—'})")
            print(f"    \"{note}\"")
    else:
        print("  Пока нет.")


if __name__ == "__main__":
    main()
