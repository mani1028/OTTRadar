import os
import time
import requests
from datetime import datetime, timezone, date, timedelta
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
from flask_cors import CORS
from functools import wraps, lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from difflib import SequenceMatcher
from sqlalchemy import text
from config import Config
from models import db, Movie, UserSubmission, Watchlist, WatchlistAlert, OTTSnapshot, UserWatchlistEmail
from discovery import MovieFilter, OTTDiscovery, UnifiedSearch
from logger import app_logger
import secrets
import re

# Initialize Flask app
load_dotenv()
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize database
db.init_app(app)

# Ensure database tables exist
with app.app_context():
    db.create_all()

# Add Jinja filter for movie slug conversion (SEO-friendly URLs)
@app.template_filter('movie_slug')
def movie_slug_filter(title):
    """Convert movie title to URL-friendly slug"""
    return slugify_movie_title(title)


# Add Jinja filter for date formatting
@app.template_filter('strftime')
def strftime_filter(date_obj, format_string):
    """Format datetime object using strftime"""
    if not date_obj:
        return ''
    try:
        if isinstance(date_obj, str):
            # Try to parse ISO format date string
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        elif isinstance(date_obj, date) and not isinstance(date_obj, datetime):
            # Convert date to datetime
            date_obj = datetime.combine(date_obj, datetime.min.time())
        return date_obj.strftime(format_string)
    except Exception as e:
        app_logger.warning(f"Date formatting error: {e}")
        return str(date_obj)


# ===== CACHING UTILITIES =====
class Cache:
    """Simple in-memory cache for homepage and API responses"""
    def __init__(self):
        self.data = {}
        self.timestamps = {}
        self.ttl = 60  # 60 seconds default
    
    def set(self, key, value, ttl=60):
        self.data[key] = value
        self.timestamps[key] = time.time()
        self.ttl = ttl
    
    def get(self, key):
        if key in self.data:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.data[key]
            else:
                del self.data[key]
                del self.timestamps[key]
        return None
    
    def clear(self):
        self.data.clear()
        self.timestamps.clear()

cache = Cache()


# ===== HELPER FUNCTIONS =====
def is_released(movie):
    """Check if movie has been released"""
    if not movie.release_date:
        return False
    try:
        release_date = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        return release_date <= date.today()
    except:
        return False


def sort_by_ott_release(movies):
    """Sort movies by most recently released to any OTT platform"""
    def get_latest_ott_date(movie):
        try:
            import json
            ott_data = json.loads(movie.ott_platforms) if movie.ott_platforms else {}
            dates = []
            for platform, info in ott_data.items():
                if isinstance(info, dict) and 'release_date' in info:
                    try:
                        d = datetime.strptime(info['release_date'], '%Y-%m-%d').date()
                        dates.append(d)
                    except:
                        pass
            return max(dates) if dates else date.min
        except:
            return date.min
    
    return sorted(movies, key=get_latest_ott_date, reverse=True)





def slugify_movie_title(title):
    """Convert movie title to URL-friendly slug (SEO-optimized)"""
    # Convert to lowercase, remove special chars, replace spaces with hyphens
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def get_movie_status(movie):
    """Determine movie status for display"""
    if not movie.release_date:
        return 'upcoming'
    
    try:
        release_date = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        today = date.today()
        
        if release_date > today:
            return 'upcoming'
        elif release_date <= today:
            return 'available'
    except:
        pass
    
    return 'available'


