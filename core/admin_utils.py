"""
Admin Control Center Utilities
Provides helper functions for the admin panel including:
- Health metrics calculation
- Script execution management
- Audit logging
- Data validation
"""

import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, session
from models import db, Movie, AuditLog, ScriptExecution, Person, UserSubmission, Watchlist
from core.logger import app_logger

# ===== SMART QUEUE SYSTEM =====
# Global lock for heavy script execution (only one heavy script at a time)
_heavy_script_lock = threading.Lock()
_heavy_script_running = False

# Script categorization
HEAVY_SCRIPTS = {
    'enrich_metadata_trailers',
    'smart_omdb_enrichment',
    'track_missing_movies',
    'discover_new_movies',
    'daily_ott_checker'
}

LIGHTWEIGHT_SCRIPTS = {
    'export_db',
    'manage_ott_links_report',
    'complete_enrichment'
}

# Script command mapping (supports args)
SCRIPT_COMMANDS = {
    'enrich_metadata_trailers': ['python', '-m', 'scripts.enrich_metadata_trailers', '--limit', '200'],
    'smart_omdb_enrichment': ['python', '-m', 'scripts.smart_omdb_enrichment', '--limit', '200'],
    'track_missing_movies': ['python', '-m', 'scripts.track_missing_movies', '--find', '100', '--save'],
    'discover_new_movies': ['python', '-m', 'scripts.discover_new_movies', '--import-from-json'],
    'daily_ott_checker': ['python', '-m', 'scripts.daily_ott_checker'],
    'export_db': ['python', '-m', 'scripts.export_db'],
    'manage_ott_links_report': ['python', '-m', 'scripts.manage_ott_links', '--report'],
    'complete_enrichment': ['python', '-m', 'scripts.complete_enrichment', '--dry-run']
}


# ===== AUDIT LOGGING =====
def log_admin_action(action_type, target_type=None, target_id=None, description=None, changes=None):
    """
    Log admin action to audit trail
    
    Args:
        action_type: Type of action (e.g., 'movie_edit', 'bulk_update', 'script_run')
        target_type: Type of entity affected (e.g., 'movie', 'person', 'submission')
        target_id: ID of affected entity
        description: Human-readable description
        changes: Dict of changes (before/after values)
    """
    try:
        admin_username = session.get('admin_username', 'admin')
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '')[:255] if request else None
        
        audit = AuditLog(
            admin_username=admin_username,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if changes:
            audit.set_changes(changes)
        
        db.session.add(audit)
        db.session.commit()
        
        app_logger.info(f"Audit: {admin_username} - {action_type} - {description}")
    except Exception as e:
        app_logger.error(f"Failed to log audit action: {e}")


# ===== HEALTH METRICS =====
def get_dashboard_metrics():
    """
    Calculate comprehensive dashboard health metrics
    
    Returns:
        dict: Contains all platform health metrics
    """
    try:
        # Basic counts
        total_movies = Movie.query.filter_by(is_active=True).count()
        inactive_movies = Movie.query.filter_by(is_active=False).count()
        total_submissions = UserSubmission.query.count()
        pending_submissions = UserSubmission.query.filter_by(status='pending').count()
        
        # Dead link detection (movies with no OTT platforms)
        dead_links = Movie.query.filter(
            Movie.is_active == True,
            db.or_(
                Movie.ott_platforms == '{}',
                Movie.ott_platforms == '',
                Movie.ott_platforms == None
            )
        ).count()
        
        # Top watchlisted movies (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        top_watchlisted = db.session.query(
            Movie.title,
            db.func.count(Watchlist.id).label('watchlist_count')
        ).join(Watchlist, Movie.id == Watchlist.movie_id)\
         .filter(Watchlist.added_at >= thirty_days_ago)\
         .group_by(Movie.id, Movie.title)\
         .order_by(db.desc('watchlist_count'))\
         .limit(5)\
         .all()
        
        # Last script execution
        last_script = ScriptExecution.query.order_by(
            ScriptExecution.started_at.desc()
        ).first()
        
        # Recent errors in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_errors = ScriptExecution.query.filter(
            ScriptExecution.status == 'failed',
            ScriptExecution.started_at >= yesterday
        ).count()
        
        # OTT platform distribution
        platform_stats = calculate_platform_stats()
        
        # Recently updated movies (last refresh activity)
        recently_updated = Movie.query.filter(
            Movie.is_active == True,
            Movie.last_updated >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        return {
            'total_movies': total_movies,
            'inactive_movies': inactive_movies,
            'total_submissions': total_submissions,
            'pending_submissions': pending_submissions,
            'dead_links': dead_links,
            'top_watchlisted': [{'title': item[0], 'count': item[1]} for item in top_watchlisted],
            'last_script': {
                'name': last_script.script_name if last_script else None,
                'status': last_script.status if last_script else None,
                'started_at': last_script.started_at.isoformat() if last_script else None,
                'duration': last_script.duration_seconds if last_script else None
            } if last_script else None,
            'recent_errors': recent_errors,
            'platform_stats': platform_stats,
            'recently_updated': recently_updated
        }
    except Exception as e:
        app_logger.error(f"Error calculating dashboard metrics: {e}")
        return {}


def calculate_platform_stats():
    """Calculate OTT platform distribution"""
    try:
        movies = Movie.query.filter_by(is_active=True).all()
        platform_counts = {}
        
        for movie in movies:
            try:
                ott_data = json.loads(movie.ott_platforms) if movie.ott_platforms else {}
                for platform in ott_data.keys():
                    platform_lower = platform.lower()
                    platform_counts[platform_lower] = platform_counts.get(platform_lower, 0) + 1
            except:
                continue
        
        # Sort by count descending
        sorted_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_platforms[:10])  # Top 10 platforms
    except Exception as e:
        app_logger.error(f"Error calculating platform stats: {e}")
        return {}


