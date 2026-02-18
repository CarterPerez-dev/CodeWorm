"""
ⒸAngelaMos | 2026
logging.py
"""
import logging
import sys

import orjson
import structlog
from rich.console import Console


console = Console()


def configure_logging(
    json_mode: bool | None = None,
    debug: bool = False,
    redis_url: str = "",
) -> None:
    """
    Configure structlog for the daemon
    Auto-detects JSON mode based on TTY if not specified
    """
    if json_mode is None:
        json_mode = not sys.stderr.isatty()

    log_level = logging.DEBUG if debug else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt = "iso",
                                         utc = True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if redis_url:
        from codeworm.core.events import init_publisher, redis_log_processor

        init_publisher(redis_url)
        shared_processors.append(redis_log_processor)

    if json_mode:
        processors = [
            *shared_processors,
            structlog.processors.JSONRenderer(serializer = _json_serializer),
        ]
    else:
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors = True),
        ]

    structlog.configure(
        processors = processors,
        wrapper_class = structlog.make_filtering_bound_logger(log_level),
        context_class = dict,
        logger_factory = structlog.PrintLoggerFactory(),
        cache_logger_on_first_use = True,
    )


def _json_serializer(obj: dict, **kwargs) -> str:
    """
    Serialize log entries to JSON using orjson for speed
    """
    return orjson.dumps(obj, default = str).decode("utf-8")


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """
    Get a bound logger instance
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(component = name)
    return logger
