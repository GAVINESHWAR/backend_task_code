"""Pydantic request/response schemas (one module to stay reviewable)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

# ---------- shared ----------
Category = Literal["Professional", "Learning", "Personal", "Social", "Health", "Finance", "Admin", "Rest", "Other"]
TaskStatus = Literal["Inbox", "Planned", "In Progress", "Paused", "Waiting", "Completed", "Cancelled", "Deferred"]
Priority = Literal["Urgent", "High", "Medium", "Low"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    priority: Priority = "Medium"
    category: Category = "Personal"
    project_id: UUID | None = None
    goal_id: UUID | None = None
    parent_task_id: UUID | None = None
    due_date: date | None = None
    start_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    energy_level: str | None = None
    context: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    category: Category | None = None
    project_id: UUID | None = None
    goal_id: UUID | None = None
    due_date: date | None = None
    start_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=1440)
    energy_level: str | None = None
    context: str | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)


class TaskOut(BaseModel):
    id: UUID
    title: str
    status: str
    priority: str
    category: str
    project_id: UUID | None
    due_date: date | None
    estimated_minutes: int | None
    actual_minutes: int
    postponed_count: int
    created_at: datetime
    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: Category = "Professional"
    status: Literal["Planning", "Active", "Paused", "Completed", "Archived"] = "Active"
    priority: Priority = "Medium"
    start_date: date | None = None
    target_date: date | None = None


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: str = "Planned"
    due_date: date | None = None
    sort_order: int = 0


class FocusStart(BaseModel):
    task_id: UUID
    planned_minutes: int = Field(default=25, ge=1, le=480)


class FocusNote(BaseModel):
    notes: str | None = None


class WorkStateUpsert(BaseModel):
    last_action: str | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_step: str | None = None
    next_action: str | None = None
    notes: str | None = None
    blocker: str | None = None


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    start_time: datetime
    end_time: datetime
    category: Category = "Personal"
    location: str | None = None
    recurrence: str | None = None
    reminder_minutes: int | None = None


class TimeBlockCreate(BaseModel):
    label: str
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: str  # HH:MM
    end_time: str


class DailyPlanUpsert(BaseModel):
    plan_date: date
    top_priorities: list[UUID] = Field(default_factory=list, max_length=3)
    secondary_tasks: list[UUID] = Field(default_factory=list)
    notes: str | None = None


class DailyReviewUpsert(BaseModel):
    review_date: date
    completed_summary: str | None = None
    unfinished_summary: str | None = None
    focus_rating: int | None = Field(default=None, ge=1, le=5)
    energy_rating: int | None = Field(default=None, ge=1, le=5)
    distraction_notes: str | None = None
    tomorrow_notes: str | None = None


class LearningPathCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "Active"


class LearningTopicCreate(BaseModel):
    path_id: UUID
    title: str
    description: str | None = None
    estimated_minutes: int | None = None
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"
    prerequisites: str | None = None
    resources: list = Field(default_factory=list)


class HabitCreate(BaseModel):
    title: str
    description: str | None = None
    frequency: Literal["Daily", "Weekly", "Custom"] = "Daily"
    target_per_week: int = 7
    custom_days: list = Field(default_factory=list)


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "Active"
    target_date: date | None = None


class NoteCreate(BaseModel):
    title: str
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    task_id: UUID | None = None
    project_id: UUID | None = None
    learning_topic_id: UUID | None = None
    goal_id: UUID | None = None
    event_id: UUID | None = None


class InboxCreate(BaseModel):
    title: str
    description: str | None = None


class InboxConvert(BaseModel):
    target: Literal["task", "event", "learning_topic", "note", "reminder"]
    priority: Priority = "Medium"
    category: Category = "Personal"


class DistractionCreate(BaseModel):
    duration_minutes: int = Field(default=5, ge=1, le=480)
    category: Literal["Social Media", "Short Videos", "YouTube", "Messaging", "Browsing", "Unplanned Work", "Music", "Other"] = "Other"
    task_id: UUID | None = None
    notes: str | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RecommendationOut(BaseModel):
    task_id: UUID | None
    reason: str
    estimated_minutes: int | None = None
    score: float = 0
