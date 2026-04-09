import logging
import json
from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter that ensures consistent field ordering and types."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to the JSON log record."""
        super().add_fields(log_record, record, message_dict)
        # Ensure timestamp is ISO format
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname


def configure_json_logging(logger_name: str, level=logging.INFO) -> logging.Logger:
    """Configure a logger with JSON output.

    Args:
        logger_name: Logger name (typically __name__)
        level: Log level (default INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove any existing handlers to avoid duplication
    logger.handlers = []

    handler = logging.StreamHandler()
    formatter = CustomJsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
