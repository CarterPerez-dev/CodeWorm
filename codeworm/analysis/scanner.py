"""
ⒸAngelaMos | 2026
analysis/scanner.py
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pathspec
from git import InvalidGitRepositoryError, Repo

from codeworm.models import LANGUAGE_EXTENSIONS, Language

if TYPE_CHECKING:
    from collections.abc import Iterator

    from codeworm.core.config import RepoEntry


@dataclass
class ScannedFile:
    """
    A file discovered during repository scanning
    """

    path: Path
    language: Language
    repo_name: str
    relative_path: Path
    size_bytes: int
    is_binary: bool = False

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


@dataclass
class RepoStats:
    """
    Statistics about a scanned repository
    """

    name: str
    path: Path
    total_files: int = 0
    files_by_language: dict[Language, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    is_git_repo: bool = False
    branch: str | None = None


class GitignoreFilter:
    """
    Filters files based on gitignore patterns
    """

    def __init__(self, repo_root: Path, extra_patterns: list[str] | None = None) -> None:
        """
        Initialize filter with gitignore from repo root
        """
        self.repo_root = repo_root
        patterns: list[str] = []

        gitignore_path = repo_root / ".gitignore"
        if gitignore_path.exists():
            patterns.extend(gitignore_path.read_text().splitlines())

        if extra_patterns:
            patterns.extend(extra_patterns)

        patterns.extend([
            ".git/",
            "__pycache__/",
            "*.pyc",
            "node_modules/",
            ".venv/",
            "venv/",
            ".env",
            "*.egg-info/",
        ])

        self.spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def is_ignored(self, path: Path) -> bool:
        """
        Check if a path should be ignored
        """
        try:
            rel_path = path.relative_to(self.repo_root)
            return self.spec.match_file(str(rel_path))
        except ValueError:
            return False


class RepoScanner:
    """
    Scans repositories to find code files for analysis
    """

    DEFAULT_EXCLUDE = [
        "**/test_*.py",
        "**/*_test.py",
        "**/*_test.go",
        "**/*.spec.ts",
        "**/*.test.ts",
        "**/*.test.js",
        "**/tests/**",
        "**/test/**",
        "**/__tests__/**",
        "**/node_modules/**",
        "**/vendor/**",
        "**/dist/**",
        "**/build/**",
        "**/.git/**",
    ]

    MAX_FILE_SIZE = 1024 * 1024
    BINARY_CHECK_BYTES = 8192

    def __init__(
        self,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """
        Initialize scanner with file patterns
        """
        self.include_patterns = include_patterns or ["**/*.py", "**/*.ts", "**/*.go", "**/*.rs", "**/*.js"]
        self.exclude_patterns = exclude_patterns or self.DEFAULT_EXCLUDE
        self._exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", self.exclude_patterns)

    def scan_repo(self, repo_path: Path, repo_name: str) -> Iterator[ScannedFile]:
        """
        Scan a repository and yield discovered files
        """
        if not repo_path.exists():
            return

        gitignore_filter = GitignoreFilter(repo_path)
        include_spec = pathspec.PathSpec.from_lines("gitwildmatch", self.include_patterns)

        for root, dirs, files in os.walk(repo_path):
            root_path = Path(root)

            dirs[:] = [
                d for d in dirs
                if not d.startswith(".")
                and not gitignore_filter.is_ignored(root_path / d)
            ]

            for filename in files:
                file_path = root_path / filename

                try:
                    rel_path = file_path.relative_to(repo_path)
                except ValueError:
                    continue

                if not include_spec.match_file(str(rel_path)):
                    continue

                if self._exclude_spec.match_file(str(rel_path)):
                    continue

                if gitignore_filter.is_ignored(file_path):
                    continue

                ext = file_path.suffix.lower()
                language = LANGUAGE_EXTENSIONS.get(ext)
                if not language:
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size > self.MAX_FILE_SIZE:
                        continue
                    if stat.st_size == 0:
                        continue

                    is_binary = self._is_binary(file_path)
                    if is_binary:
                        continue

                    yield ScannedFile(
                        path=file_path,
                        language=language,
                        repo_name=repo_name,
                        relative_path=rel_path,
                        size_bytes=stat.st_size,
                        is_binary=False,
                    )

                except (OSError, PermissionError):
                    continue

    def _is_binary(self, file_path: Path) -> bool:
        """
        Check if file appears to be binary
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(self.BINARY_CHECK_BYTES)
                if b"\x00" in chunk:
                    return True
                text_chars = sum(1 for b in chunk if 32 <= b <= 126 or b in (9, 10, 13))
                return text_chars / len(chunk) < 0.7 if chunk else False
        except Exception:
            return True

    def get_repo_stats(self, repo_path: Path, repo_name: str) -> RepoStats:
        """
        Get statistics about a repository
        """
        stats = RepoStats(name=repo_name, path=repo_path)

        try:
            git_repo = Repo(repo_path)
            stats.is_git_repo = True
            stats.branch = git_repo.active_branch.name
        except InvalidGitRepositoryError:
            stats.is_git_repo = False

        for scanned_file in self.scan_repo(repo_path, repo_name):
            stats.total_files += 1
            stats.total_size_bytes += scanned_file.size_bytes

            lang = scanned_file.language
            stats.files_by_language[lang] = stats.files_by_language.get(lang, 0) + 1

        return stats


class WeightedRepoSelector:
    """
    Selects repositories based on configured weights
    """

    def __init__(self, repos: list[RepoEntry]) -> None:
        """
        Initialize with list of repo configurations
        """
        self.repos = [r for r in repos if r.enabled]
        self._weights = [r.weight for r in self.repos]
        self._total_weight = sum(self._weights)

    def select(self) -> RepoEntry | None:
        """
        Select a repository using weighted random selection
        """
        if not self.repos:
            return None

        return random.choices(self.repos, weights=self._weights, k=1)[0]

    def select_multiple(self, count: int) -> list[RepoEntry]:
        """
        Select multiple repositories allowing duplicates based on weight
        """
        if not self.repos:
            return []

        return random.choices(self.repos, weights=self._weights, k=count)


def scan_repositories(
    repos: list[RepoEntry],
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> Iterator[tuple[RepoEntry, ScannedFile]]:
    """
    Scan multiple repositories and yield files with their repo config
    """
    scanner = RepoScanner(include_patterns, exclude_patterns)

    for repo in repos:
        if not repo.enabled:
            continue

        for scanned_file in scanner.scan_repo(repo.path, repo.name):
            yield repo, scanned_file
