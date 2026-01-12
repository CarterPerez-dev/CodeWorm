"""
ⒸAngelaMos | 2026
analysis/analyzer.py
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from git import InvalidGitRepositoryError, Repo

from codeworm.analysis.complexity import ComplexityAnalyzer, ComplexityMetrics
from codeworm.analysis.parser import CodeExtractor, ParsedFunction, ParserManager
from codeworm.analysis.scanner import RepoScanner, ScannedFile, WeightedRepoSelector
from codeworm.analysis.scoring import GitStats, InterestScore, InterestScorer
from codeworm.models import CodeSnippet, Language

if TYPE_CHECKING:
    from collections.abc import Iterator

    from codeworm.core.config import AnalyzerSettings, RepoEntry


@dataclass
class AnalysisCandidate:
    """
    A code snippet candidate for documentation
    """

    snippet: CodeSnippet
    parsed_function: ParsedFunction
    complexity: ComplexityMetrics | None
    git_stats: GitStats
    interest_score: InterestScore
    scanned_file: ScannedFile

    @property
    def score(self) -> float:
        return self.interest_score.total

    @property
    def is_worth_documenting(self) -> bool:
        """
        Check if this candidate meets minimum thresholds
        """
        return self.score >= 25 and self.snippet.line_count >= 10


class CodeAnalyzer:
    """
    Main code analysis engine
    Combines parsing, complexity analysis, and interest scoring
    """

    def __init__(
        self,
        repos: list[RepoEntry],
        settings: AnalyzerSettings | None = None,
    ) -> None:
        """
        Initialize analyzer with repository configurations
        """
        self.repos = repos
        self.settings = settings
        self.repo_selector = WeightedRepoSelector(repos)
        self.scanner = RepoScanner(
            include_patterns=settings.include_patterns if settings else None,
            exclude_patterns=settings.exclude_patterns if settings else None,
        )
        self.complexity_analyzer = ComplexityAnalyzer()
        self.scorer = InterestScorer()

        self._git_repos: dict[Path, Repo | None] = {}

        ParserManager.initialize()

    def _get_git_repo(self, repo_path: Path) -> Repo | None:
        """
        Get or create git repo instance for a path
        """
        if repo_path not in self._git_repos:
            try:
                self._git_repos[repo_path] = Repo(repo_path)
            except InvalidGitRepositoryError:
                self._git_repos[repo_path] = None
        return self._git_repos[repo_path]

    def analyze_file(self, scanned_file: ScannedFile) -> Iterator[AnalysisCandidate]:
        """
        Analyze a single file and yield documentation candidates
        """
        try:
            source = scanned_file.path.read_text(encoding="utf-8")
        except Exception:
            return

        extractor = CodeExtractor(source, scanned_file.language)
        complexity_results = self.complexity_analyzer.analyze_source(
            source,
            str(scanned_file.path),
        )
        complexity_map = {m.name: m for m in complexity_results}

        git_repo = self._get_git_repo(scanned_file.path.parent)
        if git_repo:
            self.scorer.git_repo = git_repo

        for parsed_func in extractor.extract_functions():
            if self._should_skip_function(parsed_func):
                continue

            complexity = complexity_map.get(parsed_func.name)
            if not complexity:
                for name, metrics in complexity_map.items():
                    if name.endswith(f".{parsed_func.name}"):
                        complexity = metrics
                        break

            git_stats = self.scorer.get_git_stats(
                scanned_file.path,
                parsed_func.start_line,
                parsed_func.end_line,
            )

            if complexity:
                interest = self.scorer.score(
                    complexity,
                    git_stats,
                    parsed_func.decorators,
                    parsed_func.is_async,
                    parsed_func.source,
                )
            else:
                interest = InterestScore(
                    total=20,
                    complexity_score=0,
                    length_score=0,
                    nesting_score=0,
                    parameter_score=0,
                    churn_score=0,
                    novelty_score=0,
                )

            snippet = CodeSnippet(
                repo=scanned_file.repo_name,
                file_path=scanned_file.path,
                function_name=parsed_func.name,
                class_name=parsed_func.class_name,
                language=scanned_file.language,
                source=parsed_func.source,
                start_line=parsed_func.start_line,
                end_line=parsed_func.end_line,
                complexity=complexity.cyclomatic_complexity if complexity else 0,
                nesting_depth=complexity.max_nesting_depth if complexity else 0,
                parameter_count=complexity.parameter_count if complexity else 0,
                interest_score=interest.total,
            )

            yield AnalysisCandidate(
                snippet=snippet,
                parsed_function=parsed_func,
                complexity=complexity,
                git_stats=git_stats,
                interest_score=interest,
                scanned_file=scanned_file,
            )

    def _should_skip_function(self, func: ParsedFunction) -> bool:
        """
        Check if function should be skipped from analysis
        """
        if func.name.startswith("_") and not func.name.startswith("__"):
            return random.random() > 0.3

        skip_names = {"__init__", "__str__", "__repr__", "main", "setUp", "tearDown"}
        if func.name in skip_names:
            return True

        line_count = func.end_line - func.start_line + 1
        if self.settings:
            if line_count < self.settings.min_lines:
                return True
            if line_count > self.settings.max_lines:
                return True

        return False

    def find_candidates(
        self,
        repo: RepoEntry | None = None,
        limit: int = 50,
    ) -> list[AnalysisCandidate]:
        """
        Find documentation candidates from repositories
        """
        candidates: list[AnalysisCandidate] = []

        if repo:
            repos_to_scan = [repo]
        else:
            repos_to_scan = [r for r in self.repos if r.enabled]

        for repo_config in repos_to_scan:
            for scanned_file in self.scanner.scan_repo(repo_config.path, repo_config.name):
                for candidate in self.analyze_file(scanned_file):
                    if candidate.is_worth_documenting:
                        candidates.append(candidate)

                    if len(candidates) >= limit * 3:
                        break

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:limit]

    def select_for_documentation(
        self,
        min_score: float = 30,
        count: int = 1,
    ) -> list[AnalysisCandidate]:
        """
        Select top candidates for documentation using weighted random
        """
        selected_repo = self.repo_selector.select()
        if not selected_repo:
            return []

        candidates = self.find_candidates(repo=selected_repo, limit=100)
        eligible = [c for c in candidates if c.score >= min_score]

        if not eligible:
            return []

        if count >= len(eligible):
            return eligible

        weights = [c.score for c in eligible]
        selected = random.choices(eligible, weights=weights, k=count)

        return selected


def analyze_repository(repo_path: Path, repo_name: str) -> list[AnalysisCandidate]:
    """
    Convenience function to analyze a single repository
    """
    from codeworm.core.config import RepoEntry

    repo = RepoEntry(name=repo_name, path=repo_path, weight=5)
    analyzer = CodeAnalyzer([repo])
    return analyzer.find_candidates(repo)
