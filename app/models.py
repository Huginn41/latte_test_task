from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator


class MeetingCreate(BaseModel):
    organizer: str
    with_whom: list[str]
    comment: str | None = None
    start: datetime
    end: datetime

    @field_validator("organizer")
    @classmethod
    def organizer_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("organizer must not be empty")
        return v

    @field_validator("with_whom")
    @classmethod
    def with_whom_not_empty(cls, v: list[str]) -> list[str]:
        v = [p.strip() for p in v if p.strip()]
        if not v:
            raise ValueError("with_whom must contain at least one person")
        return v

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            return v if v else None
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "MeetingCreate":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self

    @property
    def all_participants(self) -> list[str]:
        return [self.organizer] + self.with_whom


class MeetingOut(BaseModel):
    id: int
    organizer: str
    with_whom: list[str]
    comment: str | None
    start: datetime
    end: datetime
    created_at: datetime

    @property
    def start_minutes(self) -> int:
        """Minutes from midnight — used by template to position card on timeline."""
        return self.start.hour * 60 + self.start.minute

    @property
    def duration_minutes(self) -> int:
        delta = self.end - self.start
        return int(delta.total_seconds() // 60)


class MeetingUpdate(MeetingCreate):
    """Same validation as create; used for full replacement (PUT)."""
    pass


class ConflictDetail(BaseModel):
    participant: str
    conflicting_meeting_id: int
    conflicting_organizer: str
    conflicting_start: datetime
    conflicting_end: datetime
