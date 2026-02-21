"""
Configuration settings for OTT Movie Tracker
Secure configuration with no hardcoded secrets
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        print("ERROR: SECRET_KEY environment variable is not set!", file=sys.stderr)
        print("Please set it in your .env file or environment variables", file=sys.stderr)
        sys.exit(1)
    
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
    
    # Admin credentials - MUST be set in environment
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
    if not ADMIN_PASSWORD and FLASK_ENV == 'production':
        print("ERROR: ADMIN_PASSWORD must be set in production!", file=sys.stderr)
        sys.exit(1)
    
    # Database
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    # Use PostgreSQL if DATABASE_URL is set, else fallback to SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'ott_tracker.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20
    }
    # Celery + Redis
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # TMDB API
    TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
    if not TMDB_API_KEY:
        print("ERROR: TMDB_API_KEY is not set! Application cannot start.", file=sys.stderr)
        sys.exit(1)
    
    TMDB_BASE_URL = 'https://api.themoviedb.org/3'
    TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p/w500'
    
    # Pagination
    MOVIES_PER_PAGE = int(os.getenv('MOVIES_PER_PAGE', '20'))
    
    # Scheduler
    DAILY_FETCH_TIME = os.getenv('DAILY_FETCH_TIME', '09:00')
    WEEKLY_REFRESH_DAY = os.getenv('WEEKLY_REFRESH_DAY', 'Sunday')
    WEEKLY_REFRESH_TIME = os.getenv('WEEKLY_REFRESH_TIME', '09:00')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/ott_radar.log')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    # Allow insecure admin password in development only
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'dev_password_123')


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # Production MUST have secure passwords set
    if not os.getenv('ADMIN_PASSWORD') or len(os.getenv('ADMIN_PASSWORD', '')) < 8:
        print("ERROR: ADMIN_PASSWORD must be at least 8 characters in production!", file=sys.stderr)
        sys.exit(1)


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}