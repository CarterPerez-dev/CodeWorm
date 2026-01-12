"""
ⒸAngelaMos | 2026
daemon.py
"""
import signal
import sys
from pathlib import Path

from codeworm.core import (
    CodeWormSettings,
    StateManager,
    configure_logging,
    get_logger,
    load_settings,
)


class CodeWormDaemon:
    """
    Main daemon orchestrator
    Coordinates all components: analyzer, scheduler, LLM, git
    """
    def __init__(self, settings: CodeWormSettings) -> None:
        """
        Initialize daemon with settings
        """
        self.settings = settings
        self.logger = get_logger("daemon")
        self.state = StateManager(settings.db_path)
        self.running = False
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

    def _handle_reload(self, signum: int, frame) -> None:
        """
        Handle SIGHUP for config reload
        """
        self.logger.info("reload_signal_received")

    def run(self) -> None:
        """
        Main daemon run loop
        """
        self.running = True
        self.logger.info(
            "daemon_starting",
            repos=len(self.settings.repos),
            debug=self.settings.debug,
        )

        stats = self.state.get_stats()
        self.logger.info(
            "state_loaded",
            total_documented=stats["total_documented"],
            last_7_days=stats["last_7_days"],
        )

        while self.running:
            try:
                self._run_cycle()
            except Exception as e:
                self.logger.exception("cycle_error", error=str(e))

        self.logger.info("daemon_stopped")

    def _run_cycle(self) -> None:
        """
        Run one documentation cycle
        This is a placeholder - will be implemented with scheduler
        """
        import time
        time.sleep(60)


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