# ===== OPTIMIZED API ENDPOINTS =====
@app.route('/api/search', methods=['GET'])
def api_search():
    """Fast search API with pagination - minimal fields"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    
    if not query or len(query) < 2:
        return jsonify({'results': [], 'total': 0, 'page': page})
    
    # Use unified search from discovery.py
    search_results = UnifiedSearch.search_movies(query)
    
    # Paginate
    total = len(search_results)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = search_results[start:end]
    
    return jsonify({
        'results': [m.to_dict_minimal() for m in paginated],
        'total': total,
        'page': page,
        'per_page': per_page,
        'has_more': end < total
    })


@app.route('/api/movies/<category>', methods=['GET'])
def api_movies_category(category):
    """Fast API for paginated movie lists - minimal fields"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    
    movies = []
    
    if category == 'trending':
        movies = Movie.query.filter_by(is_active=True) \
            .filter(Movie.rating >= 6.5) \
            .order_by(Movie.popularity.desc()).all()
    elif category == 'new-on-ott':
        movies = OTTDiscovery.new_on_ott(days=7)
        movies = [m for m in movies if is_released(m)]
    elif category == 'free':
        movies = OTTDiscovery.free_movies()
    elif category == 'hidden-gems':
        movies = OTTDiscovery.hidden_gems(limit=500)
    elif category == 'upcoming':
        upcoming_str = date.today().strftime('%Y-%m-%d')
        movies = Movie.query.filter_by(is_active=True) \
            .filter(Movie.release_date > upcoming_str) \
            .order_by(Movie.release_date.asc()).all()
    
    # Paginate
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    return jsonify({
        'results': [m.to_dict_minimal() for m in paginated],
        'total': total,
        'page': page,
        'per_page': per_page,
        'has_more': end < total
    })


@app.route('/')
def index():
    query = request.args.get('q', '').strip()

    if query:
        # Use unified search from discovery.py
        search_results = UnifiedSearch.search_movies(query)
        return render_template('index.html', search_results=search_results, query=query, total_results=len(search_results))

    # Try to get cached homepage data (15-minute TTL)
    cached_homepage = cache.get('homepage_data')
    if cached_homepage:
        app_logger.debug('Serving homepage from cache')
        return render_template('index.html', 
                             featured=cached_homepage['featured'],
                             continue_watching=cached_homepage['continue_watching'],
                             popular_on_radar=cached_homepage['popular_on_radar'],
                             new_on_ott=cached_homepage['new_on_ott'],
                             hidden_gems=cached_homepage['hidden_gems'],
                             upcoming_hits=cached_homepage['upcoming_hits'],
                             # Legacy keys for desktop
                             today_on_ott=cached_homepage.get('today_on_ott', []),
                             trending=cached_homepage.get('trending', []),
                             new_releases=cached_homepage.get('new_releases', []),
                             upcoming=cached_homepage.get('upcoming', []),
                             query='')
    
    # Cache miss - get fresh data from database
    app_logger.debug('Cache miss - fetching fresh homepage data')
    homepage = OTTDiscovery.homepage_data()
    
    # Cache for 15 minutes (900 seconds)
    cache.set('homepage_data', homepage, ttl=900)
    
    return render_template('index.html', 
                         featured=homepage['featured'],
                         continue_watching=homepage['continue_watching'],
                         popular_on_radar=homepage['popular_on_radar'],
                         new_on_ott=homepage['new_on_ott'],
                         hidden_gems=homepage['hidden_gems'],
                         upcoming_hits=homepage['upcoming_hits'],
                         # Legacy keys for desktop
                         today_on_ott=homepage.get('today_on_ott', []),
                         trending=homepage.get('trending', []),
                         new_releases=homepage.get('new_releases', []),
                         upcoming=homepage.get('upcoming', []),
                         query='')


@app.route('/discover')
def discover():
    return redirect(url_for('filter_movies'))


@app.route('/search')
def search_page():
    """Dedicated search page with trending and genre filters"""
    # Fetch trending movies to show before user types
    trending_searches = OTTDiscovery.trending_now(limit=6)
    
    # Static popular genres for quick access
    genres = ['Action', 'Comedy', 'Drama', 'Thriller', 'Sci-Fi', 'Romance', 'Horror', 'Animation']
    
    return render_template('search.html', 
                         trending=trending_searches, 
                         genres=genres)


