"""
ⒸAngelaMos | 2026
scheduler/scheduler.py
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Callable
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.base import BaseTrigger

from codeworm.core import get_logger

if TYPE_CHECKING:
    from codeworm.core.config import ScheduleSettings

logger = get_logger("scheduler")


HOUR_WEIGHTS: dict[int, float] = {
    0: 0.02,
    1: 0.01,
    2: 0.005,
    3: 0.0,
    4: 0.0,
    5: 0.0,
    6: 0.01,
    7: 0.03,
    8: 0.08,
    9: 0.12,
    10: 0.15,
    11: 0.14,
    12: 0.08,
    13: 0.10,
    14: 0.14,
    15: 0.15,
    16: 0.14,
    17: 0.10,
    18: 0.06,
    19: 0.05,
    20: 0.10,
    21: 0.12,
    22: 0.10,
    23: 0.05,
}


@dataclass
class ScheduledTask:
    """
    A task scheduled for execution
    """

    scheduled_time: datetime
    task_id: str
    task_type: str
    executed: bool = False
    executed_at: datetime | None = None
    result: str | None = None


@dataclass
class DailySchedule:
    """
    Schedule of tasks for a single day
    """

    date: datetime
    tasks: list[ScheduledTask] = field(default_factory=list)
    target_commits: int = 0

    @property
    def pending_count(self) -> int:
        return sum(1 for t in self.tasks if not t.executed)

    @property
    def completed_count(self) -> int:
        return sum(1 for t in self.tasks if t.executed)


class HumanLikeTrigger(BaseTrigger):
    """
    APScheduler trigger that generates human-like scheduling patterns
    """

    def __init__(
        self,
        min_commits: int = 12,
        max_commits: int = 18,
        min_gap_minutes: int = 30,
        prefer_hours: list[int] | None = None,
        avoid_hours: list[int] | None = None,
        weekend_reduction: float = 0.7,
        timezone: str = "UTC",
    ) -> None:
        """
        Initialize the human-like trigger
        """
        self.min_commits = min_commits
        self.max_commits = max_commits
        self.min_gap_minutes = min_gap_minutes
        self.prefer_hours = prefer_hours or list(range(9, 18))
        self.avoid_hours = avoid_hours or [3, 4, 5, 6]
        self.weekend_reduction = weekend_reduction
        self.timezone = ZoneInfo(timezone)
        self._last_run: datetime | None = None
        self._daily_times: list[datetime] = []
        self._current_day: datetime | None = None

    def get_next_fire_time(self, previous_fire_time: datetime | None, now: datetime) -> datetime | None:
        """
        Calculate the next fire time
        """
        now_local = now.astimezone(self.timezone)
        today = now_local.date()

        if self._current_day != today or not self._daily_times:
            self._generate_daily_schedule(now_local)
            self._current_day = today

        for scheduled_time in self._daily_times:
            if scheduled_time > now_local:
                return scheduled_time.astimezone(ZoneInfo("UTC"))

        tomorrow = now_local + timedelta(days=1)
        tomorrow_start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        self._generate_daily_schedule(tomorrow_start)
        self._current_day = tomorrow.date()

        if self._daily_times:
            return self._daily_times[0].astimezone(ZoneInfo("UTC"))

        return None

    def _generate_daily_schedule(self, day: datetime) -> None:
        """
        Generate commit times for a day
        """
        is_weekend = day.weekday() >= 5
        commit_count = random.randint(self.min_commits, self.max_commits)

        if is_weekend:
            commit_count = int(commit_count * self.weekend_reduction)
            commit_count = max(commit_count, 3)

        self._daily_times = self._generate_times(day, commit_count)

        logger.debug(
            "daily_schedule_generated",
            date=day.date().isoformat(),
            commit_count=len(self._daily_times),
            is_weekend=is_weekend,
        )

    def _generate_times(self, day: datetime, count: int) -> list[datetime]:
        """
        Generate random times weighted by hour preferences
        """
        times: list[datetime] = []
        weights = self._build_hour_weights()
        hours = list(range(24))

        attempts = 0
        max_attempts = count * 10

        while len(times) < count and attempts < max_attempts:
            attempts += 1

            hour = random.choices(hours, weights=weights, k=1)[0]
            minute = random.randint(0, 59)
            second = random.randint(0, 59)

            candidate = day.replace(hour=hour, minute=minute, second=second, microsecond=0)

            if self._is_valid_time(candidate, times):
                times.append(candidate)

        times.sort()
        return times

    def _build_hour_weights(self) -> list[float]:
        """
        Build hour weights incorporating preferences and avoidances
        """
        weights = [HOUR_WEIGHTS.get(h, 0.05) for h in range(24)]

        for h in self.prefer_hours:
            if 0 <= h < 24:
                weights[h] *= 1.5

        for h in self.avoid_hours:
            if 0 <= h < 24:
                weights[h] = 0.0

        return weights

    def _is_valid_time(self, candidate: datetime, existing: list[datetime]) -> bool:
        """
        Check if candidate time is valid given existing scheduled times
        """
        min_gap = timedelta(minutes=self.min_gap_minutes)

        for existing_time in existing:
            if abs(candidate - existing_time) < min_gap:
                return False

        return True


class CodeWormScheduler:
    """
    Manages scheduling of documentation tasks
    """

    def __init__(self, settings: ScheduleSettings) -> None:
        """
        Initialize scheduler with settings
        """
        self.settings = settings
        self.timezone = ZoneInfo(settings.timezone)
        self._scheduler = BackgroundScheduler(timezone=self.timezone)
        self._task_callback: Callable[[], None] | None = None
        self._daily_schedule: DailySchedule | None = None

    def set_task_callback(self, callback: Callable[[], None]) -> None:
        """
        Set the callback function for scheduled tasks
        """
        self._task_callback = callback

    def start(self) -> None:
        """
        Start the scheduler
        """
        if not self.settings.enabled:
            logger.info("scheduler_disabled")
            return

        trigger = HumanLikeTrigger(
            min_commits=self.settings.min_commits_per_day,
            max_commits=self.settings.max_commits_per_day,
            min_gap_minutes=self.settings.min_gap_minutes,
            prefer_hours=self.settings.prefer_hours,
            avoid_hours=self.settings.avoid_hours,
            weekend_reduction=self.settings.weekend_reduction,
            timezone=self.settings.timezone,
        )

        self._scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            id="documentation_task",
            replace_existing=True,
            misfire_grace_time=3600,
            coalesce=True,
        )

        self._scheduler.start()
        logger.info(
            "scheduler_started",
            min_commits=self.settings.min_commits_per_day,
            max_commits=self.settings.max_commits_per_day,
            timezone=self.settings.timezone,
        )

    def stop(self, wait: bool = True) -> None:
        """
        Stop the scheduler
        """
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("scheduler_stopped")

    def _execute_task(self) -> None:
        """
        Execute a scheduled documentation task
        """
        if self._task_callback:
            try:
                logger.info("executing_scheduled_task")
                self._task_callback()
            except Exception as e:
                logger.exception("scheduled_task_failed", error=str(e))
        else:
            logger.warning("no_task_callback_set")

    def get_next_run_time(self) -> datetime | None:
        """
        Get the next scheduled run time
        """
        job = self._scheduler.get_job("documentation_task")
        if job:
            return job.next_run_time
        return None

    def get_schedule_preview(self, days: int = 1) -> list[dict]:
        """
        Preview upcoming scheduled times
        """
        trigger = HumanLikeTrigger(
            min_commits=self.settings.min_commits_per_day,
            max_commits=self.settings.max_commits_per_day,
            min_gap_minutes=self.settings.min_gap_minutes,
            prefer_hours=self.settings.prefer_hours,
            avoid_hours=self.settings.avoid_hours,
            weekend_reduction=self.settings.weekend_reduction,
            timezone=self.settings.timezone,
        )

        preview: list[dict] = []
        now = datetime.now(self.timezone)

        for day_offset in range(days):
            day = now + timedelta(days=day_offset)
            trigger._generate_daily_schedule(day)

            for scheduled_time in trigger._daily_times:
                preview.append({
                    "time": scheduled_time.isoformat(),
                    "hour": scheduled_time.hour,
                    "is_weekend": scheduled_time.weekday() >= 5,
                })

        return preview


def create_scheduler(settings: ScheduleSettings) -> CodeWormScheduler:
    """
    Create and configure a scheduler instance
    """
    return CodeWormScheduler(settings)
