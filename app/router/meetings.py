from datetime import date as date_type, datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException
from fastapi.responses import Response

from app.database import get_connection, get_user, short_name
from app.models import MeetingCreate, MeetingUpdate, MeetingOut, ConflictDetail
from app import repository

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(username: str | None = Cookie(default=None)) -> str | None:
    """Returns short_name (Фамилия Имя) for the logged-in user, or None."""
    if not username:
        return None
    conn = get_connection()
    try:
        row = get_user(conn, username.strip())
        return short_name(row) if row else None
    finally:
        conn.close()


def _conflict_error(conflicts: list[ConflictDetail]) -> HTTPException:
    first = conflicts[0]
    return HTTPException(
        status_code=409,
        detail={
            "message": (
                f"{first.participant} занят(а) — встреча организована "
                f"{first.conflicting_organizer} "
                f"({first.conflicting_start.strftime('%H:%M')}–"
                f"{first.conflicting_end.strftime('%H:%M')})"
            ),
            "conflicts": [c.model_dump(mode="json") for c in conflicts],
        },
    )


@router.post("", response_model=MeetingOut, status_code=201)
def create_meeting(data: MeetingCreate, conn=Depends(get_db)):
    conflicts = repository.check_conflicts(conn, data)
    if conflicts:
        raise _conflict_error(conflicts)
    return repository.create_meeting(conn, data)


@router.get("/week", response_model=dict[str, list[MeetingOut]])
def week_timeline(week: str | None = None, conn=Depends(get_db)):
    if week:
        try:
            year, week_num = week.split("-W")
            week_start = datetime.strptime(f"{year}-W{week_num}-1", "%Y-W%W-%w").date()
        except (ValueError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid week format. Use YYYY-WNN")
    else:
        today = date_type.today()
        week_start = today - timedelta(days=today.weekday())

    grouped = repository.get_week_timeline(conn, week_start)
    return {day.isoformat(): meetings for day, meetings in grouped.items()}


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: int, conn=Depends(get_db)):
    meeting = repository.get_meeting_by_id(conn, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.put("/{meeting_id}", response_model=MeetingOut)
def update_meeting(
    meeting_id: int,
    data: MeetingUpdate,
    conn=Depends(get_db),
    current_user: str | None = Depends(get_current_user),
):
    existing = repository.get_meeting_by_id(conn, meeting_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if current_user and existing.organizer != current_user:
        raise HTTPException(status_code=403, detail="Можно редактировать только свои встречи")

    conflicts = repository.check_conflicts(conn, data, exclude_id=meeting_id)
    if conflicts:
        raise _conflict_error(conflicts)
    return repository.update_meeting(conn, meeting_id, data)


@router.delete("/{meeting_id}", status_code=204)
def delete_meeting(
    meeting_id: int,
    conn=Depends(get_db),
    current_user: str | None = Depends(get_current_user),
):
    existing = repository.get_meeting_by_id(conn, meeting_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if current_user and existing.organizer != current_user:
        raise HTTPException(status_code=403, detail="Можно удалять только свои встречи")
    repository.delete_meeting(conn, meeting_id)
    return Response(status_code=204)


@router.get("", response_model=list[MeetingOut])
def list_meetings(date: str | None = None, conn=Depends(get_db)):
    if date:
        try:
            day = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        return repository.get_meetings_by_day(conn, day)
    return repository.get_meetings_by_day(conn, date_type.today())
