"""
ⒸAngelaMos | 2026
config.py
"""
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DevLogSettings(BaseModel):
    """
    Settings for the DevLog output repository
    """

    repo_path: Path
    remote: str = ""
    branch: str = "main"


class OllamaSettings(BaseModel):
    """
    Settings for Ollama LLM connection
    """

    host: str = "localhost"
    port: int = 29999
    model: str = "qwen2.5:7b"
    temperature: float = 0.2
    num_ctx: int = 16384
    num_predict: int = 4096
    keep_alive: str = "-1"

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class ScheduleSettings(BaseModel):
    """
    Settings for human-like commit scheduling
    """

    enabled: bool = True
    min_commits_per_day: Annotated[int, Field(ge=1, le=50)] = 12
    max_commits_per_day: Annotated[int, Field(ge=1, le=50)] = 18
    timezone: str = "America/Los_Angeles"
    prefer_hours: list[int] = Field(default_factory=lambda: [9, 10, 11, 14, 15, 16, 20, 21, 22])
    avoid_hours: list[int] = Field(default_factory=lambda: [3, 4, 5, 6, 7])
    weekend_reduction: float = 0.7
    min_gap_minutes: int = 30


class AnalyzerSettings(BaseModel):
    """
    Settings for code analysis and snippet selection
    """

    min_complexity: int = 3
    max_lines: int = 150
    min_lines: int = 15
    include_patterns: list[str] = Field(
        default_factory=lambda: ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.go", "**/*.rs"]
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "**/test_*.py",
            "**/*_test.py",
            "**/*_test.go",
            "**/*.spec.ts",
            "**/*.test.ts",
            "**/node_modules/**",
            "**/venv/**",
            "**/.venv/**",
            "**/__pycache__/**",
            "**/dist/**",
            "**/build/**",
            "**/.git/**",
        ]
    )


class RepoEntry(BaseModel):
    """
    Configuration for a source repository to scan
    """

    name: str
    path: Path
    weight: Annotated[int, Field(ge=1, le=10)] = 5
    enabled: bool = True


class CodeWormSettings(BaseSettings):
    """
    Main application settings loaded from env vars and .env file
    """

    model_config = SettingsConfigDict(
        env_prefix="CODEWORM_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    debug: bool = False
    data_dir: Path = Path("data")
    devlog: DevLogSettings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    analyzer: AnalyzerSettings = Field(default_factory=AnalyzerSettings)
    repos: list[RepoEntry] = Field(default_factory=list)
    github_token: SecretStr | None = None

    @property
    def db_path(self) -> Path:
        return self.data_dir / "codeworm.db"


_settings: CodeWormSettings | None = None


def get_settings() -> CodeWormSettings:
    """
    Get the current settings instance
    Raises RuntimeError if settings not initialized
    """
    global _settings
    if _settings is None:
        raise RuntimeError("Settings not initialized. Call load_settings() first.")
    return _settings


def load_settings(**overrides) -> CodeWormSettings:
    """
    Load settings from environment and optional overrides
    Creates data directory if it does not exist
    """
    global _settings
    _settings = CodeWormSettings(**overrides)
    _settings.data_dir.mkdir(parents=True, exist_ok=True)
    return _settings
