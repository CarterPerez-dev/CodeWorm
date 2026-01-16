"""
ⒸAngelaMos | 2026
daemon.py
"""
from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from codeworm.analysis import (
    CodeAnalyzer,
    ParserManager,
)
from codeworm.core import (
    CodeWormSettings,
    StateManager,
    configure_logging,
    get_logger,
    load_settings,
)
from codeworm.git import DevLogRepository
from codeworm.llm import (
    DocumentationGenerator,
    OllamaClient,
    OllamaError,
)
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
    last_success: datetime | None = None
    last_failure: datetime | None = None
    last_failure_reason: str = ""
    repos_exhausted: set = field(default_factory=set)

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
        return min(300, 30 * (2 ** (self.consecutive_failures - 1)))

    def get_ollama_wait_seconds(self) -> int:
        if self.consecutive_ollama_failures <= 1:
            return 10
        return min(300, 10 * (2 ** (self.consecutive_ollama_failures - 1)))

    def to_dict(self) -> dict:
        return {
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "skipped_cycles": self.skipped_cycles,
            "success_rate": round(self.success_rate, 1),
            "consecutive_failures": self.consecutive_failures,
            "last_success": self.last_success.isoformat() if self.last_success else None,
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
        self.state = StateManager(settings.db_path)
        self.devlog = DevLogRepository(
            repo_path=settings.devlog.repo_path,
            remote=settings.devlog.remote,
            branch=settings.devlog.branch,
        )
        self.analyzer = CodeAnalyzer(
            repos=settings.repos,
            settings=settings.analyzer,
        )
        self.scheduler = CodeWormScheduler(settings.schedule)
        self._llm_client: OllamaClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

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
        self.logger.info("shutdown_signal_received", signal=sig_name)
        self.running = False
        self.scheduler.stop(wait=False)

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
                        after_failures=self.stats.consecutive_ollama_failures,
                    )
                self.stats.record_ollama_recovery()
                return True

            wait_seconds = self.stats.get_ollama_wait_seconds()
            self.stats.record_ollama_failure()

            self.logger.warning(
                "ollama_unavailable_waiting",
                url=self.settings.ollama.base_url,
                retry_in_seconds=wait_seconds,
                consecutive_failures=self.stats.consecutive_ollama_failures,
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
            mode=mode.strip() or "normal",
            repos=len(self.settings.repos),
            devlog=str(self.settings.devlog.repo_path),
            debug=self.settings.debug,
        )

        ParserManager.initialize()

        if not self.dry_run:
            self.devlog.ensure_directory_structure()

        db_stats = self.state.get_stats()
        self.logger.info(
            "state_loaded",
            total_documented=db_stats["total_documented"],
            last_7_days=db_stats["last_7_days"],
        )

        self.logger.info("waiting_for_ollama", url=self.settings.ollama.base_url)
        if not await self._wait_for_ollama():
            self.logger.info("shutdown_during_ollama_wait")
            return

        client = await self._init_llm()
        await client.prewarm()
        self.logger.info("llm_initialized", model=self.settings.ollama.model)

        self.scheduler.set_task_callback(self._on_scheduled_task)
        self.scheduler.start()

        next_run = self.scheduler.get_next_run_time()
        if next_run:
            self.logger.info("next_scheduled_run", time=next_run.isoformat())

        while self.running:
            await asyncio.sleep(1)

        self.logger.info(
            "daemon_stopped",
            stats=self.stats.to_dict(),
        )

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
                future.result(timeout=900)
            except Exception as e:
                self.logger.exception("scheduled_task_error", error=str(e))
                self.stats.record_failure(f"task_error: {e}")

    async def _execute_documentation_cycle(self) -> None:
        """
        Execute one full documentation cycle
        - Waits for Ollama if unavailable
        - Tries multiple repos if one is exhausted
        - Backs off on consecutive failures
        """
        backoff = self.stats.get_backoff_seconds()
        if backoff > 0:
            self.logger.info(
                "backing_off",
                seconds=backoff,
                consecutive_failures=self.stats.consecutive_failures,
            )
            await asyncio.sleep(backoff)

        self.logger.info("cycle_starting", cycle_num=self.stats.total_cycles + 1)

        if not await self._ensure_ollama_ready():
            return

        candidate = await self._find_documentable_candidate()
        if not candidate:
            self.stats.record_skip("no_candidates")
            self.logger.warning(
                "cycle_skipped_no_candidates",
                repos_exhausted=list(self.stats.repos_exhausted),
            )
            return

        success = await self._document_candidate(candidate)
        if success:
            self.stats.record_success()
            self._log_cycle_stats()
        else:
            self.stats.record_failure("documentation_failed")

    async def _find_documentable_candidate(self) -> AnalysisCandidate | None:
        """
        Find a candidate to document, trying all repos if needed
        """
        enabled_repos = [r for r in self.settings.repos if r.enabled]

        for repo in enabled_repos:
            if repo.name in self.stats.repos_exhausted:
                continue

            candidates = self.analyzer.find_candidates(repo=repo, limit=50)
            for candidate in candidates:
                if self.state.should_document(candidate.snippet):
                    return candidate

            self.stats.record_repo_exhausted(repo.name)
            self.logger.debug(
                "repo_exhausted",
                repo=repo.name,
                checked=len(candidates),
            )

        return None

    async def _document_candidate(self, candidate: AnalysisCandidate) -> bool:
        """
        Generate documentation and commit for a candidate
        Returns True on success, False on failure
        """
        self.logger.info(
            "documenting",
            function=candidate.snippet.display_name,
            repo=candidate.snippet.repo,
            score=round(candidate.score, 2),
            dry_run=self.dry_run,
        )

        try:
            client = await self._init_llm()
            generator = DocumentationGenerator(client, self.settings.prompts)
            doc = await generator.generate(candidate)

            if self.dry_run:
                self.logger.info(
                    "dry_run_complete",
                    function=candidate.snippet.display_name,
                    tokens=doc.tokens_used,
                    time_ms=doc.generation_time_ms,
                    would_commit=doc.commit_message,
                )
                return True

            markdown_content = doc.to_markdown(candidate)

            file_path = self.devlog.write_snippet(
                content=markdown_content,
                filename=doc.snippet_filename,
                language=candidate.snippet.language.value,
            )

            result = self.devlog.commit(
                message=doc.commit_message,
                files=[file_path],
            )

            self.state.record_documentation(
                snippet=candidate.snippet,
                snippet_path=str(file_path.relative_to(self.devlog.repo_path)),
                git_commit=result.commit_hash,
            )

            self.logger.info(
                "documentation_committed",
                function=candidate.snippet.display_name,
                commit=result.commit_hash,
                tokens=doc.tokens_used,
                time_ms=doc.generation_time_ms,
            )

            if self.settings.devlog.remote:
                try:
                    self.devlog.push()
                    self.logger.info("push_successful")
                except Exception as e:
                    self.logger.warning("push_failed", error=str(e))

            return True

        except OllamaError as e:
            self.logger.error(
                "llm_error",
                function=candidate.snippet.display_name,
                error=str(e),
            )
            return False

        except Exception as e:
            self.logger.exception(
                "documentation_failed",
                function=candidate.snippet.display_name,
                error=str(e),
            )
            return False

    def _log_cycle_stats(self) -> None:
        """
        Log periodic stats
        """
        if self.stats.successful_cycles % 10 == 0:
            self.logger.info(
                "cycle_stats",
                **self.stats.to_dict(),
            )

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
        devlog={"repo_path": Path("/tmp/devlog")},
    )
    configure_logging(debug=settings.debug)

    daemon = CodeWormDaemon(settings)
    daemon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
