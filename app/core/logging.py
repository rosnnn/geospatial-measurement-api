import logging
import sys


def setup_logging() -> logging.Logger:
    """Configure structured logging for the application."""
    log_format = "%(asctime)s | %(levelname)-7s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logger = logging.getLogger("geospatial_api")
    logger.setLevel(logging.INFO)
    return logger


logger = setup_logging()
