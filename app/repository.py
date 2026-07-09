from datetime import datetime, date, timedelta

from app.models import MeetingCreate, MeetingOut, ConflictDetail


def _row_to_meeting(row, with_whom: list[str]) -> MeetingOut:
    return MeetingOut(
        id=row["id"],
        organizer=row["organizer"],
        with_whom=with_whom,
        comment=row["comment"],
        start=datetime.fromisoformat(row["start_time"]),
        end=datetime.fromisoformat(row["end_time"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _fetch_with_whom(conn, meeting_id: int, organizer: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM participants WHERE meeting_id = %s AND name != %s ORDER BY name",
            (meeting_id, organizer),
        )
        return [r["name"] for r in cur.fetchall()]


def check_conflicts(conn, data: MeetingCreate, exclude_id: int | None = None) -> list[ConflictDetail]:
    start_iso = data.start.isoformat()
    end_iso = data.end.isoformat()
    conflicts: list[ConflictDetail] = []

    for participant in data.all_participants:
        if exclude_id is not None:
            query = """
                SELECT m.id, m.organizer, m.start_time, m.end_time
                FROM meetings m
                JOIN participants p ON p.meeting_id = m.id
                WHERE p.name = %s
                  AND m.start_time < %s
                  AND m.end_time   > %s
                  AND m.id != %s
                LIMIT 1
            """
            params = (participant, end_iso, start_iso, exclude_id)
        else:
            query = """
                SELECT m.id, m.organizer, m.start_time, m.end_time
                FROM meetings m
                JOIN participants p ON p.meeting_id = m.id
                WHERE p.name = %s
                  AND m.start_time < %s
                  AND m.end_time   > %s
                LIMIT 1
            """
            params = (participant, end_iso, start_iso)

        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()

        if row:
            conflicts.append(
                ConflictDetail(
                    participant=participant,
                    conflicting_meeting_id=row["id"],
                    conflicting_organizer=row["organizer"],
                    conflicting_start=datetime.fromisoformat(row["start_time"]),
                    conflicting_end=datetime.fromisoformat(row["end_time"]),
                )
            )

    return conflicts


def create_meeting(conn, data: MeetingCreate) -> MeetingOut:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO meetings (organizer, comment, start_time, end_time)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (data.organizer, data.comment, data.start.isoformat(), data.end.isoformat()),
        )
        meeting_id = cur.fetchone()["id"]

        cur.executemany(
            "INSERT INTO participants (meeting_id, name) VALUES (%s, %s)",
            [(meeting_id, name) for name in data.all_participants],
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
        row = cur.fetchone()
    return _row_to_meeting(row, list(data.with_whom))


def get_meetings_by_day(conn, day: date) -> list[MeetingOut]:
    start = datetime(day.year, day.month, day.day).isoformat()
    end = datetime(day.year, day.month, day.day, 23, 59, 59).isoformat()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM meetings WHERE start_time >= %s AND start_time <= %s ORDER BY start_time",
            (start, end),
        )
        rows = cur.fetchall()

    return [
        _row_to_meeting(r, _fetch_with_whom(conn, r["id"], r["organizer"]))
        for r in rows
    ]


def get_week_timeline(conn, week_start: date) -> dict[date, list[MeetingOut]]:
    week_end = week_start + timedelta(days=6)
    start = datetime(week_start.year, week_start.month, week_start.day).isoformat()
    end = datetime(week_end.year, week_end.month, week_end.day, 23, 59, 59).isoformat()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM meetings WHERE start_time >= %s AND start_time <= %s ORDER BY start_time",
            (start, end),
        )
        rows = cur.fetchall()

    result: dict[date, list[MeetingOut]] = {
        week_start + timedelta(days=i): [] for i in range(7)
    }
    for r in rows:
        meeting = _row_to_meeting(r, _fetch_with_whom(conn, r["id"], r["organizer"]))
        day_key = meeting.start.date()
        if day_key in result:
            result[day_key].append(meeting)

    return result


def update_meeting(conn, meeting_id: int, data: MeetingCreate) -> MeetingOut:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE meetings SET organizer=%s, comment=%s, start_time=%s, end_time=%s WHERE id=%s",
            (data.organizer, data.comment, data.start.isoformat(), data.end.isoformat(), meeting_id),
        )
        cur.execute("DELETE FROM participants WHERE meeting_id=%s", (meeting_id,))
        cur.executemany(
            "INSERT INTO participants (meeting_id, name) VALUES (%s, %s)",
            [(meeting_id, name) for name in data.all_participants],
        )
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM meetings WHERE id=%s", (meeting_id,))
        row = cur.fetchone()
    return _row_to_meeting(row, _fetch_with_whom(conn, meeting_id, data.organizer))


def delete_meeting(conn, meeting_id: int) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM meetings WHERE id=%s", (meeting_id,))
        deleted = cur.rowcount > 0
    conn.commit()
    return deleted


def get_meeting_by_id(conn, meeting_id: int) -> MeetingOut | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM meetings WHERE id = %s", (meeting_id,))
        row = cur.fetchone()
    if not row:
        return None
    return _row_to_meeting(row, _fetch_with_whom(conn, row["id"], row["organizer"]))


def get_today_meetings_for_user(conn, day: date, user_name: str) -> list[MeetingOut]:
    start = datetime(day.year, day.month, day.day).isoformat()
    end = datetime(day.year, day.month, day.day, 23, 59, 59).isoformat()

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT m.*
            FROM meetings m
            JOIN participants p ON p.meeting_id = m.id
            WHERE p.name = %s
              AND m.start_time >= %s
              AND m.start_time <= %s
            ORDER BY m.start_time
            """,
            (user_name, start, end),
        )
        rows = cur.fetchall()

    return [
        _row_to_meeting(r, _fetch_with_whom(conn, r["id"], r["organizer"]))
        for r in rows
    ]
