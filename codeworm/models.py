"""
ⒸAngelaMos | 2026
models.py
"""
from enum import Enum
from pathlib import Path
from typing import Annotated
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Language(str, Enum):
    """
    Supported programming languages for code analysis
    """
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"


LANGUAGE_EXTENSIONS: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TSX,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".go": Language.GO,
    ".rs": Language.RUST,
}


class RepoConfig(BaseModel):
    """
    Configuration for a source repository to scan
    """
    name: str
    path: Path
    weight: Annotated[int, Field(ge=1, le=10)] = 5
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Repository path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Repository path is not a directory: {v}")
        return v


class CodeSnippet(BaseModel):
    """
    A code snippet extracted from a source file for analysis
    """
    repo: str
    file_path: Path
    function_name: str | None = None
    class_name: str | None = None
    language: Language
    source: str
    start_line: int
    end_line: int
    complexity: float = 0.0
    nesting_depth: int = 0
    parameter_count: int = 0
    interest_score: float = 0.0

    @property
    def display_name(self) -> str:
        if self.class_name and self.function_name:
            return f"{self.class_name}.{self.function_name}"
        return self.function_name or self.class_name or self.file_path.stem

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


class DocumentedSnippet(BaseModel):
    """
    Record of a snippet that has been documented and committed
    Stored in SQLite for deduplication
    """
    id: str
    source_repo: str
    source_file: str
    function_name: str | None = None
    class_name: str | None = None
    code_hash: str
    documented_at: datetime
    snippet_path: str
    git_commit: str | None = None

    @property
    def display_name(self) -> str:
        if self.class_name and self.function_name:
            return f"{self.class_name}.{self.function_name}"
        return self.function_name or self.class_name or Path(self.source_file).stem


class AnalysisResult(BaseModel):
    """
    Result of analyzing and documenting a code snippet
    """
    snippet: CodeSnippet
    documentation: str
    commit_message: str
    snippet_filename: str


class CommitType(str, Enum):
    """
    Types of commits the daemon can make for natural variation
    """
    NEW_DOC = "new_doc"
    UPDATE_DOC = "update_doc"
    MINOR_FIX = "minor_fix"
    REORGANIZE = "reorganize"


class ScheduledCommit(BaseModel):
    """
    A commit scheduled for future execution
    """
    scheduled_time: datetime
    commit_type: CommitType
    analysis_result: AnalysisResult | None = None
    executed: bool = False
    executed_at: datetime | None = None
