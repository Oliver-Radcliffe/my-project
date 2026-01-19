# Simple Logger for Pico Beacon
# Provides debug output with configurable levels

import time


class LogLevel:
    """Log level constants."""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    NONE = 99


class Logger:
    """Simple logger with level filtering."""

    LEVEL_NAMES = {
        LogLevel.DEBUG: "DEBUG",
        LogLevel.INFO: "INFO",
        LogLevel.WARNING: "WARN",
        LogLevel.ERROR: "ERROR"
    }

    def __init__(self, name="Beacon", level=LogLevel.INFO, enable_timestamp=True):
        """Initialize logger.

        Args:
            name: Logger name (appears in output)
            level: Minimum log level to output
            enable_timestamp: Include timestamp in output
        """
        self.name = name
        self.level = level
        self.enable_timestamp = enable_timestamp

    def _log(self, level, message):
        """Internal log method."""
        if level < self.level:
            return

        level_name = self.LEVEL_NAMES.get(level, "?")

        if self.enable_timestamp:
            # Get timestamp (milliseconds since boot)
            ts = time.ticks_ms()
            secs = ts // 1000
            ms = ts % 1000
            print(f"[{secs:6d}.{ms:03d}] [{level_name:5s}] {self.name}: {message}")
        else:
            print(f"[{level_name:5s}] {self.name}: {message}")

    def debug(self, message):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message)

    def info(self, message):
        """Log info message."""
        self._log(LogLevel.INFO, message)

    def warning(self, message):
        """Log warning message."""
        self._log(LogLevel.WARNING, message)

    def warn(self, message):
        """Alias for warning()."""
        self.warning(message)

    def error(self, message):
        """Log error message."""
        self._log(LogLevel.ERROR, message)

    def set_level(self, level):
        """Set minimum log level.

        Args:
            level: LogLevel constant
        """
        self.level = level

    def hex_dump(self, data, message="Data"):
        """Log a hex dump of data (at DEBUG level).

        Args:
            data: bytes or bytearray to dump
            message: Description of data
        """
        if self.level > LogLevel.DEBUG:
            return

        hex_str = ' '.join(f'{b:02X}' for b in data)
        self._log(LogLevel.DEBUG, f"{message} ({len(data)} bytes): {hex_str}")


# Global default logger instance
_default_logger = Logger()


def get_logger(name=None):
    """Get a logger instance.

    Args:
        name: Logger name (or None for default)

    Returns:
        Logger instance
    """
    if name:
        return Logger(name)
    return _default_logger


def set_global_level(level):
    """Set log level for default logger.

    Args:
        level: LogLevel constant
    """
    _default_logger.set_level(level)
