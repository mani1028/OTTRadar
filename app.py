import os
import time
import requests
import json
import secrets
import re
from datetime import datetime, timezone, date, timedelta
from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify, send_from_directory
from flask_cors import CORS
from functools import wraps, lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from difflib import SequenceMatcher
from sqlalchemy import text, and_, or_, desc, func

from config import Config
from models import (
    db, Movie, UserSubmission, Watchlist, WatchlistAlert, 
    OTTSnapshot, UserWatchlistEmail, AffiliateConfig, 
    LinkHealthCheck, PriceDrop, ScriptExecution, AuditLog, Person
)
from discovery import MovieFilter, OTTDiscovery, UnifiedSearch
from affiliate_utils import AffiliateManager, AffiliateAnalytics
from logger import app_logger
from db_init import init_database

# Initialize Flask app
load_dotenv()
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize database
db.init_app(app)

# ===== GLOBAL CONSTANTS & CONTEXT PROCESSORS =====
LANGUAGE_MAP = {
    'te': 'Telugu', 
    'ta': 'Tamil', 
    'hi': 'Hindi', 
    'en': 'English', 
    'kn': 'Kannada', 
    'ml': 'Malayalam',
    'mr': 'Marathi',
    'bn': 'Bengali',
    'gu': 'Gujarati',
    'pa': 'Punjabi'
}

@app.context_processor
def inject_globals():
    """Injects common variables into all Jinja templates automatically."""
    return {
        'language_map': LANGUAGE_MAP,
        'now': datetime.now(timezone.utc),
        'app_name': 'OTT RADAR'
    }

# ===== JINJA FILTERS =====
@app.template_filter('movie_slug')
def movie_slug_filter(title):
    """
    Jinja Filter: Converts a movie title into an SEO-friendly URL slug.
    Example: "The Raja Saab" -> "the-raja-saab"
    """
    if not title: return ""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

@app.template_filter('urlencode')
def urlencode_filter(value):
    """Jinja Filter: Safely encodes strings for use in URLs."""
    from urllib.parse import quote
    return quote(str(value), safe='')

@app.template_filter('strftime')
def strftime_filter(date_obj, format_string):
    """Jinja Filter: Formats date objects or ISO strings into readable dates."""
    if not date_obj:
        return ''
    try:
        if isinstance(date_obj, str):
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        elif isinstance(date_obj, date) and not isinstance(date_obj, datetime):
            date_obj = datetime.combine(date_obj, datetime.min.time())
        return date_obj.strftime(format_string)
    except Exception:
        return ''

def get_search_url(platform, title):
    """
    Helper: Generates a platform-specific search URL.
    Used for 'Searchable Links' when a direct OTT link is missing.
    """
    platform = platform.lower()
    from urllib.parse import quote_plus
    q = quote_plus(title)
    urls = {
        'netflix': f'https://www.netflix.com/search?q={q}',
        'prime': f'https://www.amazon.com/s?k={q}&i=instant-video',
        'primevideo': f'https://www.amazon.com/s?k={q}&i=instant-video',
        'amazon': f'https://www.amazon.com/s?k={q}&i=instant-video',
        'hotstar': f'https://www.hotstar.com/in/search?q={q}',
        'jiocinema': f'https://www.jiocinema.com/search/{q}',
        'zee5': f'https://www.zee5.com/search?q={q}',
        'sonyliv': f'https://www.sonyliv.com/search?q={q}',
        'aha': f'https://www.aha.video/search?q={q}',
        'youtube': f'https://www.youtube.com/results?search_query={q}'
    }
    return urls.get(platform, f'https://www.google.com/search?q={q}+{platform}+ott')

app.jinja_env.globals['get_search_url'] = get_search_url

# ===== CACHING UTILITIES =====
class Cache:
    """Internal caching system to reduce database load for common requests."""
    def __init__(self):
        self.data = {}
        self.timestamps = {}
        self.ttl = 900
    
    def set(self, key, value, ttl=900):
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
    """Checks if a movie's release date has passed."""
    if not movie.release_date: return False
    try:
        release_date = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        return release_date <= date.today()
    except: return False

