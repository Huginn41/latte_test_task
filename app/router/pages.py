from datetime import date, timedelta, datetime
from dataclasses import dataclass

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_connection, get_user, verify_password, short_name, full_name

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

COOKIE_NAME = "username"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


@dataclass
class CurrentUser:
    username: str
    short: str   # Фамилия Имя
    full: str    # Фамилия Имя Отчество


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _resolve_user(username: str | None) -> CurrentUser | None:
    if not username:
        return None
    conn = get_connection()
    try:
        row = get_user(conn, username)
        if not row:
            return None
        return CurrentUser(
            username=row["username"],
            short=short_name(row),
            full=full_name(row),
        )
    finally:
        conn.close()


def _current_user(username: str | None = Cookie(default=None)) -> CurrentUser | None:
    return _resolve_user(username)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


# ── Login / Logout ─────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, username: str | None = Cookie(default=None)):
    if _resolve_user(username):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    username = username.strip()
    conn = get_connection()
    try:
        user = get_user(conn, username)
    finally:
        conn.close()

    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверный логин или пароль"},
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=username,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Main page ──────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    week: str | None = None,
    conn=Depends(get_db),
    user: CurrentUser | None = Depends(_current_user),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app import repository
    today = date.today()

    if week:
        try:
            year, week_num = week.split("-W")
            ws = datetime.strptime(f"{year}-W{week_num}-1", "%Y-W%W-%w").date()
        except (ValueError, AttributeError):
            ws = _week_start(today)
    else:
        ws = _week_start(today)

    grouped = repository.get_week_timeline(conn, ws)
    week_days = [ws + timedelta(days=i) for i in range(7)]
    today_meetings = repository.get_today_meetings_for_user(conn, today, user.short)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": user.full,
            "current_user_short": user.short,
            "today": today,
            "week_start": ws,
            "week_days": week_days,
            "grouped": {d.isoformat(): m for d, m in grouped.items()},
            "hours": list(range(24)),
            "prev_week": (ws - timedelta(weeks=1)).strftime("%Y-W%W"),
            "next_week": (ws + timedelta(weeks=1)).strftime("%Y-W%W"),
            "today_meetings": today_meetings,
        },
    )


# ── Meeting detail page ────────────────────────────────────────

@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(
    meeting_id: int,
    request: Request,
    conn=Depends(get_db),
    user: CurrentUser | None = Depends(_current_user),
):
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    from app import repository
    meeting = repository.get_meeting_by_id(conn, meeting_id)
    if not meeting:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "current_user": user.full, "current_user_short": user.short},
            status_code=404,
        )
    return templates.TemplateResponse(
        "meetings/detail.html",
        {
            "request": request,
            "meeting": meeting,
            "current_user": user.full,
            "current_user_short": user.short,
        },
    )