@app.route('/suggest', methods=['GET', 'POST'])
def suggest():
    if request.method == 'POST':
        submission_type = request.form.get('type', 'movie').strip()
        
        if submission_type == 'movie':
            # Movie Request
            movie_name = request.form.get('movie_name', '').strip()
            language = request.form.get('language', '').strip()
            platform = request.form.get('platform', '').strip()
            notes = request.form.get('notes', '').strip()
            
            if movie_name:
                new_submission = UserSubmission(
                    movie_title=movie_name,
                    language=language,
                    platform_name=platform,
                    comment=notes,
                    submission_type='movie'
                )
                db.session.add(new_submission)
                db.session.commit()
                flash('Movie request submitted successfully!', 'success')
                return redirect(url_for('suggest'))
            flash('Movie name is required.', 'error')
        
        elif submission_type == 'feature':
            # Feature Suggestion
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            category = request.form.get('category', 'feature').strip()
            
            if title and description:
                new_submission = UserSubmission(
                    movie_title=title,  # Using movie_title field for suggestion title
                    comment=description,
                    submission_type='feature',
                    category=category
                )
                db.session.add(new_submission)
                db.session.commit()
                flash('Feature suggestion submitted successfully!', 'success')
                return redirect(url_for('suggest'))
            flash('Title and description are required.', 'error')

    return render_template('suggest.html')


@app.route('/about')
def about():
    return render_template('about.html')


# ===== DISCOVERY & SMART FILTERING =====
@app.route('/free-movies')
def free_movies():
    """All free movies"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    movies = OTTDiscovery.free_movies()
    
    # Paginate
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    return render_template('free_movies.html', 
                         movies=paginated, 
                         page=page, 
                         total=total,
                         per_page=per_page)


@app.route('/new-on-ott')
def new_on_ott():
    """Recently added to any OTT platform"""
    days = request.args.get('days', 7, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    movies = OTTDiscovery.new_on_ott(days=days)
    
    # Paginate
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    return render_template('new_on_ott.html',
                         movies=paginated,
                         page=page,
                         total=total,
                         per_page=per_page,
                         days=days)


@app.route('/hidden-gems')
def hidden_gems():
    """High-rated but low-popularity movies"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    movies = OTTDiscovery.hidden_gems(limit=500)
    
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    return render_template('hidden_gems.html',
                         movies=paginated,
                         page=page,
                         total=total,
                         per_page=per_page)