def get_movie_status(movie):
    """Returns 'upcoming' or 'available' based on release date."""
    if not movie.release_date: return 'upcoming'
    try:
        rd = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        return 'upcoming' if rd > date.today() else 'available'
    except: return 'available'

def get_db_integrity_stats():
    """Calculates completion percentages for critical database fields."""
    fields = [
        {'key': 'overview', 'label': 'Overview', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'poster', 'label': 'Poster', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'backdrop', 'label': 'Backdrop', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'runtime', 'label': 'Runtime', 'missing': lambda c: or_(c == None, c == 0)},
        {'key': 'genres', 'label': 'Genres', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'cast', 'label': 'Cast', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'certification', 'label': 'Certification', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'youtube_trailer_id', 'label': 'Trailer ID', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'rating', 'label': 'Rating', 'missing': lambda c: or_(c == None, c == 0)},
        {'key': 'release_date', 'label': 'Release Date', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'ott_release_date', 'label': 'OTT Release Date', 'missing': lambda c: or_(c == None, c == '')},
        {'key': 'ott_platforms', 'label': 'OTT Platforms', 'missing': lambda c: or_(c == None, c == '', c == '{}')},
    ]
    total_movies = Movie.query.count()
    stats = {}
    missing_filters = []
    for field in fields:
        column = getattr(Movie, field['key'])
        missing_filter = field['missing'](column)
        missing_count = Movie.query.filter(missing_filter).count()
        stats[field['key']] = {
            'label': field['label'],
            'missing': missing_count,
            'available': max(total_movies - missing_count, 0),
            'percent': round(((total_movies - missing_count) / total_movies) * 100, 1) if total_movies > 0 else 0
        }
        missing_filters.append(missing_filter)
    return stats, total_movies, fields, missing_filters

