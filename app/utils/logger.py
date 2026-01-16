"""Structured logging configuration."""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.stdlib import LoggerFactory


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = None,
    log_dir: str = "logs",
) -> None:
    """
    Configure structured logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
        log_file: Optional log file name (if None, logs to stdout)
        log_dir: Directory for log files (default: "logs")
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to prevent duplicate log messages
    # This is necessary because logging handlers can accumulate across multiple
    # calls to configure_logging() (e.g., during testing or module reloading).
    # Without clearing, logs would be written multiple times to the same handlers.
    root_logger.handlers = []
    
    if log_file:
        # File-based logging with rotation
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        file_path = log_path / log_file
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,  # Keep 10 backup files
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)
        
        # Also log to stdout in development
        if os.getenv("ENVIRONMENT", "development") == "development":
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_handler.setFormatter(logging.Formatter("%(message)s"))
            root_logger.addHandler(console_handler)
    else:
        # Console-only logging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> Any:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

