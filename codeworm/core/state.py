"""
ⒸAngelaMos | 2026
state.py
"""
import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from codeworm.models import CodeSnippet, DocumentedSnippet


SCHEMA = """
CREATE TABLE IF NOT EXISTS documented_snippets (
    id TEXT PRIMARY KEY,
    source_repo TEXT NOT NULL,
    source_file TEXT NOT NULL,
    function_name TEXT,
    class_name TEXT,
    code_hash TEXT NOT NULL,
    documented_at TIMESTAMP NOT NULL,
    snippet_path TEXT NOT NULL,
    git_commit TEXT
);

CREATE INDEX IF NOT EXISTS idx_code_hash ON documented_snippets(code_hash);
CREATE INDEX IF NOT EXISTS idx_source ON documented_snippets(source_repo, source_file);
CREATE INDEX IF NOT EXISTS idx_function ON documented_snippets(source_file, function_name);
"""


class StateManager:
    """
    Manages persistent state in SQLite
    This is the daemon's memory - tracks what has been documented
    """
    def __init__(self, db_path: Path) -> None:
        """
        Initialize state manager with database path
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents = True, exist_ok = True)
        self._init_db()

    def _init_db(self) -> None:
        """
        Initialize database schema
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """
        Get a database connection with row factory
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def hash_code(source: str) -> str:
        """
        Generate SHA256 hash of source code for deduplication
        """
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def is_documented(self, snippet: CodeSnippet) -> bool:
        """
        Check if this exact code has already been documented
        """
        code_hash = self.hash_code(snippet.source)
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM documented_snippets WHERE code_hash = ? LIMIT 1",
                (code_hash,
                 ),
            )
            return cursor.fetchone() is not None

    def get_existing_doc(self, snippet: CodeSnippet) -> DocumentedSnippet | None:
        """
        Get existing documentation record for a function/class if it exists
        Returns None if never documented
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM documented_snippets
                WHERE source_file = ? AND function_name = ? AND class_name IS ?
                ORDER BY documented_at DESC LIMIT 1
                """,
                (
                    str(snippet.file_path),
                    snippet.function_name,
                    snippet.class_name
                ),
            )
            row = cursor.fetchone()
            if row:
                return DocumentedSnippet(
                    id = row["id"],
                    source_repo = row["source_repo"],
                    source_file = row["source_file"],
                    function_name = row["function_name"],
                    class_name = row["class_name"],
                    code_hash = row["code_hash"],
                    documented_at = datetime.fromisoformat(row["documented_at"]),
                    snippet_path = row["snippet_path"],
                    git_commit = row["git_commit"],
                )
            return None

    def should_document(
        self,
        snippet: CodeSnippet,
        redocument_after_days: int = 30,
    ) -> bool:
        """
        Determine if a snippet should be documented
        Returns True if:
        - Never documented before
        - Code has changed AND enough time has passed
        """
        code_hash = self.hash_code(snippet.source)
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM documented_snippets WHERE code_hash = ? LIMIT 1",
                (code_hash,
                 ),
            )
            if cursor.fetchone():
                return False

            cursor = conn.execute(
                """
                SELECT documented_at FROM documented_snippets
                WHERE source_file = ? AND function_name = ? AND class_name IS ?
                ORDER BY documented_at DESC LIMIT 1
                """,
                (
                    str(snippet.file_path),
                    snippet.function_name,
                    snippet.class_name
                ),
            )
            row = cursor.fetchone()
            if row:
                last_doc = datetime.fromisoformat(row["documented_at"])
                if datetime.now() - last_doc < timedelta(
                        days = redocument_after_days):
                    return False

            return True

    def record_documentation(
        self,
        snippet: CodeSnippet,
        snippet_path: str,
        git_commit: str | None = None,
    ) -> DocumentedSnippet:
        """
        Record that a snippet has been documented
        """
        doc_id = str(uuid.uuid4())
        code_hash = self.hash_code(snippet.source)
        now = datetime.now()

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO documented_snippets
                (id, source_repo, source_file, function_name, class_name,
                 code_hash, documented_at, snippet_path, git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    snippet.repo,
                    str(snippet.file_path),
                    snippet.function_name,
                    snippet.class_name,
                    code_hash,
                    now.isoformat(),
                    snippet_path,
                    git_commit,
                ),
            )
            conn.commit()

        return DocumentedSnippet(
            id = doc_id,
            source_repo = snippet.repo,
            source_file = str(snippet.file_path),
            function_name = snippet.function_name,
            class_name = snippet.class_name,
            code_hash = code_hash,
            documented_at = now,
            snippet_path = snippet_path,
            git_commit = git_commit,
        )

    def get_stats(self) -> dict:
        """
        Get statistics about documented snippets
        """
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documented_snippets"
                                 ).fetchone()[0]
            by_repo = dict(
                conn.execute(
                    "SELECT source_repo, COUNT(*) FROM documented_snippets GROUP BY source_repo"
                ).fetchall()
            )
            recent = conn.execute(
                """
                SELECT COUNT(*) FROM documented_snippets
                WHERE documented_at > datetime('now', '-7 days')
                """
            ).fetchone()[0]

        return {
            "total_documented": total,
            "by_repo": by_repo,
            "last_7_days": recent,
        }
