"""
Advanced Logging Configuration for Fuel Analytics Backend
Provides structured logging with rotation, error tracking, and diagnostics
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

# Create logs directory
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


class CrashLogger:
    """Logs crashes and critical errors for post-mortem analysis"""

    def __init__(self, log_dir: Path = LOGS_DIR):
        self.log_dir = log_dir
        self.crash_log = log_dir / "crashes.log"

    def log_crash(self, error: Exception, context: str = ""):
        """Log a crash with full traceback"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.crash_log, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CRASH: {timestamp}\n")
            f.write(f"Context: {context}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Error: {type(error).__name__}: {str(error)}\n")

            import traceback

            f.write(f"\nTraceback:\n")
            f.write(traceback.format_exc())
            f.write(f"\n{'='*80}\n\n")


def setup_logging(
    name: str = "fuel_analytics",
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Setup comprehensive logging with rotation and error tracking

    Args:
        name: Logger name
        level: Logging level
        log_to_file: Enable file logging
        log_to_console: Enable console logging

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Formatter for files
    file_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Formatter for console
    console_formatter = ColoredFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    if log_to_file:
        # Main rotating log file (10MB max, keep 5 backups)
        main_handler = RotatingFileHandler(
            LOGS_DIR / f"{name}.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        main_handler.setLevel(level)
        main_handler.setFormatter(file_formatter)
        logger.addHandler(main_handler)

        # Error log file (only ERROR and CRITICAL)
        error_handler = RotatingFileHandler(
            LOGS_DIR / f"{name}_errors.log",
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        logger.addHandler(error_handler)

        # Daily rotating log
        daily_handler = TimedRotatingFileHandler(
            LOGS_DIR / f"{name}_daily.log",
            when="midnight",
            interval=1,
            backupCount=7,  # Keep 7 days
            encoding="utf-8",
        )
        daily_handler.setLevel(level)
        daily_handler.setFormatter(file_formatter)
        logger.addHandler(daily_handler)

    if log_to_console:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


def log_system_info(logger: logging.Logger):
    """Log system information for diagnostics"""
    import platform

    import psutil

    logger.info("═" * 60)
    logger.info("SYSTEM INFORMATION")
    logger.info("═" * 60)
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Python: {platform.python_version()}")
    logger.info(f"CPU Cores: {psutil.cpu_count()}")
    logger.info(f"RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    logger.info(f"Disk: {psutil.disk_usage('/').free / (1024**3):.1f} GB free")
    logger.info("═" * 60)


# Global crash logger instance
crash_logger = CrashLogger()


# Convenience function
def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get or create a logger with standard configuration"""
    return setup_logging(name, level)


if __name__ == "__main__":
    # Test logging
    test_logger = get_logger("test", logging.DEBUG)
    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    test_logger.error("Error message")
    test_logger.critical("Critical message")

    # Test crash logger
    try:
        raise ValueError("Test crash")
    except Exception as e:
        crash_logger.log_crash(e, "Testing crash logger")

    print(f"\n✅ Logs written to: {LOGS_DIR}")
