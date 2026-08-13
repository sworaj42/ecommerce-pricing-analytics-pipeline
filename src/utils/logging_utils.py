"""Consistent logging setup shared by the pipeline's CLI scripts."""

import logging


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a module-level logger with a single, consistently formatted handler."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