@app.route('/trending')
def trending():
    """Trending movies (recent high-rated popular content)"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    movies = OTTDiscovery.trending_now(limit=500)
    
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    return render_template('trending.html',
                         movies=paginated,
                         page=page,
                         total=total,
                         per_page=per_page)


@app.route('/filter')
def filter_movies():
    """Smart filtering with multiple criteria"""
    # Get filter params
    language = request.args.getlist('lang')  # Multiple select
    platforms = request.args.getlist('platform')
    min_rating = request.args.get('min_rating', 0, type=float)
    max_rating = request.args.get('max_rating', 10, type=float)
    genre = request.args.get('genre', '')
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    free_only = request.args.get('free_only', 'off') == 'on'
    dubbed_only = request.args.get('dubbed', 'off') == 'on'
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    filters = MovieFilter()
    
    if language:
        filters.by_language(language)
    if genre:
        filters.by_genre(genre)
    if platforms:
        filters.by_platform(platforms)
    if min_rating or max_rating < 10:
        filters.by_rating(min_rating, max_rating)
    if year_from or year_to:
        filters.by_year(year_from, year_to)
    if dubbed_only:
        filters.by_dubbed(True)
    
    movies = filters.execute()
    movies = sort_by_ott_release(movies)
    
    # Optional: Show free_only
    if free_only:
        movies = [m for m in movies if any((v or {}).get('is_free') for v in (m.get_ott_platforms() or {}).values())]
    
    total = len(movies)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = movies[start:end]
    
    # Get available filter options
    all_movies = Movie.query.filter_by(is_active=True).all()
    lang_options = set(m.language for m in all_movies if m.language)
    genre_options = set()
    for m in all_movies:
        if m.genres:
            genre_options.update(g.strip() for g in m.genres.split(','))
    
    platform_options = set()
    for m in all_movies:
        ott = m.get_ott_platforms()
        platform_options.update(ott.keys())
    
    return render_template('filter_movies.html',
                         movies=paginated,
                         page=page,
                         total=total,
                         per_page=per_page,
                         applied_filters={
                             'lang': language,
                             'platform': platforms,
                             'min_rating': min_rating,
                             'max_rating': max_rating,
                             'genre': genre,
                             'year_from': year_from,
                             'year_to': year_to,
                             'free_only': free_only,
                             'dubbed_only': dubbed_only
                         },
                         lang_options=sorted(lang_options),
                         genre_options=sorted(genre_options),
                         platform_options=sorted(platform_options))


@app.route('/ott-dashboard')
def ott_dashboard():
    """OTT platform statistics and insights"""
    stats = OTTDiscovery.platform_stats()
    
    # Get daily snapshot if available
    today = datetime.utcnow().date()
    snapshot = OTTSnapshot.query.filter_by(date=today).first()
    
    free_movies = OTTDiscovery.free_movies(limit=None)
    
    return render_template('ott_dashboard.html',
                         stats=stats,
                         snapshot=snapshot,
                         free_movie_count=len(free_movies),
                         total_movies=Movie.query.filter_by(is_active=True).count())


@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    """User watchlist management (session-based for anonymous users)"""
    user_id = session.get('user_id')
    if not user_id:
        from uuid import uuid4
        user_id = f"anon_{uuid4().hex[:12]}"
        session['user_id'] = user_id
    
    if request.method == 'POST':
        movie_id = request.form.get('movie_id', type=int)
        tmdb_id = request.form.get('tmdb_id', type=int)
        action = request.form.get('action', 'add')  # 'add', 'remove', 'watched', 'watchlist', 'interested'
        
        try:
            if action == 'add':
                existing = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
                if not existing:
                    movie = Movie.query.get(movie_id)
                    if movie:
                        platforms_list = list(movie.get_ott_platforms().keys())
                        watchlist_item = Watchlist(
                            user_id=user_id,
                            movie_id=movie_id,
                            platforms_available=platforms_list
                        )
                        db.session.add(watchlist_item)
                        db.session.commit()
                        flash('Added to watchlist!', 'success')
            elif action == 'remove':
                item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
                if item:
                    db.session.delete(item)
                    db.session.commit()
                    flash('Removed from watchlist', 'success')
            elif action == 'watched':
                item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
                if item:
                    item.status = 'watched'
                    from datetime import timezone
                    item.watched_at = datetime.now(timezone.utc)
                    db.session.commit()
                    flash('Marked as watched!', 'success')
            elif action == 'watchlist':
                # Revert back to watchlist status
                item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
                if item:
                    item.status = 'watchlist'
                    item.watched_at = None
                    db.session.commit()
                    flash('Moved back to watchlist', 'success')
            elif action == 'interested':
                item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
                if item:
                    item.status = 'interested'
                    db.session.commit()
                    flash('Marked as interested', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            db.session.rollback()
        
        # Redirect back to remove POST data
        if tmdb_id:
            return redirect(url_for('movie_detail', tmdb_id=tmdb_id))
        return redirect(url_for('watchlist', status=request.args.get('status', '')))
    
    # Get user's watchlist with optional status filter
    status_filter = request.args.get('status', '').strip()
    query = Watchlist.query.filter_by(user_id=user_id)
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    user_watchlist = query.order_by(Watchlist.added_at.desc()).all()
    
    # Get counts for each status
    counts = {
        'watchlist': Watchlist.query.filter_by(user_id=user_id, status='watchlist').count(),
        'watched': Watchlist.query.filter_by(user_id=user_id, status='watched').count(),
        'interested': Watchlist.query.filter_by(user_id=user_id, status='interested').count(),
    }
    total = sum(counts.values())
    
    return render_template('watchlist.html',
                         movies=user_watchlist,
                         user_id=user_id,
                         status=status_filter,
                         counts=counts,
                         total=total)



# ===== ADMIN AUTHENTICATION =====
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please login to access admin panel', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        # Use environment variable for admin password (no fallback for security)
        admin_password = os.getenv('ADMIN_PASSWORD')
        
        if not admin_password:
            app_logger.error('ADMIN_PASSWORD not set in environment variables')
            flash('Server configuration error. Contact administrator.', 'error')
            return render_template('admin_login.html')
        
        if password == admin_password:
            session['admin_logged_in'] = True
            app_logger.info('Admin login successful')
            flash('Welcome to Admin Panel', 'success')
            return redirect(url_for('admin'))
        else:
            app_logger.warning(f'Failed admin login attempt')
            flash('Invalid password', 'error')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin():
    # Database stats
    total_movies = Movie.query.filter_by(is_active=True).count()
    total_submissions = UserSubmission.query.count()
    pending_submissions = UserSubmission.query.filter_by(status='pending').count()
    
    # Recent submissions - paginated to 20 for performance
    page = request.args.get('page', 1, type=int)
    per_page = 20
    submissions = UserSubmission.query.order_by(UserSubmission.created_at.desc()).limit(per_page).all()
    
    return render_template('admin.html', 
                         total_movies=total_movies,
                         total_submissions=total_submissions,
                         pending_submissions=pending_submissions,
                         submissions=submissions)


@app.route('/admin/movie/search', methods=['GET', 'POST'])
@login_required
def admin_movie_search():
    movies = []
    search_query = ''
    if request.method == 'POST':
        search_query = request.form.get('search_query', '').strip()
        
        if search_query:
            # Use UnifiedSearch for consistent search experience across app
            # This ensures improvements to search algorithm benefit both frontend and admin panel
            search_results = UnifiedSearch.search_movies(search_query)
            movies = search_results[:20] if search_results else []
            
            if movies:
                app_logger.info(f'Admin search: Found {len(movies)} results for "{search_query}"')
            else:
                # Fallback: Direct TMDB ID search if UnifiedSearch doesn't find anything
                if search_query.isdigit():
                    exact_match = Movie.query.filter_by(tmdb_id=int(search_query)).first()
                    if exact_match:
                        movies = [exact_match]
                        app_logger.info(f'Admin search: Found exact TMDB ID match for {search_query}')
                
                if not movies:
                    flash(f'No movies found matching: {search_query}', 'error')
    
    return render_template('admin_edit_movie.html', movies=movies, search_query=search_query)


@app.route('/admin/movie/edit/<int:tmdb_id>', methods=['POST'])
@login_required
def admin_movie_edit(tmdb_id):
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first_or_404()
    
    # Update all editable movie fields
    movie.title = request.form.get('title', movie.title)
    movie.overview = request.form.get('overview', movie.overview)
    movie.poster = request.form.get('poster', movie.poster)
    movie.backdrop = request.form.get('backdrop', movie.backdrop)
    movie.trailer = request.form.get('trailer', movie.trailer)
    movie.release_date = request.form.get('release_date', movie.release_date)
    movie.runtime = int(request.form.get('runtime', movie.runtime))
    movie.genres = request.form.get('genres', movie.genres)
    movie.cast = request.form.get('cast', movie.cast)
    movie.certification = request.form.get('certification', movie.certification)
    movie.language = request.form.get('language', movie.language)
    movie.ott_platforms = request.form.get('ott_platforms', movie.ott_platforms)
    movie.rating = float(request.form.get('rating', movie.rating))
    movie.popularity = float(request.form.get('popularity', movie.popularity))
    movie.is_active = request.form.get('is_active') == 'on'
    movie.is_dubbed = request.form.get('is_dubbed') == 'on'
    movie.last_updated = datetime.now(timezone.utc)
    
    db.session.commit()
    flash(f'Updated: {movie.title}', 'success')
    return redirect(url_for('admin_movie_search'))


@app.route('/admin/submission/<int:id>/update', methods=['POST'])
@login_required
def admin_submission_update(id):
    submission = UserSubmission.query.get_or_404(id)
    action = request.form.get('action')
    
    if action == 'approve':
        submission.status = 'added'
        flash(f'Approved: {submission.movie_title}', 'success')
    elif action == 'reject':
        submission.status = 'rejected'
        flash(f'Rejected: {submission.movie_title}', 'error')
    
    db.session.commit()
    return redirect(url_for('admin'))


# ===== MOVIE DETAIL PAGE =====
@app.route('/movie/<movie_identifier>')
def movie_detail(movie_identifier):
    """Movie detail page supporting both name-based and ID-based routes"""
    movie = None
    
    # Try to parse as integer TMDB ID first
    if movie_identifier.isdigit():
        movie = Movie.query.filter_by(tmdb_id=int(movie_identifier)).first_or_404()
    else:
        # Handle URL-friendly name slug
        # Search for movies with matching slugified title
        all_movies = Movie.query.filter_by(is_active=True).all()
        target_slug = movie_identifier.lower()
        
        for m in all_movies:
            if slugify_movie_title(m.title) == target_slug:
                movie = m
                break
        
        if not movie:
            # Fallback: search by partial title match
            similar = Movie.query.filter(
                Movie.is_active == True,
                Movie.title.ilike(f'%{movie_identifier.replace("-", " ")}%')
            ).first()
            movie = similar if similar else None
        
        if not movie:
            return redirect(url_for('index'))
    
    # Parse OTT platforms JSON with proper error handling
    try:
        import json
        ott_data = json.loads(movie.ott_platforms) if movie.ott_platforms else {}
    except json.JSONDecodeError as e:
        app_logger.error(f'JSON parsing error for movie {movie.tmdb_id} ({movie.title}): {e}')
        app_logger.error(f'Malformed data: {movie.ott_platforms[:100]}...')
        ott_data = {}
    except Exception as e:
        app_logger.error(f'Unexpected error parsing OTT platforms for movie {movie.tmdb_id}: {e}')
        ott_data = {}
    
    # Get movie status
    status = get_movie_status(movie)
    
    # Get similar movies based on shared genres (optimized database query)
    similar_movies = []
    if movie.genres:
        # Get primary genre (first genre in the list)
        primary_genre = movie.genres.split(',')[0].strip()
        
        # Use database query instead of Python loop for better performance
        similar_movies = Movie.query.filter(
            Movie.id != movie.id,
            Movie.is_active == True,
            Movie.genres.like(f'%{primary_genre}%')
        ).order_by(Movie.popularity.desc()).limit(6).all()
    
    return render_template('movie.html', movie=movie, ott_data=ott_data, status=status, similar_movies=similar_movies)


# ===== PERSON / ACTOR DETAIL ROUTE =====
@app.route('/person/<actor_name>')
def person_details(actor_name):
    """
    Display actor/person detail page with their movies on OTT RADAR
    Uses TMDB CDN for profile images (zero-download architecture)
    Limits to 20 movies to prevent mobile browser crashes
    """
    try:
        # Search for movies where this actor appears in cast
        # Cast is stored as comma-separated names or JSON with tmdb_id
        actor_name_clean = actor_name.replace('-', ' ').title()
        
        # Search using unfiltered query - will match partial names too (LIMIT 20 for mobile perf)
        movies_with_actor = Movie.query.filter(
            Movie.is_active == True,
            Movie.cast.ilike(f'%{actor_name_clean}%')
        ).order_by(Movie.popularity.desc()).limit(20).all()
        
        if not movies_with_actor:
            # Try without word boundaries for more lenient search
            actor_parts = actor_name_clean.split()
            if actor_parts:
                first_name = actor_parts[0]
                movies_with_actor = Movie.query.filter(
                    Movie.is_active == True,
                    Movie.cast.ilike(f'%{first_name}%')
                ).order_by(Movie.popularity.desc()).limit(20).all()
        
        # Prepare person data with TMDB enrichment
        person_data = {
            'name': actor_name_clean,
            'display_name': actor_name.replace('-', ' '),
            'movie_count': len(movies_with_actor),
            'visibility': f'{len(movies_with_actor)} movies on OTT RADAR',
            'bio': None,
            'birth_date': None,
            'profile_path': None,
            'popularity': 0,
            'known_for_department': None
        }
        
        # Try to enrich with TMDB person data
        try:
            import requests
            # First, search for the person to get their ID
            tmdb_search_url = f"https://api.themoviedb.org/3/search/person"
            tmdb_params = {
                'api_key': 'e99307154fabc578ecbacc3a4c5832b8',
                'query': actor_name_clean
            }
            response = requests.get(tmdb_search_url, params=tmdb_params, timeout=3)
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    person_id = results[0].get('id')
                    person_data['profile_path'] = results[0].get('profile_path')
                    person_data['popularity'] = results[0].get('popularity', 0)
                    person_data['known_for_department'] = results[0].get('known_for_department')
                    
                    # Get detailed person info including biography
                    person_detail_url = f"https://api.themoviedb.org/3/person/{person_id}"
                    person_detail_params = {'api_key': 'e99307154fabc578ecbacc3a4c5832b8'}
                    detail_response = requests.get(person_detail_url, params=person_detail_params, timeout=3)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        person_data['bio'] = detail_data.get('biography', '')
                        person_data['birth_date'] = detail_data.get('birthday')
        except Exception as tmdb_err:
            app_logger.debug(f'TMDB enrichment failed for {actor_name_clean}: {tmdb_err}')
        
        app_logger.info(f'Person detail page viewed: {actor_name_clean} ({len(movies_with_actor)} movies)')
        
        return render_template(
            'person.html', 
            person=person_data, 
            movies=movies_with_actor  # Show up to 20 movies (limited for performance)
        )
    
    except Exception as e:
        app_logger.error(f'Error loading person details for {actor_name}: {e}')
        flash('Could not load actor profile', 'warning')
        return redirect(url_for('index'))


@app.route('/admin/submission/<int:id>/delete', methods=['POST'])
@login_required
def admin_submission_delete(id):
    submission = UserSubmission.query.get_or_404(id)
    title = submission.movie_title
    db.session.delete(submission)
    db.session.commit()
    flash(f'Deleted submission: {title}', 'success')
    return redirect(url_for('admin'))


# ===== HEALTH CHECK ENDPOINT =====
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring and load balancers"""
    try:
        # Test database connection with a simple query
        Movie.query.limit(1).all()
        
        # Get basic stats
        movie_count = Movie.query.filter_by(is_active=True).count()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': 'connected',
            'movie_count': movie_count,
            'cache_size': len(cache.data)
        }), 200
    except Exception as e:
        app_logger.error(f'Health check failed: {e}')
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }), 503