# ===== SCRIPT EXECUTION MANAGEMENT =====
def execute_script_async(script_name, admin_username):
    """
    Execute a Python script asynchronously with smart queue management
    
    Heavy scripts (enrich_existing, weekly_refresh, daily_fetch) are queued
    and run one at a time to prevent DB contention and API rate limits.
    
    Lightweight scripts (clear_cache, db_stats, etc.) run immediately.
    
    Args:
        script_name: Name of script in scripts/ folder
        admin_username: Admin who triggered the script
        
    Returns:
        tuple: (execution_id: int, queued: bool)
    """
    global _heavy_script_running
    
    is_heavy = script_name in HEAVY_SCRIPTS
    
    # Create execution record
    execution = ScriptExecution(
        script_name=script_name,
        triggered_by=admin_username,
        status='queued' if is_heavy else 'running'
    )
    db.session.add(execution)
    db.session.commit()
    
    execution_id = execution.id
    
    # Lightweight scripts run immediately
    if not is_heavy:
        thread = threading.Thread(
            target=_run_script_thread,
            args=(execution_id, script_name, False)
        )
        thread.daemon = True
        thread.start()
        return execution_id, False
    
    # Heavy scripts: check if another heavy script is running
    with _heavy_script_lock:
        if _heavy_script_running:
            app_logger.info(f"Heavy script {script_name} queued (another heavy script is running)")
            return execution_id, True  # Queued
        
        # Start heavy script execution
        _heavy_script_running = True
        thread = threading.Thread(
            target=_run_script_thread,
            args=(execution_id, script_name, True)
        )
        thread.daemon = True
        thread.start()
        return execution_id, False  # Started immediately


def _run_script_thread(execution_id, script_name, is_heavy):
    """
    Internal: Run script in thread and update execution record
    
    Args:
        execution_id: ScriptExecution ID
        script_name: Name of script
        is_heavy: Whether this is a heavy script (releases lock on completion)
    """
    global _heavy_script_running
    from app import app  # Import inside thread to get app context
    
    with app.app_context():
        execution = ScriptExecution.query.get(execution_id)
        if not execution:
            if is_heavy:
                with _heavy_script_lock:
                    _heavy_script_running = False
            return
        
        try:
            # Update status to running
            execution.status = 'running'
            db.session.commit()
            
            # Build command
            cmd = SCRIPT_COMMANDS.get(script_name)
            if not cmd:
                cmd = ['python', '-m', f'scripts.{script_name}']
            
            # Execute script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            # Update execution record
            execution.completed_at = datetime.utcnow()
            execution.duration_seconds = int(
                (execution.completed_at - execution.started_at).total_seconds()
            )
            execution.output_log = result.stdout[:10000]  # Limit to 10KB
            
            if result.returncode == 0:
                execution.status = 'success'
            else:
                execution.status = 'failed'
                execution.error_message = result.stderr[:5000]  # Limit to 5KB
            
            db.session.commit()
            
            app_logger.info(f"Script {script_name} completed with status: {execution.status}")
            
        except subprocess.TimeoutExpired:
            execution.status = 'failed'
            execution.error_message = 'Script execution timeout (>1 hour)'
            execution.completed_at = datetime.utcnow()
            db.session.commit()
            app_logger.error(f"Script {script_name} timed out")
            
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            db.session.commit()
            app_logger.error(f"Script {script_name} failed: {e}")
        
        finally:
            # Release heavy script lock if applicable
            if is_heavy:
                with _heavy_script_lock:
                    _heavy_script_running = False
                app_logger.info(f"Heavy script lock released for {script_name}")


