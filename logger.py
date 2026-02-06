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
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file specified)
    if log_file:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Rotating file handler (max 10MB, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
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
