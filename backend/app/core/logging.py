import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=get_settings().log_level, stream=sys.stdout)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
