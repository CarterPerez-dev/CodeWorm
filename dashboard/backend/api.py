"""
ⒸAngelaMos | 2026
dashboard/backend/api.py
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Query

from dashboard.backend.models import (
    ActivityDay,
    LanguageBreakdown,
    RecentDoc,
    RepoStatus,
    StatsResponse,
)


router = APIRouter()


def _get_db_path() -> Path:
    return Path(os.environ.get("CODEWORM_DB_PATH", "data/codeworm.db"))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return column in {row[1] for row in cursor.fetchall()}


@router.get("/stats", response_model = StatsResponse)
async def get_stats() -> StatsResponse:
    db = _get_db_path()
    if not db.exists():
        return StatsResponse()

    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documented_snippets"
                             ).fetchone()[0]

        by_repo = dict(
            conn.execute(
                "SELECT source_repo, COUNT(*) FROM documented_snippets "
                "GROUP BY source_repo"
            ).fetchall()
        )

        if _has_column(conn, "documented_snippets", "doc_type"):
            by_doc_type = dict(
                conn.execute(
                    "SELECT doc_type, COUNT(*) FROM documented_snippets "
                    "GROUP BY doc_type"
                ).fetchall()
            )
        else:
            by_doc_type = {"function_doc": total}

        last_7 = conn.execute(
            "SELECT COUNT(*) FROM documented_snippets "
            "WHERE documented_at > datetime('now', '-7 days')"
        ).fetchone()[0]

        last_30 = conn.execute(
            "SELECT COUNT(*) FROM documented_snippets "
            "WHERE documented_at > datetime('now', '-30 days')"
        ).fetchone()[0]

        today = conn.execute(
            "SELECT COUNT(*) FROM documented_snippets "
            "WHERE date(documented_at) = date('now')"
        ).fetchone()[0]

        lang_rows = conn.execute(
            "SELECT "
            "CASE "
            "  WHEN source_file LIKE '%.py' THEN 'python' "
            "  WHEN source_file LIKE '%.ts' THEN 'typescript' "
            "  WHEN source_file LIKE '%.tsx' THEN 'tsx' "
            "  WHEN source_file LIKE '%.js' THEN 'javascript' "
            "  WHEN source_file LIKE '%.go' THEN 'go' "
            "  WHEN source_file LIKE '%.rs' THEN 'rust' "
            "  ELSE 'other' "
            "END AS lang, COUNT(*) "
            "FROM documented_snippets GROUP BY lang"
        ).fetchall()
        by_language = dict(lang_rows)

    return StatsResponse(
        total_documented = total,
        by_repo = by_repo,
        by_language = by_language,
        by_doc_type = by_doc_type,
        last_7_days = last_7,
        last_30_days = last_30,
        today = today,
    )


@router.get("/repos", response_model = list[RepoStatus])
async def get_repos() -> list[RepoStatus]:
    config_dir = Path(os.environ.get("CODEWORM_CONFIG_DIR", "config"))
    repos_path = config_dir / "repos.yaml"

    repos: list[RepoStatus] = []
    if repos_path.exists():
        import yaml

        with repos_path.open() as f:
            data = yaml.safe_load(f) or {}

        db = _get_db_path()
        repo_counts: dict[str, int] = {}
        repo_last: dict[str, str] = {}

        if db.exists():
            with _get_conn() as conn:
                for row in conn.execute(
                        "SELECT source_repo, COUNT(*), MAX(documented_at) "
                        "FROM documented_snippets GROUP BY source_repo"
                ).fetchall():
                    repo_counts[row[0]] = row[1]
                    repo_last[row[0]] = row[2]

        for entry in data.get("repositories", []):
            from datetime import datetime

            name = entry.get("name", "")
            last_str = repo_last.get(name)
            last_dt = datetime.fromisoformat(last_str) if last_str else None

            repos.append(
                RepoStatus(
                    name = name,
                    path = str(entry.get("path",
                                         "")),
                    weight = entry.get("weight",
                                       5),
                    enabled = entry.get("enabled",
                                        True),
                    docs_generated = repo_counts.get(name,
                                                     0),
                    last_activity = last_dt,
                )
            )

    return repos


@router.get("/recent", response_model = list[RecentDoc])
async def get_recent(
    limit: int = Query(default = 50,
                       ge = 1,
                       le = 200),
    offset: int = Query(default = 0,
                        ge = 0),
    repo: str | None = Query(default = None),
    doc_type: str | None = Query(default = None),
) -> list[RecentDoc]:
    db = _get_db_path()
    if not db.exists():
        return []

    query = "SELECT * FROM documented_snippets"
    params: list = []
    conditions: list[str] = []
    has_doc_type = False

    with _get_conn() as check_conn:
        has_doc_type = _has_column(check_conn, "documented_snippets", "doc_type")

    if repo:
        conditions.append("source_repo = ?")
        params.append(repo)
    if doc_type and has_doc_type:
        conditions.append("doc_type = ?")
        params.append(doc_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY documented_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    results = []
    for row in rows:
        results.append(
            RecentDoc(
                id = row["id"],
                source_repo = row["source_repo"],
                source_file = row["source_file"],
                function_name = row["function_name"],
                class_name = row["class_name"],
                doc_type = row["doc_type"]
                if "doc_type" in row.keys() else "function_doc",
                documented_at = row["documented_at"],
                snippet_path = row["snippet_path"],
                git_commit = row["git_commit"],
            )
        )

    return results


@router.get("/activity", response_model = list[ActivityDay])
async def get_activity(
    days: int = Query(default = 90,
                      ge = 1,
                      le = 365),
) -> list[ActivityDay]:
    db = _get_db_path()
    if not db.exists():
        return []

    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT date(documented_at) AS day, COUNT(*) AS cnt "
            "FROM documented_snippets "
            "WHERE documented_at > datetime('now', ?) "
            "GROUP BY day ORDER BY day",
            (f"-{days} days",
             ),
        ).fetchall()

    return [ActivityDay(date = row["day"], count = row["cnt"]) for row in rows]


@router.get("/languages", response_model = list[LanguageBreakdown])
async def get_languages() -> list[LanguageBreakdown]:
    db = _get_db_path()
    if not db.exists():
        return []

    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM documented_snippets"
                             ).fetchone()[0]

        if total == 0:
            return []

        rows = conn.execute(
            "SELECT "
            "CASE "
            "  WHEN source_file LIKE '%.py' THEN 'python' "
            "  WHEN source_file LIKE '%.ts' THEN 'typescript' "
            "  WHEN source_file LIKE '%.tsx' THEN 'tsx' "
            "  WHEN source_file LIKE '%.js' THEN 'javascript' "
            "  WHEN source_file LIKE '%.go' THEN 'go' "
            "  WHEN source_file LIKE '%.rs' THEN 'rust' "
            "  ELSE 'other' "
            "END AS lang, COUNT(*) AS cnt "
            "FROM documented_snippets GROUP BY lang ORDER BY cnt DESC"
        ).fetchall()

    return [
        LanguageBreakdown(
            language = row["lang"],
            count = row["cnt"],
            percentage = round(row["cnt"] / total * 100,
                               1),
        ) for row in rows
    ]