# ===== WATCHLIST EMAIL LINKING ENDPOINTS =====
# Prevent anonymous user data loss by linking watchlists to email accounts

@app.route('/watchlist/link-email', methods=['POST'])
def watchlist_link_email():
    """Link anonymous watchlist to email address"""
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        user_id = session.get('user_id')
        
        if not email or not user_id:
            app_logger.warning(f'Invalid email link request: {user_id}')
            return jsonify({'error': 'Email and session required'}), 400
        
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            app_logger.warning(f'Invalid email format: {email}')
            return jsonify({'error': 'Invalid email format'}), 400
        
        existing = UserWatchlistEmail.query.filter_by(email=email).first()
        if existing and existing.is_verified:
            app_logger.info(f'Email already linked: {email}')
            return jsonify({'error': 'Email already linked'}), 400
        
        verification_token = secrets.token_urlsafe(32)
        link_record = UserWatchlistEmail.query.filter_by(anonymous_user_id=user_id).first()
        
        if not link_record:
            link_record = UserWatchlistEmail(
                anonymous_user_id=user_id,
                email=email,
                verification_token=verification_token
            )
            db.session.add(link_record)
        else:
            link_record.email = email
            link_record.verification_token = verification_token
            link_record.is_verified = False
        
        db.session.commit()
        app_logger.info(f'Email link initiated: {user_id} -> {email}')
        
        return jsonify({
            'success': True,
            'message': 'Verification required',
            'email': email,
            'token': verification_token
        }), 200
    except Exception as e:
        app_logger.error(f'Error linking email: {e}')
        db.session.rollback()
        return jsonify({'error': 'Server error'}), 500