# ===== OPTIMIZED API ENDPOINTS =====
@app.route('/api/search', methods=['GET'])
def api_search():
    """Endpoint: JSON search for autocomplete and dynamic lists."""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    
    if not query or len(query) < 2:
        return jsonify({'results': [], 'total': 0, 'page': page})
    
    search_results = UnifiedSearch.search_movies(query)
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
    """Endpoint: Fetches paginated movies by category (trending, free, etc.)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    movies = []
    
    if category == 'trending':
        movies = Movie.query.filter_by(is_active=True).filter(Movie.rating >= 6.5).order_by(Movie.popularity.desc()).all()
    elif category == 'new-on-ott':
        movies = [m for m in OTTDiscovery.new_on_ott(days=30) if is_released(m)]
    elif category == 'free':
        movies = OTTDiscovery.free_movies()
    elif category == 'hidden-gems':
        movies = OTTDiscovery.hidden_gems(limit=500)
    elif category == 'upcoming':
        upcoming_str = date.today().strftime('%Y-%m-%d')
        movies = Movie.query.filter_by(is_active=True).filter(Movie.release_date > upcoming_str).order_by(Movie.release_date.asc()).all()
    
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

# ===== CORE VIEW ROUTES =====
@app.route('/')
def index():
    """Main homepage showing featured categories or search results."""
    query = request.args.get('q', '').strip()
    if query:
        search_results = UnifiedSearch.search_movies(query)
        return render_template('index.html', search_results=search_results, query=query, total_results=len(search_results))

    cached_homepage = cache.get('homepage_data')
    if cached_homepage:
        return render_template('index.html', **cached_homepage, query='')
    
    homepage = OTTDiscovery.homepage_data()
    cache.set('homepage_data', homepage, ttl=900)
    return render_template('index.html', **homepage, query='')

@app.route('/discover')
def discover():
    """Alias for filter_movies."""
    return redirect(url_for('filter_movies'))

@app.route('/search')
def search_page():
    """Dedicated search UI with trending searches and genre filters."""
    trending_searches = OTTDiscovery.trending_now(limit=6)
    genres = ['Action', 'Comedy', 'Drama', 'Thriller', 'Sci-Fi', 'Romance', 'Horror', 'Animation']
    return render_template('search.html', trending=trending_searches, genres=genres)

@app.route('/suggest', methods=['GET', 'POST'])
def suggest():
    """Allows users to submit movie requests or feature suggestions."""
    if request.method == 'POST':
        submission_type = request.form.get('type', 'movie').strip()
        if submission_type == 'movie':
            movie_name = request.form.get('movie_name', '').strip()
            if movie_name:
                db.session.add(UserSubmission(movie_title=movie_name, submission_type='movie'))
                db.session.commit()
                flash('Movie request submitted!', 'success')
        elif submission_type == 'feature':
            title = request.form.get('title', '').strip()
            desc = request.form.get('description', '').strip()
            if title and desc:
                db.session.add(UserSubmission(movie_title=title, comment=desc, submission_type='feature'))
                db.session.commit()
                flash('Suggestion submitted!', 'success')
    return render_template('suggest.html')

@app.route('/about')
def about():
    """Standard about page."""
    return render_template('about.html')

@app.route('/sitemap.xml')
def sitemap():
    """Dynamic XML Sitemap for SEO crawlers."""
    movies = Movie.query.filter_by(is_active=True).limit(5000).all()
    sitemap_xml = render_template('sitemap.xml', movies=movies, base_url=request.host_url)
    response = app.make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')


@app.route('/hidden-gems')
def hidden_gems():
    """List view for Hidden Gems (High rating, low popularity)."""
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.hidden_gems(limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('hidden_gems.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/trending')
def trending():
    """List view for Trending movies."""
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.trending_now(limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('trending.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/new-on-ott')
def new_on_ott():
    """List view for newly released movies on OTT."""
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.new_on_ott(days=30, limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('new_on_ott.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/free-movies')
def free_movies():
    """List view for movies available for free on platforms like YouTube."""
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.free_movies(limit=None)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('free_movies.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/filter')
def filter_movies():
    """Advanced movie filter with multi-select support."""
    language = request.args.getlist('lang')
    platforms = request.args.getlist('platform')
    min_rating = request.args.get('min_rating', 0, type=float)
    genre = request.args.get('genre', '')
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    
    if q:
        movies = UnifiedSearch.search_movies(q)
    else:
        f = MovieFilter()
        if language: f.by_language(language)
        if genre: f.by_genre(genre)
        if min_rating: f.by_rating(min_rating)
        movies = f.all()
    
    total = len(movies)
    start = (page - 1) * 20
    paginated = movies[start:start+20]
    return render_template('filter_movies.html', movies=paginated, page=page, total=total, per_page=20, applied_filters={'lang': language, 'genre': genre})

@app.route('/ott-dashboard')
def ott_dashboard():
    """Visual dashboard for platform statistics and historical snapshots."""
    stats = OTTDiscovery.platform_stats()
    snapshot = OTTSnapshot.query.order_by(OTTSnapshot.date.desc()).first()
    return render_template('ott_dashboard.html', stats=stats, snapshot=snapshot, total_movies=Movie.query.count())

@app.route('/watchlist', methods=['GET', 'POST'])
def watchlist():
    """Personalized user watchlist based on session or linked email."""
    user_id = session.get('user_id')
    if not user_id:
        user_id = f"anon_{secrets.token_hex(6)}"
        session['user_id'] = user_id
    
    if request.method == 'POST':
        movie_id = request.form.get('movie_id', type=int)
        action = request.form.get('action', 'add')
        existing = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        if action == 'add' and not existing:
            db.session.add(Watchlist(user_id=user_id, movie_id=movie_id))
        elif action == 'remove' and existing:
            db.session.delete(existing)
        db.session.commit()
        return redirect(url_for('watchlist'))

    items = Watchlist.query.filter_by(user_id=user_id).all()
    return render_template('watchlist.html', movies=items, counts={})

@app.route('/movies')
def movies_only():
    """Infinite list of all movies, ordered by popularity."""
    page = request.args.get('page', 1, type=int)
    pagination = Movie.query.filter_by(is_active=True).order_by(Movie.popularity.desc()).paginate(page=page, per_page=50)
    return render_template('movies.html', movies=pagination.items, pagination=pagination)

@app.route('/series')
def tv_series_list():
    """Grouped view of all TV series in the database."""
    page = request.args.get('page', 1, type=int)
    series_query = db.session.query(
        Movie.series_name, db.func.count(Movie.id).label('total_episodes'),
        db.func.max(Movie.poster).label('poster'), db.func.max(Movie.rating).label('rating')
    ).filter(Movie.media_type == 'tv').group_by(Movie.series_name).order_by(db.func.max(Movie.popularity).desc())
    pagination = series_query.paginate(page=page, per_page=20)
    return render_template('series_list.html', series_list=pagination.items, pagination=pagination)

@app.route('/series/<series_name>')
def series_detail(series_name):
    """Detailed view for a specific TV show, grouping by seasons."""
    from urllib.parse import unquote
    series_name_decoded = unquote(series_name)
    episodes = Movie.query.filter_by(series_name=series_name_decoded, is_active=True).order_by(Movie.season_number.asc(), Movie.episode_number.asc()).all()
    if not episodes: return redirect(url_for('tv_series_list'))
    seasons = {}
    for ep in episodes:
        s = ep.season_number or 1
        if s not in seasons: seasons[s] = []
        seasons[s].append(ep)
    return render_template('series_detail.html', series_name=series_name_decoded, seasons=seasons, total_episodes=len(episodes))

# ===== ADMIN AUTHENTICATION & DASHBOARD =====
def login_required(f):
    """Decorator: Ensures the user is logged in as an administrator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Secure login for administrators."""
    if request.method == 'POST':
        if request.form.get('password') == os.getenv('ADMIN_PASSWORD'):
            session['admin_logged_in'] = True
            session.permanent = True
            return redirect(url_for('admin'))
        flash('Invalid Credentials', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Logs out admin and redirects home."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    """Main administrative control panel."""
    from admin_utils import get_dashboard_metrics
    metrics = get_dashboard_metrics()
    integrity_stats, total, _, _ = get_db_integrity_stats()
    submissions = UserSubmission.query.order_by(UserSubmission.created_at.desc()).limit(10).all()
    return render_template('admin.html', metrics=metrics, integrity_stats=integrity_stats, integrity_total=total, submissions=submissions)

@app.route('/admin/data-integrity')
@login_required
def admin_data_integrity():
    """Diagnostics page for finding movies with missing metadata."""
    stats, total, fields, filters = get_db_integrity_stats()
    incomplete = Movie.query.filter(or_(*filters)).order_by(Movie.popularity.desc()).limit(50).all()
    
    # Critical Fix: Map missing fields explicitly so template item.missing_fields works
    movies_with_missing = []
    for m in incomplete:
        missing = []
        for field in fields:
            val = getattr(m, field['key'])
            if val is None or val == '' or val == 0 or val == '{}':
                missing.append(field['label'])
        movies_with_missing.append({
            'movie': m,
            'missing_fields': missing
        })
    
    return render_template('admin_integrity.html', 
                         stats=stats, 
                         total_movies=total, 
                         movies_with_missing=movies_with_missing,
                         language_map=LANGUAGE_MAP)

@app.route('/admin/inventory')
@login_required
def admin_inventory():
    """Tabular list of recently updated movies in the inventory."""
    movies = Movie.query.order_by(Movie.last_updated.desc()).limit(100).all()
    return render_template('admin_inventory.html', 
                         movies=movies, 
                         language_map=LANGUAGE_MAP)

@app.route('/admin/operations')
@login_required
def admin_operations():
    """Tracks background script execution and user submissions."""
    from models import ScriptExecution
    submissions = UserSubmission.query.order_by(UserSubmission.created_at.desc()).limit(20).all()
    recent_scripts = ScriptExecution.query.order_by(ScriptExecution.started_at.desc()).limit(10).all()
    return render_template('admin_operations.html', submissions=submissions, recent_scripts=recent_scripts)

@app.route('/admin/audit-log')
@login_required
def admin_audit_log():
    """Historical log of administrative changes and system events."""
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('admin_audit_log.html', logs=logs)

@app.route('/admin/price-drops')
@login_required
def admin_price_drops():
    """Tracks detected price changes for affiliate-linked products."""
    drops = PriceDrop.query.order_by(PriceDrop.detected_at.desc()).limit(100).all()
    return render_template('admin_price_drops.html', price_drops=drops)

@app.route('/admin/persons')
@login_required
def admin_person():
    """Search and manage cast and crew member profiles."""
    query = request.args.get('q', '').strip()
    if query:
        persons = Person.query.filter(Person.name.ilike(f"%{query}%")).all()
    else:
        persons = Person.query.order_by(Person.popularity.desc()).limit(50).all()
    return render_template('admin_person.html', persons=persons, search_query=query)

@app.route('/admin/person/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_person_edit(id):
    """Edits metadata for a specific actor or director."""
    person = Person.query.get_or_404(id)
    if request.method == 'POST':
        person.name = request.form.get('name', person.name)
        person.biography = request.form.get('biography', person.biography)
        person.popularity = float(request.form.get('popularity') or 0.0)
        db.session.commit()
        flash(f'Updated {person.name}', 'success')
        return redirect(url_for('admin_person'))
    return render_template('admin_person_edit.html', person=person)

@app.route('/admin/movie/search', methods=['GET', 'POST'])
@login_required
def admin_movie_search():
    """Admin-only internal search for selecting movies to edit."""
    query = request.form.get('search_query', '').strip() or request.args.get('q', '').strip()
    movies = Movie.query.filter(Movie.title.ilike(f"%{query}%")).all() if query else []
    return render_template('admin_edit_movie.html', movies=movies, search_query=query)

@app.route('/admin/movie/edit/<int:tmdb_id>', methods=['GET', 'POST'])
@login_required
def admin_movie_edit(tmdb_id):
    """Detailed editor for movie metadata and OTT platform links."""
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first_or_404()
    if request.method == 'POST':
        movie.title = request.form.get('title', movie.title)
        movie.overview = request.form.get('overview', movie.overview)
        movie.rating = float(request.form.get('rating') or 0.0)
        movie.is_active = request.form.get('is_active') == 'on'
        
        raw_ott = request.form.get('ott_platforms', '{}')
        try:
            json.loads(raw_ott)
            movie.ott_platforms = raw_ott
        except: pass

        movie.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        flash(f'Successfully updated {movie.title}', 'success')
        return redirect(url_for('admin_movie_search', q=movie.title))
    return render_template('admin_edit_movie.html', movie=movie, movies=None)

@app.route('/admin/movie/bulk-actions', methods=['POST'])
@login_required
def admin_bulk_actions():
    """Handles mass updates (activate, deactivate, delete) for multiple movies at once."""
    movie_ids = request.form.getlist('movie_ids')
    action = request.form.get('bulk_action')
    
    if not movie_ids:
        flash('No movies selected', 'warning')
        return redirect(request.referrer or url_for('admin_movie_search'))
        
    count = 0
    if action == 'delete':
        count = Movie.query.filter(Movie.id.in_(movie_ids)).delete(synchronize_session=False)
    elif action == 'activate':
        count = Movie.query.filter(Movie.id.in_(movie_ids)).update({Movie.is_active: True}, synchronize_session=False)
    elif action == 'deactivate':
        count = Movie.query.filter(Movie.id.in_(movie_ids)).update({Movie.is_active: False}, synchronize_session=False)
    
    db.session.commit()
    flash(f'Successfully performed "{action}" on {count} movies', 'success')
    return redirect(request.referrer or url_for('admin_movie_search'))

@app.route('/admin/submission/<int:id>/update', methods=['POST'])
@login_required
def admin_submission_update(id):
    """Approve or reject a user-submitted movie request."""
    submission = UserSubmission.query.get_or_404(id)
    action = request.form.get('action')
    if action == 'approve': submission.status = 'added'
    elif action == 'reject': submission.status = 'rejected'
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/submission/<int:id>/delete', methods=['POST'])
@login_required
def admin_submission_delete(id):
    """Deletes a submission from the queue."""
    submission = UserSubmission.query.get_or_404(id)
    db.session.delete(submission)
    db.session.commit()
    flash('Submission deleted', 'success')
    return redirect(url_for('admin'))

# ===== MONETIZATION, ANALYTICS & EXTERNAL APIS =====
@app.route('/admin/affiliates')
@login_required
def admin_affiliate_manager():
    """Configures global affiliate tags for Amazon and Apple."""
    config = AffiliateConfig.query.first() or AffiliateConfig()
    dead_links = AffiliateAnalytics.get_dead_affiliate_links()
    price_drops = AffiliateAnalytics.get_high_potential_products()
    return render_template('admin_affiliates.html', config=config, dead_links=dead_links, price_drops=price_drops)

@app.route('/api/actor-image/<actor_name>')
def get_actor_image(actor_name):
    """Proxy API to fetch profile images for actors from TMDB."""
    api_key = os.getenv('TMDB_API_KEY')
    res = requests.get(f"https://api.themoviedb.org/3/search/person?api_key={api_key}&query={actor_name}")
    if res.status_code == 200:
        results = res.json().get('results')
        if results: return jsonify({'profile_path': results[0].get('profile_path')})
    return jsonify({'profile_path': None})

@app.route('/api/fetch-trailer/<int:tmdb_id>')
def api_fetch_trailer(tmdb_id):
    """Fetches the YouTube trailer key for a movie and saves it to the DB."""
    api_key = os.getenv('TMDB_API_KEY')
    res = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={api_key}")
    if res.status_code == 200:
        videos = res.json().get('results', [])
        for v in videos:
            if v['type'] == 'Trailer' and v['site'] == 'YouTube':
                movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
                if movie:
                    movie.youtube_trailer_id = v['key']
                    db.session.commit()
                return jsonify({'youtube_trailer_id': v['key']})
    return jsonify({'error': 'Not found'}), 404

# ===== HEALTH & SECURITY =====
@app.route('/health')
def health_check():
    """Standard health check for server monitoring."""
    return jsonify({'status': 'healthy', 'db': 'connected', 'movie_count': Movie.query.count()})

@app.route('/watchlist/link-email', methods=['POST'])
def watchlist_link_email():
    """Connects an anonymous session to a verified email address."""
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        user_id = session.get('user_id')
        if not email or not user_id: return jsonify({'error': 'Invalid request'}), 400
        token = secrets.token_urlsafe(32)
        record = UserWatchlistEmail.query.filter_by(anonymous_user_id=user_id).first()
        if not record:
            record = UserWatchlistEmail(anonymous_user_id=user_id, email=email, verification_token=token)
            db.session.add(record)
        else:
            record.email = email
            record.verification_token = token
        db.session.commit()
        return jsonify({'success': True, 'token': token})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/watchlist/verify-email/<token>')
def watchlist_verify_email(token):
    """Verifies a user email using a unique secure token."""
    record = UserWatchlistEmail.query.filter_by(verification_token=token).first_or_404()
    record.is_verified = True
    db.session.commit()
    flash('Email verified!', 'success')
    return redirect(url_for('watchlist'))

@app.route('/watchlist/email-status')
def watchlist_email_status():
    """Checks if the current session is linked and verified."""
    user_id = session.get('user_id')
    if not user_id: return jsonify({'linked': False})
    record = UserWatchlistEmail.query.filter_by(anonymous_user_id=user_id).first()
    return jsonify({'linked': record.is_verified if record else False, 'email': record.email if record else None})

@app.route('/watchlist/recover', methods=['POST'])
def watchlist_recover():
    """Allows a user to reclaim a watchlist from a different device using their email."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    record = UserWatchlistEmail.query.filter_by(email=email, is_verified=True).first()
    if record:
        session['user_id'] = record.anonymous_user_id
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

