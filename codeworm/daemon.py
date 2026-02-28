"""
ⒸAngelaMos | 2026
daemon.py
"""
from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from codeworm.analysis import (
    CodeAnalyzer,
    ParserManager,
    TargetRouter,
)
from codeworm.analysis.targets import DocumentationTarget, select_doc_type
from codeworm.core import (
    CodeWormSettings,
    StateManager,
    configure_logging,
    get_logger,
    load_settings,
)
from codeworm.core.events import get_publisher
from codeworm.core.notifier import CodeWormNotifier
from codeworm.git import DevLogRepository
from codeworm.llm import (
    DocumentationGenerator,
    OllamaClient,
    OllamaError,
)
from codeworm.models import DocType
from codeworm.scheduler import CodeWormScheduler

if TYPE_CHECKING:
    from codeworm.analysis import AnalysisCandidate


@dataclass
class CycleStats:
    """
    Tracks cycle statistics for monitoring and backoff logic
    """
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    skipped_cycles: int = 0
    consecutive_failures: int = 0
    consecutive_ollama_failures: int = 0
    consecutive_push_failures: int = 0
    last_success: datetime | None = None
    last_failure: datetime | None = None
    last_failure_reason: str = ""
    repos_exhausted: set = field(default_factory = set)

    @property
    def success_rate(self) -> float:
        if self.total_cycles == 0:
            return 0.0
        return self.successful_cycles / self.total_cycles * 100

    def record_success(self) -> None:
        self.total_cycles += 1
        self.successful_cycles += 1
        self.consecutive_failures = 0
        self.consecutive_ollama_failures = 0
        self.last_success = datetime.now()
        self.repos_exhausted.clear()

    def record_failure(self, reason: str) -> None:
        self.total_cycles += 1
        self.failed_cycles += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()
        self.last_failure_reason = reason

    def record_ollama_failure(self) -> None:
        self.consecutive_ollama_failures += 1

    def record_ollama_recovery(self) -> None:
        self.consecutive_ollama_failures = 0

    def record_skip(self, reason: str) -> None:
        self.total_cycles += 1
        self.skipped_cycles += 1
        self.last_failure_reason = reason

    def record_repo_exhausted(self, repo_name: str) -> None:
        self.repos_exhausted.add(repo_name)

    def get_backoff_seconds(self) -> int:
        if self.consecutive_failures <= 1:
            return 0
        return min(300, 30 * (2**(self.consecutive_failures - 1)))

    def get_ollama_wait_seconds(self) -> int:
        if self.consecutive_ollama_failures <= 1:
            return 10
        return min(300, 10 * (2**(self.consecutive_ollama_failures - 1)))

    def to_dict(self) -> dict:
        return {
            "total_cycles":
            self.total_cycles,
            "successful_cycles":
            self.successful_cycles,
            "failed_cycles":
            self.failed_cycles,
            "skipped_cycles":
            self.skipped_cycles,
            "success_rate":
            round(self.success_rate,
                  1),
            "consecutive_failures":
            self.consecutive_failures,
            "last_success":
            self.last_success.isoformat() if self.last_success else None,
        }


