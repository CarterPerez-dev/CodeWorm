"""
ⒸAngelaMos | 2026
git/ops.py
"""
from __future__ import annotations

import random
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError, InvalidGitRepositoryError, Repo
from git.exc import GitError

from codeworm.core import get_logger

if TYPE_CHECKING:
    from codeworm.llm.generator import GeneratedDocumentation

logger = get_logger("git")


class GitOperationError(Exception):
    """
    Base exception for git operations
    """

    pass


class GitPushError(GitOperationError):
    """
    Failed to push to remote
    """

    pass


class GitConflictError(GitOperationError):
    """
    Merge conflict detected
    """

    pass


@dataclass
class CommitResult:
    """
    Result of a git commit operation
    """

    commit_hash: str
    message: str
    files_changed: int
    committed_at: datetime
    branch: str


COMMIT_PREFIXES = [
    "Document",
    "Add docs for",
    "Analyze",
    "Detail",
    "Explain",
    "Cover",
]

MINOR_FIX_MESSAGES = [
    "fix typo in {name} docs",
    "update formatting in {name}",
    "clarify {name} explanation",
    "improve {name} documentation",
    "refine {name} description",
]


class DevLogRepository:
    """
    Manages the DevLog output repository
    """

    def __init__(self, repo_path: Path, remote: str = "", branch: str = "main") -> None:
        """
        Initialize with repository path
        """
        self.repo_path = repo_path
        self.remote_url = remote
        self.branch = branch
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """
        Get or initialize the git repository
        """
        if self._repo is None:
            if not self.repo_path.exists():
                self.repo_path.mkdir(parents=True, exist_ok=True)

            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                self._repo = Repo.init(self.repo_path)
                logger.info("initialized_new_repo", path=str(self.repo_path))

        return self._repo

    def ensure_directory_structure(self) -> None:
        """
        Create the DevLog directory structure if needed
        """
        dirs = [
            "snippets/python",
            "snippets/typescript",
            "snippets/javascript",
            "snippets/go",
            "snippets/rust",
            "analysis/weekly",
            "analysis/monthly",
            "patterns",
            "stats",
        ]

        for dir_path in dirs:
            full_path = self.repo_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            gitkeep = full_path / ".gitkeep"
            if not gitkeep.exists():
                gitkeep.touch()

    def write_snippet(
        self,
        content: str,
        filename: str,
        language: str,
    ) -> Path:
        """
        Write a snippet file to the appropriate directory
        """
        snippet_dir = self.repo_path / "snippets" / language
        snippet_dir.mkdir(parents=True, exist_ok=True)

        file_path = snippet_dir / filename
        file_path.write_text(content, encoding="utf-8")

        return file_path

    def commit(
        self,
        message: str,
        files: list[Path] | None = None,
    ) -> CommitResult:
        """
        Create a commit with the specified message
        """
        repo = self.repo

        if files:
            for file_path in files:
                try:
                    rel_path = file_path.relative_to(self.repo_path)
                    repo.index.add([str(rel_path)])
                except ValueError:
                    repo.index.add([str(file_path)])
        else:
            repo.git.add(A=True)

        if not repo.index.diff("HEAD") and not repo.untracked_files:
            raise GitOperationError("Nothing to commit")

        commit = repo.index.commit(message)

        return CommitResult(
            commit_hash=commit.hexsha[:8],
            message=message,
            files_changed=len(commit.stats.files),
            committed_at=datetime.now(),
            branch=repo.active_branch.name,
        )

    def push(
        self,
        remote: str = "origin",
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> bool:
        """
        Push commits to remote with retry logic
        """
        if not self.remote_url:
            logger.debug("no_remote_configured")
            return False

        repo = self.repo

        try:
            repo.remote(remote)
        except ValueError:
            repo.create_remote(remote, self.remote_url)
            logger.info("created_remote", name=remote, url=self.remote_url)

        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                repo.git.push(remote, self.branch, force_with_lease=True)
                logger.info("push_successful", remote=remote, branch=self.branch)
                return True

            except GitCommandError as e:
                last_error = e
                error_msg = str(e).lower()

                if "conflict" in error_msg or "rejected" in error_msg:
                    raise GitConflictError(f"Push rejected due to conflict: {e}")

                if self._is_transient_error(error_msg):
                    logger.warning(
                        "push_retry",
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise GitPushError(f"Push failed: {e}")

        raise GitPushError(f"Push failed after {max_retries} retries: {last_error}")

    def _is_transient_error(self, error_msg: str) -> bool:
        """
        Check if error is transient and worth retrying
        """
        transient_patterns = [
            "connection reset",
            "connection refused",
            "connection timed out",
            "network unreachable",
            "could not resolve host",
            "ssl",
            "temporary failure",
        ]
        return any(pattern in error_msg for pattern in transient_patterns)

    def pull(self, remote: str = "origin") -> bool:
        """
        Pull latest changes from remote
        """
        try:
            self.repo.git.pull(remote, self.branch, rebase=True)
            return True
        except GitError as e:
            if "conflict" in str(e).lower():
                raise GitConflictError(f"Pull conflict: {e}")
            logger.warning("pull_failed", error=str(e))
            return False

    def get_recent_commits(self, count: int = 10) -> list[dict]:
        """
        Get recent commit information
        """
        commits = []
        for commit in self.repo.iter_commits(max_count=count):
            commits.append({
                "hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": datetime.fromtimestamp(commit.committed_date),
            })
        return commits


class CommitMessageGenerator:
    """
    Generates varied commit messages for natural patterns
    """

    def __init__(self) -> None:
        """
        Initialize generator
        """
        self._last_prefix: str | None = None

    def generate(self, function_name: str, language: str, is_minor: bool = False) -> str:
        """
        Generate a commit message for a documentation commit
        """
        if is_minor:
            template = random.choice(MINOR_FIX_MESSAGES)
            return template.format(name=function_name)

        prefix = random.choice([p for p in COMMIT_PREFIXES if p != self._last_prefix])
        self._last_prefix = prefix

        templates = [
            f"{prefix} {function_name} implementation",
            f"{prefix} {function_name} in {language}",
            f"{prefix} {function_name}",
            f"add snippet: {function_name}",
            f"cover {function_name} patterns",
        ]

        return random.choice(templates)


def commit_documentation(
    devlog_repo: DevLogRepository,
    documentation: GeneratedDocumentation,
    language: str,
    function_name: str,
) -> CommitResult:
    """
    Convenience function to commit generated documentation
    """
    file_path = devlog_repo.write_snippet(
        content=documentation.content,
        filename=documentation.snippet_filename,
        language=language,
    )

    return devlog_repo.commit(
        message=documentation.commit_message,
        files=[file_path],
    )
