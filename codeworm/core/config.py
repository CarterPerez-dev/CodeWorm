"""
ⒸAngelaMos | 2026
config.py
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class DevLogSettings(BaseModel):
    """
    Settings for the DevLog output repository
    """
    repo_path: Path
    remote: str = ""
    branch: str = "main"

    @field_validator("repo_path", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """
        Expand ~ and environment variables in path
        """
        if isinstance(v, str):
            return Path(os.path.expanduser(os.path.expandvars(v)))
        return v


class OllamaSettings(BaseModel):
    """
    Settings for Ollama LLM connection
    """
    host: str = "localhost"
    port: int = 11434
    model: str = "qwen2.5:7b"
    temperature: float = 0.3
    num_ctx: int = 16384
    num_predict: int = 4096
    keep_alive: str = "-1"

    @property
    def base_url(self) -> str:
        """
        Construct the base URL for Ollama API
        """
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
            "**/vendor/**",
            "**/target/**",
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

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """
        Expand ~ and environment variables in path
        """
        if isinstance(v, str):
            return Path(os.path.expanduser(os.path.expandvars(v)))
        return v


class PromptSettings(BaseModel):
    """
    Settings for LLM prompts loaded from prompts.yaml
    """
    style: str = "technical"
    system_prompt: str = ""
    documentation_template: str = ""
    commit_message_template: str = ""
    language_hints: dict[str, str] = Field(default_factory=dict)


class CodeWormSettings(BaseSettings):
    """
    Main application settings
    Loads from YAML config files with env var overrides
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
    config_dir: Path = DEFAULT_CONFIG_DIR
    devlog: DevLogSettings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    schedule: ScheduleSettings = Field(default_factory=ScheduleSettings)
    analyzer: AnalyzerSettings = Field(default_factory=AnalyzerSettings)
    repos: list[RepoEntry] = Field(default_factory=list)
    prompts: PromptSettings = Field(default_factory=PromptSettings)
    github_token: SecretStr | None = None

    @field_validator("data_dir", "config_dir", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """
        Expand ~ and environment variables in path
        """
        if isinstance(v, str):
            return Path(os.path.expanduser(os.path.expandvars(v)))
        return v

    @property
    def db_path(self) -> Path:
        """
        Path to the SQLite database
        """
        return self.data_dir / "codeworm.db"


def load_yaml_file(path: Path) -> dict:
    """
    Load a YAML file and return its contents
    Returns empty dict if file does not exist
    """
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def merge_configs(base: dict, override: dict) -> dict:
    """
    Deep merge two config dictionaries
    Override takes precedence
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result


def load_config_from_yaml(config_dir: Path | None = None) -> dict:
    """
    Load configuration from YAML files in config directory
    """
    if config_dir is None:
        config_dir = DEFAULT_CONFIG_DIR

    config_dir = Path(os.path.expanduser(os.path.expandvars(str(config_dir))))

    config = load_yaml_file(config_dir / "config.yaml")

    repos_config = load_yaml_file(config_dir / "repos.yaml")
    if "repositories" in repos_config:
        repos = [r for r in repos_config["repositories"] if r.get("enabled", True)]
        config["repos"] = repos

    prompts_config = load_yaml_file(config_dir / "prompts.yaml")
    if prompts_config:
        config["prompts"] = prompts_config

    return config


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


def load_settings(config_dir: Path | str | None = None, **overrides) -> CodeWormSettings:
    """
    Load settings from YAML files and optional overrides

    Priority (highest to lowest):
    1. Explicit overrides passed to this function
    2. Environment variables (CODEWORM_ prefix)
    3. YAML config files
    4. Default values
    """
    global _settings

    if config_dir is not None:
        config_dir = Path(os.path.expanduser(os.path.expandvars(str(config_dir))))

    yaml_config = load_config_from_yaml(config_dir)

    merged = merge_configs(yaml_config, overrides)

    if config_dir is not None:
        merged["config_dir"] = config_dir

    _settings = CodeWormSettings(**merged)
    _settings.data_dir.mkdir(parents=True, exist_ok=True)

    return _settings


def get_enabled_repos() -> list[RepoEntry]:
    """
    Get list of enabled repositories from current settings
    """
    settings = get_settings()
    return [r for r in settings.repos if r.enabled]