class CodeWormDaemon:
    """
    Main daemon orchestrator - designed for bulletproof 24/7 operation
    Coordinates analysis, LLM generation, git commits, and scheduling
    Self-heals when Ollama goes down, backs off on failures, never dies
    """
    OLLAMA_WAIT_MAX = 300
    OLLAMA_CHECK_INTERVAL = 10

    def __init__(self, settings: CodeWormSettings, dry_run: bool = False) -> None:
        """
        Initialize daemon with all components
        """
        self.settings = settings
        self.dry_run = dry_run
        self.logger = get_logger("daemon")
        self.running = False

        self.stats = CycleStats()
        self._start_time = datetime.now()
        self.state = StateManager(settings.db_path)
        self.devlog = DevLogRepository(
            repo_path = settings.devlog.repo_path,
            remote = settings.devlog.remote,
            branch = settings.devlog.branch,
        )
        self.analyzer = CodeAnalyzer(
            repos = settings.repos,
            settings = settings.analyzer,
        )
        self.target_router = TargetRouter(
            analyzer = self.analyzer,
            scanner = self.analyzer.scanner,
        )
        self.scheduler = CodeWormScheduler(settings.schedule)
        self._llm_client: OllamaClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._dead_mans_task: asyncio.Task | None = None

        self.notifier: CodeWormNotifier | None = None
        if settings.telegram.enabled and settings.telegram.bot_token:
            self.notifier = CodeWormNotifier(settings.telegram)

        self._setup_signals()

    def _setup_signals(self) -> None:
        """
        Set up signal handlers for graceful shutdown
        """
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGHUP, self._handle_reload)

    def _handle_shutdown(self, signum: int, _frame) -> None:
        """
        Handle shutdown signals gracefully
        """
        sig_name = signal.Signals(signum).name
        self.logger.info("shutdown_signal_received", signal = sig_name)
        self.running = False
        self.scheduler.stop(wait = False)

    def _handle_reload(self, _signum: int, _frame) -> None:
        """
        Handle SIGHUP for config reload
        """
        self.logger.info("reload_signal_received")

    async def _init_llm(self) -> OllamaClient:
        """
        Initialize the LLM client (does not prewarm here)
        """
        if self._llm_client is None:
            self._llm_client = OllamaClient(self.settings.ollama)
        return self._llm_client

    async def _wait_for_ollama(self) -> bool:
        """
        Wait for Ollama to become available with exponential backoff
        Returns True when available, False if daemon is shutting down
        """
        client = await self._init_llm()

        while self.running:
            if await client.health_check():
                if self.stats.consecutive_ollama_failures > 0:
                    self.logger.info(
                        "ollama_recovered",
                        after_failures = self.stats.consecutive_ollama_failures,
                    )
                self.stats.record_ollama_recovery()
                return True

            wait_seconds = self.stats.get_ollama_wait_seconds()
            self.stats.record_ollama_failure()

            self.logger.warning(
                "ollama_unavailable_waiting",
                url = self.settings.ollama.base_url,
                retry_in_seconds = wait_seconds,
                consecutive_failures = self.stats.consecutive_ollama_failures,
            )

            if (self.notifier and self.stats.consecutive_ollama_failures
                    == self.settings.telegram.alert_after_failures):
                await self.notifier.send_alert(
                    f"Ollama unavailable — {self.stats.consecutive_ollama_failures} consecutive failures",
                    details =
                    f"Retrying every {wait_seconds}s. Daemon is paused until Ollama recovers.",
                )

            for _ in range(wait_seconds):
                if not self.running:
                    return False
                await asyncio.sleep(1)

        return False

    async def _ensure_ollama_ready(self) -> bool:
        """
        Ensure Ollama is ready, waiting if necessary
        Returns True when ready, False if should abort
        """
        client = await self._init_llm()
        if await client.health_check():
            return True
        return await self._wait_for_ollama()

    async def _cleanup(self) -> None:
        """
        Cleanup resources on shutdown
        """
        if self._llm_client:
            await self._llm_client.close()
            self._llm_client = None
        if self.notifier:
            await self.notifier.close()

    def run(self) -> None:
        """
        Main daemon run loop
        """
        self.running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._async_run())
        finally:
            self._loop.run_until_complete(self._cleanup())
            self._loop.close()

    async def _async_run(self) -> None:
        """
        Async main run loop
        """
        mode = "[DRY RUN] " if self.dry_run else ""
        self.logger.info(
            "daemon_starting",
            mode = mode.strip() or "normal",
            repos = len(self.settings.repos),
            devlog = str(self.settings.devlog.repo_path),
            debug = self.settings.debug,
        )

        ParserManager.initialize()

        if not self.dry_run:
            self.devlog.ensure_directory_structure()

        db_stats = self.state.get_stats()
        self.logger.info(
            "state_loaded",
            total_documented = db_stats["total_documented"],
            last_7_days = db_stats["last_7_days"],
        )

        self.logger.info(
            "waiting_for_ollama",
            url = self.settings.ollama.base_url
        )
        if not await self._wait_for_ollama():
            self.logger.info("shutdown_during_ollama_wait")
            return

        client = await self._init_llm()
        await client.prewarm()
        self.logger.info("llm_initialized", model = self.settings.ollama.model)

        self.scheduler.set_task_callback(self._on_scheduled_task)
        self.scheduler.start()

        next_run = self.scheduler.get_next_run_time()
        if next_run:
            self.logger.info("next_scheduled_run", time = next_run.isoformat())
            self._emit_event("next_cycle", {"time": next_run.isoformat()})

        self._dead_mans_task = asyncio.create_task(self._dead_mans_switch())

        while self.running:
            await asyncio.sleep(1)

        self.logger.info(
            "daemon_stopped",
            stats = self.stats.to_dict(),
        )

    def _tail_log(self, lines: int = 20) -> str:
        log_path = Path("/tmp/codeworm.log")
        try:
            text = log_path.read_text(encoding = "utf-8", errors = "replace")
            readable = [line for line in text.splitlines() if not line.startswith("{")]
            tail = readable[-lines :]
            return "\n".join(tail)
        except Exception:
            return "(log unavailable)"

    async def _dead_mans_switch(self) -> None:
        check_interval = 300
        alert_threshold = 2700
        alerted = False

        await asyncio.sleep(check_interval)

        while self.running:
            reference = self.stats.last_success or self._start_time
            age = (datetime.now() - reference).total_seconds()
            if age > alert_threshold and not alerted:
                self.logger.warning(
                    "dead_mans_switch_triggered",
                    minutes_since_last_commit = round(age / 60,
                                                      1),
                )
                if self.notifier:
                    log_tail = self._tail_log(20)
                    await self.notifier.send_alert(
                        f"No commits in {int(age / 60)} minutes",
                        details = f"<pre>{log_tail}</pre>",
                    )
                alerted = True
            elif age <= alert_threshold and alerted:
                alerted = False

            await asyncio.sleep(check_interval)

    def _on_scheduled_task(self) -> None:
        """
        Callback executed by scheduler for each documentation task
        """
        if self._loop:
            future = asyncio.run_coroutine_threadsafe(
                self._execute_documentation_cycle(),
                self._loop,
            )
            try:
                future.result(timeout = 1800)
            except Exception as e:
                self.logger.exception("scheduled_task_error", error = str(e))
                self.stats.record_failure(f"task_error: {e}")
                if self.notifier and self.stats.consecutive_failures >= self.settings.telegram.alert_after_failures:
                    self.notifier.send_error_sync(e, "scheduler")

            next_run = self.scheduler.get_next_run_time()
            if next_run:
                self.logger.info(
                    "next_scheduled_run",
                    time = next_run.isoformat()
                )
                self._emit_event("next_cycle", {"time": next_run.isoformat()})

    async def _execute_documentation_cycle(self) -> None:
        """
        Execute one full documentation cycle
        Selects a random doc type, finds a target, generates, commits
        """
        backoff = self.stats.get_backoff_seconds()
        if backoff > 0:
            self.logger.info(
                "backing_off",
                seconds = backoff,
                consecutive_failures = self.stats.consecutive_failures,
            )
            await asyncio.sleep(backoff)

        self.logger.info(
            "cycle_starting",
            cycle_num = self.stats.total_cycles + 1
        )
        self._emit_event(
            "cycle_starting",
            {"cycle_num": self.stats.total_cycles + 1}
        )

        if not await self._ensure_ollama_ready():
            return

        try:
            target = await self._find_documentation_target()
            if not target:
                self.stats.record_skip("no_candidates")
                self.logger.warning(
                    "cycle_skipped_no_candidates",
                    repos_exhausted = list(self.stats.repos_exhausted),
                )
                if self.notifier and self.stats.skipped_cycles >= self.settings.telegram.alert_after_failures:
                    await self.notifier.send_alert(
                        f"{self.stats.skipped_cycles} cycles skipped — no candidates found",
                        details =
                        f"Repos exhausted: {list(self.stats.repos_exhausted)}",
                    )
                self.stats.repos_exhausted.clear()
                next_run = self.scheduler.get_next_run_time()
                if next_run:
                    self._emit_event("next_cycle", {"time": next_run.isoformat()})
                return

            self._emit_event(
                "analyzing",
                {
                    "target": target.display_name,
                    "doc_type": target.doc_type.value,
                    "repo": target.snippet.repo,
                }
            )

            success = await self._document_target(target)
            if success:
                self.stats.record_success()
                self._log_cycle_stats()
                self._emit_stats()
            else:
                self.stats.record_failure("documentation_failed")
                if (self.notifier and self.stats.consecutive_failures
                        >= self.settings.telegram.alert_after_failures):
                    await self.notifier.send_alert(
                        f"{self.stats.consecutive_failures} consecutive documentation failures",
                        last_error = self.stats.last_failure_reason,
                    )

            next_run = self.scheduler.get_next_run_time()
            if next_run:
                self._emit_event("next_cycle", {"time": next_run.isoformat()})
        finally:
            self.analyzer.close_repos()

    async def _find_documentation_target(self) -> DocumentationTarget | None:
        """
        Find a documentation target using weighted doc type selection
        Tries the selected type first, then falls back to others
        """
        type_weights = self.settings.documentation.type_weights
        redoc_days = self.settings.documentation.redocument_after_days
        enabled_repos = [r for r in self.settings.repos if r.enabled]

        selected_type = select_doc_type(type_weights)
        tried_types: set[DocType] = set()

        all_types = list(type_weights.keys())

        for type_str in [selected_type.value, *all_types]:
            try:
                doc_type = DocType(type_str)
            except ValueError:
                continue

            if doc_type in tried_types:
                continue
            if doc_type in (DocType.WEEKLY_SUMMARY, DocType.MONTHLY_SUMMARY):
                continue
            tried_types.add(doc_type)

            for repo in enabled_repos:
                if repo.name in self.stats.repos_exhausted:
                    continue

                targets = self.target_router.find_targets(
                    doc_type = doc_type,
                    repo = repo,
                    limit = 30,
                )

                for target in targets:
                    if self.state.should_document(
                            target.snippet,
                            doc_type = doc_type,
                            redocument_after_days = redoc_days,
                    ):
                        self.logger.debug(
                            "target_found",
                            doc_type = doc_type.value,
                            target = target.display_name,
                            repo = repo.name,
                        )
                        return target

        return None

    async def _find_documentable_candidate(self) -> AnalysisCandidate | None:
        """
        Legacy method - find a function candidate to document
        """
        enabled_repos = [r for r in self.settings.repos if r.enabled]

        for repo in enabled_repos:
            if repo.name in self.stats.repos_exhausted:
                continue

            candidates = self.analyzer.find_candidates(repo = repo, limit = 50)
            for candidate in candidates:
                if self.state.should_document(candidate.snippet):
                    return candidate

            self.stats.record_repo_exhausted(repo.name)
            self.logger.debug(
                "repo_exhausted",
                repo = repo.name,
                checked = len(candidates),
            )

        return None

    async def _document_target(self, target: DocumentationTarget) -> bool:
        """
        Generate documentation and commit for a DocumentationTarget
        """
        self.logger.info(
            "documenting",
            target = target.display_name,
            doc_type = target.doc_type.value,
            repo = target.snippet.repo,
            score = round(target.score,
                          2),
            dry_run = self.dry_run,
        )

        try:
            self._emit_event(
                "generating",
                {
                    "target": target.display_name,
                    "doc_type": target.doc_type.value,
                    "repo": target.snippet.repo,
                    "language": target.snippet.language.value,
                }
            )

            client = await self._init_llm()
            generator = DocumentationGenerator(client, self.settings.prompts)
            doc = await generator.generate_from_target(target)

            if self.dry_run:
                self.logger.info(
                    "dry_run_complete",
                    target = target.display_name,
                    doc_type = target.doc_type.value,
                    tokens = doc.tokens_used,
                    time_ms = doc.generation_time_ms,
                    would_commit = doc.commit_message,
                )
                return True

            markdown_content = doc.to_markdown_from_target(target)

            file_path = self.devlog.write_snippet(
                content = markdown_content,
                filename = doc.snippet_filename,
                language = target.snippet.language.value,
                doc_type = target.doc_type,
            )

            result = self.devlog.commit(
                message = doc.commit_message,
                files = [file_path],
            )

            self.state.record_documentation(
                snippet = target.snippet,
                snippet_path = str(file_path.relative_to(self.devlog.repo_path)),
                git_commit = result.commit_hash,
                doc_type = target.doc_type,
            )

            self.logger.info(
                "documentation_committed",
                target = target.display_name,
                doc_type = target.doc_type.value,
                commit = result.commit_hash,
                tokens = doc.tokens_used,
                time_ms = doc.generation_time_ms,
            )

            self._emit_event(
                "documentation_committed",
                {
                    "target": target.display_name,
                    "doc_type": target.doc_type.value,
                    "commit": result.commit_hash,
                    "tokens": doc.tokens_used,
                    "time_ms": doc.generation_time_ms,
                    "repo": target.snippet.repo,
                    "language": target.snippet.language.value,
                    "commit_message": doc.commit_message,
                }
            )

            if self.settings.devlog.remote:
                try:
                    self.devlog.push()
                    self.logger.info("push_successful")
                    self.stats.consecutive_push_failures = 0
                except Exception as e:
                    self.stats.consecutive_push_failures += 1
                    error_str = str(e)
                    self.logger.warning("push_failed", error = error_str)
                    if self.notifier and self.settings.telegram.alert_on_push_failure:
                        if "GH013" in error_str or "secret" in error_str.lower():
                            await self.notifier.send_alert(
                                "Push blocked — secret scanning violation",
                                last_error = error_str[: 300],
                                details = "Manual intervention required.",
                            )
                        elif self.stats.consecutive_push_failures >= self.settings.telegram.alert_after_failures:
                            await self.notifier.send_error(e, "git.push")

            return True

        except OllamaError as e:
            self.logger.error(
                "llm_error",
                target = target.display_name,
                error = str(e),
            )
            return False

        except Exception as e:
            self.logger.exception(
                "documentation_failed",
                target = target.display_name,
                error = str(e),
            )
            return False

    async def _document_candidate(self, candidate: AnalysisCandidate) -> bool:
        """
        Legacy method - generate documentation and commit for an AnalysisCandidate
        """
        self.logger.info(
            "documenting",
            function = candidate.snippet.display_name,
            repo = candidate.snippet.repo,
            score = round(candidate.score,
                          2),
            dry_run = self.dry_run,
        )

        try:
            client = await self._init_llm()
            generator = DocumentationGenerator(client, self.settings.prompts)
            doc = await generator.generate(candidate)

            if self.dry_run:
                self.logger.info(
                    "dry_run_complete",
                    function = candidate.snippet.display_name,
                    tokens = doc.tokens_used,
                    time_ms = doc.generation_time_ms,
                    would_commit = doc.commit_message,
                )
                return True

            markdown_content = doc.to_markdown(candidate)

            file_path = self.devlog.write_snippet(
                content = markdown_content,
                filename = doc.snippet_filename,
                language = candidate.snippet.language.value,
            )

            result = self.devlog.commit(
                message = doc.commit_message,
                files = [file_path],
            )

            self.state.record_documentation(
                snippet = candidate.snippet,
                snippet_path = str(file_path.relative_to(self.devlog.repo_path)),
                git_commit = result.commit_hash,
            )

            self.logger.info(
                "documentation_committed",
                function = candidate.snippet.display_name,
                commit = result.commit_hash,
                tokens = doc.tokens_used,
                time_ms = doc.generation_time_ms,
            )

            if self.settings.devlog.remote:
                try:
                    self.devlog.push()
                    self.logger.info("push_successful")
                except Exception as e:
                    self.logger.warning("push_failed", error = str(e))

            return True

        except OllamaError as e:
            self.logger.error(
                "llm_error",
                function = candidate.snippet.display_name,
                error = str(e),
            )
            return False

        except Exception as e:
            self.logger.exception(
                "documentation_failed",
                function = candidate.snippet.display_name,
                error = str(e),
            )
            return False

    def _log_cycle_stats(self) -> None:
        if self.stats.successful_cycles % 10 == 0:
            self.logger.info(
                "cycle_stats",
                **self.stats.to_dict(),
            )

    def _emit_event(self, event_type: str, data: dict | None = None) -> None:
        publisher = get_publisher()
        if publisher is not None:
            publisher.publish_event(event_type, data)

    def _emit_stats(self) -> None:
        publisher = get_publisher()
        if publisher is not None:
            db_stats = self.state.get_stats()
            publisher.publish_stats({
                **self.stats.to_dict(),
                **db_stats,
            })

    async def run_once(self, dry_run: bool = False) -> bool:
        """
        Run a single documentation cycle manually
        Returns True if documentation was generated
        """
        self.dry_run = dry_run
        ParserManager.initialize()

        if not dry_run:
            self.devlog.ensure_directory_structure()

        if not await self._ensure_ollama_ready():
            self.logger.error("ollama_not_available")
            return False

        client = await self._init_llm()
        await client.prewarm()

        candidate = await self._find_documentable_candidate()
        if not candidate:
            self.logger.info("no_documentable_candidates_found")
            return False

        return await self._document_candidate(candidate)


def main() -> int:
    """
    Entry point for the daemon
    """
    settings = load_settings(
        devlog = {"repo_path": Path("/tmp/devlog")},
    )
    configure_logging(debug = settings.debug)

    daemon = CodeWormDaemon(settings)
    daemon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
