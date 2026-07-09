import hashlib
import os
from datetime import date, timedelta

import psycopg2
import psycopg2.extras


def get_connection() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed


def short_name(user) -> str:
    """Фамилия Имя — used as meeting organizer identifier."""
    return f"{user['last_name']} {user['first_name']}"


def full_name(user) -> str:
    """Фамилия Имя Отчество (Отчество optional)."""
    parts = [user['last_name'], user['first_name']]
    if user['patronymic']:
        parts.append(user['patronymic'])
    return ' '.join(parts)


def init_db() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username      TEXT PRIMARY KEY,
                    last_name     TEXT NOT NULL,
                    first_name    TEXT NOT NULL,
                    patronymic    TEXT,
                    password_hash TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id         SERIAL PRIMARY KEY,
                    organizer  TEXT NOT NULL,
                    comment    TEXT,
                    start_time TEXT NOT NULL,
                    end_time   TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS')
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
                    name       TEXT    NOT NULL,
                    PRIMARY KEY (meeting_id, name)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_meetings_start ON meetings(start_time)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_participants_name ON participants(name)
            """)
        conn.commit()
        _seed(conn)
    finally:
        conn.close()


def get_user(conn, username: str):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchone()


def _seed(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE username = 'worker'")
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO users (username, last_name, first_name, patronymic, password_hash)
                   VALUES (%s, %s, %s, %s, %s)""",
                ("worker", "Иванов", "Иван", "Иванович", hash_password("worker123")),
            )
            conn.commit()

        cur.execute("SELECT COUNT(*) FROM meetings")
        row = cur.fetchone()
        if row["count"] > 0:
            return

        monday = date.today() - timedelta(days=date.today().weekday())

        seed_data = [
            (
                "Смирнова Анна",
                "Обсудить план на квартал и распределить задачи по команде",
                0, 10, 0, 11, 0,
                ["Смирнова Анна", "Козлов Дмитрий"],
            ),
            (
                "Смирнова Анна",
                "Ревью дизайн-макетов новой версии продукта",
                2, 14, 30, 15, 30,
                ["Смирнова Анна", "Козлов Дмитрий", "Фролова Мария"],
            ),
            (
                "Козлов Дмитрий",
                "Синхронизация с разработкой по текущему спринту",
                1, 9, 0, 9, 45,
                ["Козлов Дмитрий", "Фролова Мария"],
            ),
        ]

        for organizer, comment, day_offset, sh, sm, eh, em, participants in seed_data:
            day = monday + timedelta(days=day_offset)
            start = f"{day.isoformat()}T{sh:02d}:{sm:02d}:00"
            end   = f"{day.isoformat()}T{eh:02d}:{em:02d}:00"

            cur.execute(
                "INSERT INTO meetings (organizer, comment, start_time, end_time) VALUES (%s, %s, %s, %s) RETURNING id",
                (organizer, comment, start, end),
            )
            meeting_id = cur.fetchone()["id"]
            cur.executemany(
                "INSERT INTO participants (meeting_id, name) VALUES (%s, %s)",
                [(meeting_id, name) for name in participants],
            )

        conn.commit()
