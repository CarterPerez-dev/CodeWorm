"""
ⒸAngelaMos | 2026
analysis/scoring.py
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from typing import TYPE_CHECKING, ClassVar

from codeworm.analysis.complexity import ComplexityMetrics

if TYPE_CHECKING:
    from git import Repo


@dataclass
class GitStats:
    """
    Git derived statistics for a file or function
    """
    commit_count_30d: int = 0
    commit_count_90d: int = 0
    last_modified: datetime | None = None
    unique_authors: int = 0
    is_new: bool = False

    @property
    def days_since_modified(self) -> int:
        """
        Days since last modification
        """
        if not self.last_modified:
            return 999
        delta = datetime.now() - self.last_modified
        return delta.days

    @property
    def is_hot(self) -> bool:
        """
        Check if this is a frequently modified hotspot
        """
        return self.commit_count_30d >= 3

    @property
    def is_recent(self) -> bool:
        """
        Check if modified in last 30 days
        """
        return self.days_since_modified <= 30


@dataclass
class InterestScore:
    """
    Computed interest score with breakdown
    """
    total: float
    complexity_score: float
    length_score: float
    nesting_score: float
    parameter_score: float
    churn_score: float
    novelty_score: float
    pattern_bonus: float = 0.0

    @property
    def rating(self) -> str:
        """
        Human readable interest rating
        """
        if self.total >= 70:
            return "highly_interesting"
        if self.total >= 50:
            return "interesting"
        if self.total >= 30:
            return "moderate"
        return "low"

    def to_dict(self) -> dict:
        """
        Convert to dictionary for logging
        """
        return {
            "total": round(self.total,
                           2),
            "complexity": round(self.complexity_score,
                                2),
            "length": round(self.length_score,
                            2),
            "nesting": round(self.nesting_score,
                             2),
            "parameters": round(self.parameter_score,
                                2),
            "churn": round(self.churn_score,
                           2),
            "novelty": round(self.novelty_score,
                             2),
            "pattern_bonus": round(self.pattern_bonus,
                                   2),
            "rating": self.rating,
        }


class InterestScorer:
    """
    Scores code snippets based on how interesting they are to document
    Uses weighted factors normalized to 0-100 scale
    """
    WEIGHTS: ClassVar[dict[str, float]] = {
        "complexity": 0.35,
        "length": 0.15,
        "nesting": 0.15,
        "parameters": 0.10,
        "churn": 0.15,
        "novelty": 0.10,
    }

    COMPLEXITY_CAP = 20
    LENGTH_CAP = 100
    NESTING_CAP = 5
    PARAM_CAP = 7
    CHURN_CAP = 5
    NOVELTY_DAYS = 30

    PATTERN_BONUSES: ClassVar[dict[str, int]] = {
        "decorator": 5,
        "async": 5,
        "context_manager": 10,
        "generator": 8,
        "class_method": 3,
        "property": 3,
        "abstract": 8,
        "dataclass": 7,
    }

    def __init__(self, git_repo: Repo | None = None) -> None:
        """
        Initialize scorer with optional git repo for stats
        """
        self.git_repo = git_repo

    def score(
        self,
        metrics: ComplexityMetrics,
        git_stats: GitStats | None = None,
        decorators: list[str] | None = None,
        is_async: bool = False,
        source: str = "",
    ) -> InterestScore:
        """
        Calculate interest score for a function
        """
        if git_stats is None:
            git_stats = GitStats()

        complexity_score = min(
            metrics.cyclomatic_complexity / self.COMPLEXITY_CAP,
            1.0
        ) * 100
        length_score = min(metrics.nloc / self.LENGTH_CAP, 1.0) * 100
        nesting_score = min(
            metrics.max_nesting_depth / self.NESTING_CAP,
            1.0
        ) * 100
        param_score = min(metrics.parameter_count / self.PARAM_CAP, 1.0) * 100

        churn_score = min(git_stats.commit_count_30d / self.CHURN_CAP, 1.0) * 100

        days_old = git_stats.days_since_modified
        novelty_score = max(
            0,
            (self.NOVELTY_DAYS - days_old) / self.NOVELTY_DAYS
        ) * 100

        pattern_bonus = self._calculate_pattern_bonus(
            decorators,
            is_async,
            source
        )

        weighted_total = (
            complexity_score * self.WEIGHTS["complexity"] +
            length_score * self.WEIGHTS["length"] +
            nesting_score * self.WEIGHTS["nesting"] +
            param_score * self.WEIGHTS["parameters"] +
            churn_score * self.WEIGHTS["churn"] +
            novelty_score * self.WEIGHTS["novelty"] + pattern_bonus
        )

        return InterestScore(
            total = min(weighted_total,
                        100),
            complexity_score = complexity_score * self.WEIGHTS["complexity"],
            length_score = length_score * self.WEIGHTS["length"],
            nesting_score = nesting_score * self.WEIGHTS["nesting"],
            parameter_score = param_score * self.WEIGHTS["parameters"],
            churn_score = churn_score * self.WEIGHTS["churn"],
            novelty_score = novelty_score * self.WEIGHTS["novelty"],
            pattern_bonus = pattern_bonus,
        )

    def _calculate_pattern_bonus(
        self,
        decorators: list[str] | None,
        is_async: bool,
        source: str,
    ) -> float:
        """
        Calculate bonus points for interesting code patterns
        """
        bonus = 0.0

        if is_async:
            bonus += self.PATTERN_BONUSES["async"]

        if decorators:
            bonus += len(decorators) * self.PATTERN_BONUSES["decorator"]

            decorator_text = " ".join(decorators).lower()
            if "property" in decorator_text:
                bonus += self.PATTERN_BONUSES["property"]
            if "classmethod" in decorator_text or "staticmethod" in decorator_text:
                bonus += self.PATTERN_BONUSES["class_method"]
            if "abstractmethod" in decorator_text:
                bonus += self.PATTERN_BONUSES["abstract"]
            if "dataclass" in decorator_text:
                bonus += self.PATTERN_BONUSES["dataclass"]

        if "yield" in source:
            bonus += self.PATTERN_BONUSES["generator"]
        if "__enter__" in source or "__exit__" in source:
            bonus += self.PATTERN_BONUSES["context_manager"]

        return bonus

    def get_git_stats(
        self,
        file_path: Path,
        _start_line: int = 0,
        _end_line: int = 0
    ) -> GitStats:
        """
        Get git statistics for a file
        """
        if not self.git_repo:
            return GitStats()

        try:
            commits_30d = 0
            commits_90d = 0
            last_modified = None
            authors = set()

            now = datetime.now()
            cutoff_30d = now - timedelta(days = 30)
            cutoff_90d = now - timedelta(days = 90)

            rel_path = str(file_path)
            with contextlib.suppress(ValueError):
                rel_path = str(file_path.relative_to(self.git_repo.working_dir))

            for commit in self.git_repo.iter_commits(paths = rel_path,
                                                     max_count = 100):
                commit_date = datetime.fromtimestamp(commit.committed_date)

                if last_modified is None:
                    last_modified = commit_date

                if commit_date >= cutoff_30d:
                    commits_30d += 1
                if commit_date >= cutoff_90d:
                    commits_90d += 1

                authors.add(commit.author.email)

            is_new = commits_90d <= 2 and last_modified and (
                now - last_modified
            ).days <= 14

            return GitStats(
                commit_count_30d = commits_30d,
                commit_count_90d = commits_90d,
                last_modified = last_modified,
                unique_authors = len(authors),
                is_new = is_new,
            )

        except Exception:
            return GitStats()


def calculate_interest(
    metrics: ComplexityMetrics,
    git_stats: GitStats | None = None,
    decorators: list[str] | None = None,
    is_async: bool = False,
    source: str = "",
) -> InterestScore:
    """
    Convenience function to calculate interest score
    """
    scorer = InterestScorer()
    return scorer.score(metrics, git_stats, decorators, is_async, source)
