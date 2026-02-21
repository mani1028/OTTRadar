"""
Centralized logging configuration for OTT RADAR
Replaces scattered print() statements with structured logging
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime


def setup_logger(name='ott_radar', log_file=None, log_level='INFO'):
    """
    Configure and return a logger instance with both file and console handlers.
    
    Args:
        name: Logger name (useful for identifying different modules)
        log_file: Path to log file (creates parent directories if needed)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Create log file directory if needed
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

    # Avoid duplicate handlers
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            log_file or 'logs/ott_radar.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_script_logger(script_name):
    """
    Get a logger for background scripts with automatic log file naming.
    
    Args:
        script_name: Name of the script (e.g., 'daily_fetch', 'refresh_ott')
    
    Returns:
        logging.Logger: Configured logger for the script
    """
    log_file = f'logs/scripts/{script_name}.log'
    return setup_logger(script_name, log_file=log_file)


# Create default app logger
app_logger = setup_logger('ott_radar', log_file='logs/ott_radar.log')


# Example usage for maintainers:
if __name__ == '__main__':
    # Test logging
    logger = setup_logger('test', log_file='logs/test.log', log_level='DEBUG')
    
    logger.debug('This is a debug message')
    logger.info('Application started successfully')
    logger.warning('This is a warning')
    logger.error('An error occurred')
    logger.critical('Critical system failure')
    
    print("\nTest logs written to logs/test.log")
