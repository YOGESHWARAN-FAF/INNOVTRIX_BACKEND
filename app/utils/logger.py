import logging
from logging.handlers import RotatingFileHandler
import os
import sys

def setup_logger(name="app_logger", log_file="app.log", level=logging.INFO):
    """Function to setup a logger with rotating file handler and console handler"""
    
    # Create logs directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    formatter = logging.Formatter(
        "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s"
    )

    handler = RotatingFileHandler(
        f"logs/{log_file}", maxBytes=10000000, backupCount=5
    )
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.addHandler(handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()