# ===== BULK ENTRY & DIAGNOSTICS =====
@app.route('/admin/ott')
@login_required
def admin_bulk_ott():
    """Visual tool for quickly adding OTT links to movies missing them."""
    return render_template('admin_bulk_ott.html')

@app.route('/api/movies-without-ott')
@login_required
def api_movies_without_ott():
    """Fetches a list of movies that currently have no OTT information."""
    movies = Movie.query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}')).limit(100).all()
    return jsonify({'movies': [m.to_dict_minimal() for m in movies]})

@app.route('/api/save-ott-entry', methods=['POST'])
@login_required
def api_save_ott_entry():
    """Direct API to save a single platform link to a movie."""
    data = request.get_json()
    movie = Movie.query.get(data.get('movie_id'))
    if movie:
        ott_data = json.loads(movie.ott_platforms or '{}')
        ott_data[data.get('platform')] = {'url': data.get('ott_link'), 'added_date': datetime.utcnow().isoformat()}
        movie.ott_platforms = json.dumps(ott_data)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/ott-diagnostics')
@login_required
def api_ott_diagnostics():
    """Comprehensive check of DB health, distribution, and missing data."""
    total = Movie.query.count()
    without_ott = Movie.query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}')).count()
    
    # Year distribution for priority updates
    year_dist = db.session.query(
        func.substr(Movie.release_date, 1, 4).label('year'),
        func.count(Movie.id)
    ).filter(
        (Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}'),
        Movie.release_date != None
    ).group_by('year').order_by(desc('year')).all()
    
    year_dict = {y[0]: y[1] for y in year_dist if y[0]}
    
    return jsonify({
        'total_movies': total, 
        'without_ott': without_ott, 
        'with_ott': total - without_ott,
        'year_distribution': year_dict
    })

