"""
ⒸAngelaMos | 2026
dashboard/backend/models.py
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_documented: int = 0
    by_repo: dict[str, int] = {}
    by_language: dict[str, int] = {}
    by_doc_type: dict[str, int] = {}
    last_7_days: int = 0
    last_30_days: int = 0
    today: int = 0


class RepoStatus(BaseModel):
    name: str
    path: str
    weight: int
    enabled: bool
    docs_generated: int = 0
    last_activity: datetime | None = None


class RecentDoc(BaseModel):
    id: str
    source_repo: str
    source_file: str
    function_name: str | None
    class_name: str | None
    doc_type: str
    documented_at: datetime
    snippet_path: str
    git_commit: str | None


class ActivityDay(BaseModel):
    date: str
    count: int


class LanguageBreakdown(BaseModel):
    language: str
    count: int
    percentage: float


class DaemonStatus(BaseModel):
    running: bool = False
    current_activity: str = "idle"
    current_target: str | None = None
    current_repo: str | None = None
    current_doc_type: str | None = None