def get_script_status(execution_id):
    """Get status of running/completed script"""
    execution = ScriptExecution.query.get(execution_id)
    if not execution:
        return None
    
    return {
        'id': execution.id,
        'script_name': execution.script_name,
        'status': execution.status,
        'started_at': execution.started_at.isoformat(),
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_seconds': execution.duration_seconds,
        'output_log': execution.output_log,
        'error_message': execution.error_message
    }


# ===== DATA VALIDATION =====
def validate_ott_json(json_string):
    """
    Validate OTT platforms JSON format
    
    Args:
        json_string: JSON string to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not json_string or json_string.strip() == '':
        return True, None  # Empty is valid
    
    try:
        data = json.loads(json_string)
        
        # Must be a dictionary
        if not isinstance(data, dict):
            return False, "OTT platforms must be a JSON object (dictionary), not a list or string"
        
        # Validate structure (each platform should have certain fields)
        for platform, info in data.items():
            if not isinstance(info, dict):
                return False, f"Platform '{platform}' must have an object value with 'url' field"
            
            if 'url' not in info:
                return False, f"Platform '{platform}' is missing required 'url' field"
        
        return True, None
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {str(e)}"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def validate_movie_data(data):
    """
    Validate movie data before saving
    
    Args:
        data: Dictionary of movie fields
        
    Returns:
        tuple: (is_valid: bool, errors: list)
    """
    errors = []
    
    # Required fields
    if not data.get('title'):
        errors.append("Title is required")
    
    if not data.get('tmdb_id'):
        errors.append("TMDB ID is required")
    
    # Validate numeric fields
    try:
        if data.get('rating'):
            rating = float(data['rating'])
            if rating < 0 or rating > 10:
                errors.append("Rating must be between 0 and 10")
    except ValueError:
        errors.append("Rating must be a valid number")
    
    try:
        if data.get('runtime'):
            runtime = int(data['runtime'])
            if runtime < 0:
                errors.append("Runtime must be a positive number")
    except ValueError:
        errors.append("Runtime must be a valid integer")
    
    # Validate OTT JSON
    if data.get('ott_platforms'):
        is_valid, error_msg = validate_ott_json(data['ott_platforms'])
        if not is_valid:
            errors.append(f"OTT Platforms: {error_msg}")
    
    # Validate URLs
    if data.get('poster') and not (data['poster'].startswith('http://') or data['poster'].startswith('https://')):
        errors.append("Poster URL must start with http:// or https://")
    
    return len(errors) == 0, errors


# ===== BROKEN IMAGE DETECTION =====
def scan_broken_images(limit=100):
    """
    Scan movie posters for broken images (404 errors)
    
    Args:
        limit: Maximum number of movies to check
        
    Returns:
        list: List of movies with broken images
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    movies = Movie.query.filter(
        Movie.is_active == True,
        Movie.poster != None,
        Movie.poster != ''
    ).limit(limit).all()
    
    broken_images = []
    
    # Setup session with retries
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=0.1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    for movie in movies:
        try:
            response = session.head(movie.poster, timeout=5, allow_redirects=True)
            if response.status_code == 404:
                broken_images.append({
                    'id': movie.id,
                    'tmdb_id': movie.tmdb_id,
                    'title': movie.title,
                    'poster': movie.poster
                })
        except Exception as e:
            app_logger.debug(f"Error checking poster for {movie.title}: {e}")
            continue
    
    return broken_images


# ===== CACHE MANAGEMENT =====
def clear_app_cache():
    """Clear application cache (homepage, API responses)"""
    from app import cache
    cache.clear()
    app_logger.info("Application cache cleared")
    return True
