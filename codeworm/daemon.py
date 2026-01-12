"""
ⒸAngelaMos | 2026
daemon.py
"""
from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from codeworm.analysis import CodeAnalyzer, ParserManager
from codeworm.core import (
    CodeWormSettings,
    StateManager,
    configure_logging,
    get_logger,
    load_settings,
)
from codeworm.git import DevLogRepository
from codeworm.llm import DocumentationGenerator, OllamaClient, OllamaError
from codeworm.scheduler import CodeWormScheduler

if TYPE_CHECKING:
    from codeworm.analysis import AnalysisCandidate


class CodeWormDaemon:
    """
    Main daemon orchestrator
    Coordinates analysis, LLM generation, git commits, and scheduling
    """

    def __init__(self, settings: CodeWormSettings) -> None:
        """
        Initialize daemon with all components
        """
        self.settings = settings
        self.logger = get_logger("daemon")
        self.running = False

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

    def _handle_shutdown(self, signum: int, frame) -> None:
        """
        Handle shutdown signals gracefully
        """
        sig_name = signal.Signals(signum).name
        self.logger.info("shutdown_signal_received", signal=sig_name)
        self.running = False
        self.scheduler.stop(wait=False)

    def _handle_reload(self, signum: int, frame) -> None:
        """
        Handle SIGHUP for config reload
        """
        self.logger.info("reload_signal_received")

    async def _init_llm(self) -> OllamaClient:
        """
        Initialize and prewarm the LLM client
        """
        if self._llm_client is None:
            self._llm_client = OllamaClient(self.settings.ollama)

            if await self._llm_client.health_check():
                await self._llm_client.prewarm()
                self.logger.info("llm_initialized", model=self.settings.ollama.model)
            else:
                self.logger.warning("llm_not_available", url=self.settings.ollama.base_url)

        return self._llm_client

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
        self.logger.info(
            "daemon_starting",
            repos=len(self.settings.repos),
            devlog=str(self.settings.devlog.repo_path),
            debug=self.settings.debug,
        )

        ParserManager.initialize()
        self.devlog.ensure_directory_structure()

        stats = self.state.get_stats()
        self.logger.info(
            "state_loaded",
            total_documented=stats["total_documented"],
            last_7_days=stats["last_7_days"],
        )

        await self._init_llm()

        self.scheduler.set_task_callback(self._on_scheduled_task)
        self.scheduler.start()

        next_run = self.scheduler.get_next_run_time()
        if next_run:
            self.logger.info("next_scheduled_run", time=next_run.isoformat())

        while self.running:
            await asyncio.sleep(1)

        self.logger.info("daemon_stopped")

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
                future.result(timeout=300)
            except Exception as e:
                self.logger.exception("scheduled_task_error", error=str(e))

    async def _execute_documentation_cycle(self) -> None:
        """
        Execute one full documentation cycle
        """
        self.logger.info("cycle_starting")

        candidates = self.analyzer.select_for_documentation(
            min_score=self.settings.analyzer.min_complexity * 10,
            count=1,
        )

        if not candidates:
            self.logger.info("no_candidates_found")
            return

        candidate = candidates[0]

        if not self.state.should_document(candidate.snippet):
            self.logger.info(
                "skipping_already_documented",
                function=candidate.snippet.display_name,
            )
            return

        await self._document_candidate(candidate)

    async def _document_candidate(self, candidate: AnalysisCandidate) -> None:
        """
        Generate documentation and commit for a candidate
        """
        self.logger.info(
            "documenting",
            function=candidate.snippet.display_name,
            repo=candidate.snippet.repo,
            score=round(candidate.score, 2),
        )

        try:
            client = await self._init_llm()
            generator = DocumentationGenerator(client)
            doc = await generator.generate(candidate)

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
                except Exception as e:
                    self.logger.warning("push_failed", error=str(e))

        except OllamaError as e:
            self.logger.error(
                "llm_error",
                function=candidate.snippet.display_name,
                error=str(e),
            )

        except Exception as e:
            self.logger.exception(
                "documentation_failed",
                function=candidate.snippet.display_name,
                error=str(e),
            )

    async def run_once(self) -> bool:
        """
        Run a single documentation cycle manually
        Returns True if documentation was generated
        """
        ParserManager.initialize()
        self.devlog.ensure_directory_structure()
        await self._init_llm()

        candidates = self.analyzer.select_for_documentation(count=1)
        if not candidates:
            return False

        candidate = candidates[0]
        if not self.state.should_document(candidate.snippet):
            return False

        await self._document_candidate(candidate)
        return True


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