@app.route('/watchlist/verify-email/<token>', methods=['GET'])
def watchlist_verify_email(token):
    """Verify email and merge watchlist"""
    try:
        link_record = UserWatchlistEmail.query.filter_by(verification_token=token).first()
        if not link_record:
            app_logger.warning(f'Invalid token: {token[:10]}...')
            flash('Invalid verification link', 'error')
            return redirect(url_for('index'))
        
        if link_record.is_verified:
            flash('Email already verified', 'info')
            return redirect(url_for('watchlist'))
        
        link_record.is_verified = True
        link_record.linked_at = datetime.utcnow()
        
        anonymous_user_id = link_record.anonymous_user_id
        email = link_record.email
        
        watchlist_items = Watchlist.query.filter_by(user_id=anonymous_user_id).all()
        for item in watchlist_items:
            item.email = email
            item.linked_at = datetime.utcnow()
        
        db.session.commit()
        app_logger.info(f'Email verified: {anonymous_user_id} -> {email} ({len(watchlist_items)} items)')
        
        flash(f'Email verified! {len(watchlist_items)} watchlist items saved.', 'success')
        return redirect(url_for('watchlist'))
        
    except Exception as e:
        app_logger.error(f'Error verifying email: {e}')
        db.session.rollback()
        flash('Error verifying email', 'error')
        return redirect(url_for('index'))