# ===== PERSON DETAILS =====
@app.route('/person/<actor_name>')
def person_details(actor_name):
    """Person detail page showing metadata and movies featuring this actor."""
    from urllib.parse import unquote
    name = unquote(actor_name).replace('-', ' ')
    
    # Try to find person record
    person = Person.query.filter(Person.name.ilike(name)).first()
    
    # Get movies featuring this actor (search in cast string)
    movies = Movie.query.filter(
        Movie.is_active == True,
        Movie.cast.ilike(f"%{name}%")
    ).order_by(Movie.popularity.desc()).all()
    
    return render_template('person.html', person=person, person_name=name, movies=movies)

# ===== MOVIE DETAIL (THE ONLY ONE) =====
@app.route('/movie/<movie_identifier>')
def movie_detail(movie_identifier):
    """
    Detailed page for a specific movie.
    Supports TMDB ID (numeric) or Title Slug (string).
    """
    movie = None
    if movie_identifier.isdigit():
        movie = Movie.query.filter_by(tmdb_id=int(movie_identifier)).first()
    
    if not movie:
        # Flexible slug match
        clean_id = movie_identifier.lower().strip('-')
        all_active = Movie.query.filter_by(is_active=True).all()
        movie = next((m for m in all_active if movie_slug_filter(m.title) == clean_id), None)
        # Substring fallback if slug match fails
        if not movie:
            movie = Movie.query.filter(
                Movie.is_active == True,
                Movie.title.ilike(f"%{movie_identifier.replace('-', ' ')}%")
            ).first()

    if not movie: return redirect(url_for('index'))

    # Crucial Fix: Always pass dictionary to template for looping
    ott_data = {}
    if movie.ott_platforms:
        try:
            ott_data = json.loads(movie.ott_platforms) if isinstance(movie.ott_platforms, str) else movie.ott_platforms
        except: ott_data = {}

    status = get_movie_status(movie)
    similar = Movie.query.filter(Movie.id != movie.id, Movie.is_active == True).limit(6).all()
    
    # Process available languages
    available_languages = set()
    if movie.language: available_languages.add(movie.language.lower())
    for _, info in ott_data.items():
        if isinstance(info, dict) and 'languages' in info:
            available_languages.update([l.lower() for l in info['languages']])
    
    available_langs = {c: LANGUAGE_MAP.get(c, c.upper()) for c in available_languages if c}

    return render_template(
        'movie.html', 
        movie=movie, 
        ott_data=ott_data, 
        status=status, 
        similar_movies=similar,
        available_languages=available_langs,
        affiliate_ctas=AffiliateManager.build_smart_cta(movie, ott_data)
    )

# ===== MAIN EXECUTION BLOCK (AT THE END) =====
if __name__ == '__main__':
    with app.app_context():
        # Correctly initialize database before the server starts
        init_database(verbose=False)
    app.run(debug=True, port=5000)