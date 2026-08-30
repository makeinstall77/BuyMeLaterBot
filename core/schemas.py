from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.models import ItemStatus, ListType, ScopeType


class ScopeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_type: ScopeType
    telegram_chat_id: int
    title: str
    timezone: str
    created_at: datetime
    updated_at: datetime


class ListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scope_id: UUID
    list_type: ListType
    name: str
    created_at: datetime
    updated_at: datetime


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    list_id: UUID
    title: str
    description: str | None
    status: ItemStatus
    created_by_id: UUID | None
    due_at: datetime | None
    is_recurring: bool
    rrule: str | None
    notifications_enabled: bool
    last_notified_at: datetime | None
    next_notify_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    due_at: datetime | None = None
    is_recurring: bool = False
    rrule: str | None = None
    notifications_enabled: bool = False
    created_by_id: UUID | None = None


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: ItemStatus | None = None
    due_at: datetime | None = None
    is_recurring: bool | None = None
    rrule: str | None = None
    notifications_enabled: bool | None = None
    next_notify_at: datetime | None = None
    completed_at: datetime | None = None


class RecurrencePreset(str, Enum):
    daily = "daily"
    weekdays = "weekdays"
    weekly = "weekly"
    monthly = "monthly"


RRULE_BY_PRESET: dict[RecurrencePreset, str] = {
    RecurrencePreset.daily: "FREQ=DAILY",
    RecurrencePreset.weekdays: "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
    RecurrencePreset.weekly: "FREQ=WEEKLY",
    RecurrencePreset.monthly: "FREQ=MONTHLY",
}


class ParsedReminder(BaseModel):
    list_type: ListType
    title: str
    due_at: datetime | None = None
    notifications_enabled: bool = False
    is_recurring: bool = False
    recurrence: RecurrencePreset | None = None
    raw_text: str = ""