@app.route('/watchlist/email-status', methods=['GET'])
def watchlist_email_status():
    """Check if watchlist is linked to email"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'linked': False}), 200
        
        link_record = UserWatchlistEmail.query.filter_by(anonymous_user_id=user_id).first()
        
        if not link_record:
            return jsonify({'linked': False, 'user_id': user_id}), 200
        
        return jsonify({
            'linked': link_record.is_verified,
            'email': link_record.email if link_record.is_verified else None,
            'verified': link_record.is_verified
        }), 200
    except Exception as e:
        app_logger.error(f'Error checking status: {e}')
        return jsonify({'error': 'Server error'}), 500


@app.route('/watchlist/recover', methods=['POST'])
def watchlist_recover():
    """Recover watchlist using verified email"""
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email required'}), 400
        
        link_record = UserWatchlistEmail.query.filter_by(
            email=email,
            is_verified=True
        ).first()
        
        if not link_record:
            app_logger.warning(f'Recovery attempt: {email}')
            return jsonify({'error': 'Email not linked'}), 404
        
        session['user_id'] = link_record.anonymous_user_id
        session.permanent = True
        app_logger.info(f'Watchlist recovered: {email}')
        
        return jsonify({'success': True, 'message': 'Watchlist recovered'}), 200
    except Exception as e:
        app_logger.error(f'Error recovering watchlist: {e}')
        return jsonify({'error': 'Server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
