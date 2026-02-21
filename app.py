from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import sys
import time
import json
import secrets
import re
import subprocess
from datetime import datetime, timezone, date, timedelta

from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify, send_from_directory
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_caching import Cache
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

from celery import Celery
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from difflib import SequenceMatcher
from sqlalchemy import text, and_, or_, desc, func, extract

from config import Config
from models import (
    db, User, Movie, UserSubmission, Watchlist, WatchlistAlert, 
    OTTSnapshot, UserWatchlistEmail, AffiliateConfig, 
    LinkHealthCheck, PriceDrop, ScriptExecution, AuditLog, Person
)
from core.discovery import MovieFilter, OTTDiscovery, UnifiedSearch
from core.affiliate_utils import AffiliateManager, AffiliateAnalytics
from core.logger import app_logger
from db_init import init_database

# 1. Load Environment Variables
load_dotenv()

# 2. Initialize Flask App FIRST
app = Flask(__name__)
app.config.from_object(Config)

# Trust the X-Forwarded-For header (Standard for Cloudflare/AWS/Render/Heroku)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# 3. Initialize Extensions
csrf = CSRFProtect(app)
CORS(app, resources={r"/api/*": {"origins": ["https://ottradar.app", "https://www.ottradar.app"]}})

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    app=app
)

cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 900
})

db.init_app(app)
migrate = Migrate(app, db)

# Celery integration
celery = Celery(app.name, broker=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))
celery.conf.update(app.config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ===== GLOBAL CONSTANTS & CONTEXT PROCESSORS =====
LANGUAGE_MAP = {
    'te': 'Telugu', 'ta': 'Tamil', 'hi': 'Hindi', 'en': 'English', 
    'kn': 'Kannada', 'ml': 'Malayalam', 'mr': 'Marathi',
    'bn': 'Bengali', 'gu': 'Gujarati', 'pa': 'Punjabi'
}

@app.context_processor
def inject_globals():
    """Injects common variables into all Jinja templates automatically."""
    return {
        'language_map': LANGUAGE_MAP,
        'now': datetime.now(timezone.utc),
        'app_name': 'OTT RADAR'
    }


# ===== ERROR HANDLERS =====
@app.errorhandler(404)
def not_found_error(error):
    return render_template('public/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('public/500.html'), 500


# ===== JINJA FILTERS & GLOBALS =====
@app.template_filter('movie_slug')
def movie_slug_filter(title):
    """Converts a movie title into an SEO-friendly URL slug."""
    if not title: return ""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')

@app.template_filter('urlencode')
def urlencode_filter(value):
    """Safely encodes strings for use in URLs."""
    from urllib.parse import quote
    return quote(str(value), safe='')

@app.template_filter('strftime')
def strftime_filter(date_obj, format_string):
    """Formats date objects or ISO strings into readable dates."""
    if not date_obj: return ''
    try:
        if isinstance(date_obj, str):
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        elif isinstance(date_obj, date) and not isinstance(date_obj, datetime):
            date_obj = datetime.combine(date_obj, datetime.min.time())
        return date_obj.strftime(format_string)
    except Exception:
        return ''

def get_search_url(platform, title):
    """Generates a platform-specific search URL."""
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


# ===== HELPER FUNCTIONS =====
def is_released(movie):
    if not movie.release_date: return False
    try:
        release_date = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        return release_date <= date.today()
    except: return False

def get_movie_status(movie):
    if not movie.release_date: return 'upcoming'
    try:
        rd = datetime.strptime(movie.release_date, '%Y-%m-%d').date()
        return 'upcoming' if rd > date.today() else 'available'
    except: return 'available'

def get_db_integrity_stats():
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
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    
    if not query or len(query) < 2:
        return jsonify({'results': [], 'total': 0, 'page': page})
    
    # 1. DB Search
    pagination = UnifiedSearch.search_movies_paginated(query, page=page, per_page=per_page)
    results = pagination.items if pagination else []
    total = pagination.total if pagination else 0

    # 2. TMDB Fallback
    if not results:
        from core.discovery import OTTDiscovery
        tmdb_results = OTTDiscovery.fetch_new_movies(language='te', limit=10)
        min_popularity = 5.0
        min_rating = 5.0
        filtered_tmdb = [item for item in tmdb_results if item.get('popularity', 0) >= min_popularity and item.get('rating', 0) >= min_rating]
        for item in filtered_tmdb:
            if query.lower() in item['title'].lower():
                existing = Movie.query.filter_by(tmdb_id=item['tmdb_id']).first()
                if not existing:
                    new_movie = Movie(
                        tmdb_id=item['tmdb_id'],
                        title=item['title'],
                        overview=item['overview'],
                        poster=item['poster'],
                        rating=item['rating'],
                        language=item['language'],
                        is_active=True
                    )
                    db.session.add(new_movie)
        db.session.commit()
        # Re-run local search to get newly added items
        pagination = UnifiedSearch.search_movies_paginated(query, page=page, per_page=per_page)
        results = pagination.items if pagination else []
        total = pagination.total if pagination else 0

    return jsonify({
        'results': [m.to_dict_minimal() for m in results],
        'total': total,
        'page': page,
        'per_page': per_page,
        'has_more': (page * per_page) < total
    })

@app.route('/api/movies/<category>', methods=['GET'])
def api_movies_category(category):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('limit', 12, type=int)
    
    # DB-Level Pagination
    if category == 'trending':
        pagination = Movie.query.filter_by(is_active=True).filter(Movie.rating >= 6.5).order_by(Movie.popularity.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'results': [m.to_dict_minimal() for m in pagination.items], 'total': pagination.total, 'page': page, 'per_page': per_page, 'has_more': pagination.has_next})
    elif category == 'upcoming':
        upcoming_str = date.today().strftime('%Y-%m-%d')
        pagination = Movie.query.filter_by(is_active=True).filter(Movie.release_date > upcoming_str).order_by(Movie.release_date.asc()).paginate(page=page, per_page=per_page, error_out=False)
        return jsonify({'results': [m.to_dict_minimal() for m in pagination.items], 'total': pagination.total, 'page': page, 'per_page': per_page, 'has_more': pagination.has_next})
    
    # Python-Level Pagination
    movies = []
    if category == 'new-on-ott':
        movies = [m for m in OTTDiscovery.new_on_ott(days=30, limit=200) if is_released(m)]
    elif category == 'free':
        movies = OTTDiscovery.free_movies(limit=200)
    elif category == 'hidden-gems':
        movies = OTTDiscovery.hidden_gems(limit=500)
        
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


# ===== CORE PUBLIC VIEW ROUTES =====
@app.route('/')
def index():
    query = request.args.get('q', '').strip()
    if query:
        search_results = UnifiedSearch.search_movies(query)
        return render_template('public/index.html', search_results=search_results, query=query, total_results=len(search_results))

    cached_homepage = cache.get('homepage_data')
    if cached_homepage:
        return render_template('public/index.html', **cached_homepage, query='')
    
    homepage = OTTDiscovery.homepage_data()
    cache.set('homepage_data', homepage, timeout=900)
    return render_template('public/index.html', **homepage, query='')


@app.route('/discover')
def discover():
    movies = Movie.query.filter_by(is_active=True).order_by(Movie.popularity.desc()).limit(500).all()
    return render_template('public/discover.html', movies=movies)

@app.route('/search')
@limiter.limit("10 per minute")
def search_page():
    trending_searches = OTTDiscovery.trending_now(limit=6)
    genres = ['Action', 'Comedy', 'Drama', 'Thriller', 'Sci-Fi', 'Romance', 'Horror', 'Animation']
    return render_template('public/search.html', trending=trending_searches, genres=genres)

@app.route('/suggest', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def suggest():
    if request.method == 'POST':
        submission_type = request.form.get('type', 'movie').strip()
        if submission_type == 'movie':
            movie_name = request.form.get('movie_name', '').strip()
            if movie_name:
                db.session.add(UserSubmission(movie_title=movie_name, submission_type='movie'))
                try:
                    db.session.commit()
                    flash('Movie request submitted!', 'success')
                except Exception as e:
                    db.session.rollback()
                    app_logger.error(f"Database error in suggest (movie): {str(e)}")
                    flash('Error saving to database. Please check your inputs.', 'error')
        elif submission_type == 'feature':
            title = request.form.get('title', '').strip()
            desc = request.form.get('description', '').strip()
            if title and desc:
                db.session.add(UserSubmission(movie_title=title, comment=desc, submission_type='feature'))
                try:
                    db.session.commit()
                    flash('Suggestion submitted!', 'success')
                except Exception as e:
                    db.session.rollback()
                    app_logger.error(f"Database error in suggest (feature): {str(e)}")
                    flash('Error saving to database. Please check your inputs.', 'error')
    return render_template('public/suggest.html')

@app.route('/about')
def about():
    return render_template('public/about.html')

@app.route('/sitemap.xml')
def sitemap():
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
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.hidden_gems(limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('hidden_gems.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/trending')
def trending():
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.trending_now(limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('trending.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/new-on-ott')
def new_on_ott():
    days = request.args.get('days', 30, type=int)
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.new_on_ott(days=days, limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('new_on_ott.html', movies=movies[start:start+20], page=page, total=total, per_page=20, days=days)

@app.route('/free-movies')
def free_movies():
    page = request.args.get('page', 1, type=int)
    movies = OTTDiscovery.free_movies(limit=500)
    total = len(movies)
    start = (page - 1) * 20
    return render_template('free_movies.html', movies=movies[start:start+20], page=page, total=total, per_page=20)

@app.route('/filter')
def filter_movies():
    language = request.args.getlist('lang')
    platforms = request.args.getlist('platform')
    min_rating = request.args.get('min_rating', 0, type=float)
    genre = request.args.get('genre', '')
    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    year_from = request.args.get('year_from', type=int)
    year_to = request.args.get('year_to', type=int)
    dubbed = request.args.get('dubbed')

    if q:
        pagination = UnifiedSearch.search_movies_paginated(q, page=page, per_page=20)
        movies = pagination.items
        total = pagination.total
    else:
        f = MovieFilter()
        if language:
            f.by_language(language)
        if genre:
            f.by_genre(genre)
        if platforms:
            for platform in platforms:
                if platform:
                    f.by_platform(platform)
        if min_rating and min_rating > 0:
            f.by_rating(min_rating)
        if year_from or year_to:
            f.by_year_range(year_from, year_to)
        if dubbed == 'on':
            f.by_dubbed()
        pagination = f.paginate(page=page, per_page=20)
        movies = pagination.items
        total = pagination.total
        
    applied_filters = {
        'lang': language, 'genre': genre, 'platform': platforms,
        'min_rating': min_rating, 'year_from': year_from,
        'year_to': year_to, 'dubbed_only': dubbed == 'on'
    }
    return render_template('filter_movies.html', movies=movies, page=page, total=total, per_page=20, applied_filters=applied_filters)

@app.route('/movies')
def movies_only():
    page = request.args.get('page', 1, type=int)
    pagination = Movie.query.filter_by(is_active=True).order_by(Movie.popularity.desc()).paginate(page=page, per_page=50)
    return render_template('movies.html', movies=pagination.items, pagination=pagination)

@app.route('/series')
def tv_series_list():
    page = request.args.get('page', 1, type=int)
    series_query = db.session.query(
        Movie.series_name, db.func.count(Movie.id).label('total_episodes'),
        db.func.max(Movie.poster).label('poster'), db.func.max(Movie.rating).label('rating')
    ).filter(Movie.media_type == 'tv').group_by(Movie.series_name).order_by(db.func.max(Movie.popularity).desc())
    pagination = series_query.paginate(page=page, per_page=20)
    return render_template('series_list.html', series_list=pagination.items, pagination=pagination)

@app.route('/series/<series_name>')
def series_detail(series_name):
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

@app.route('/watchlist')
def watchlist():
    user_id = session.get('user_id')
    status = request.args.get('status', '')
    from sqlalchemy.orm import joinedload
    query = Watchlist.query.options(joinedload(Watchlist.movie))
    if user_id:
        query = query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    items = query.order_by(Watchlist.added_at.desc()).all()

    counts = {
        'watchlist': Watchlist.query.filter_by(user_id=user_id, status='watchlist').count() if user_id else 0,
        'watched': Watchlist.query.filter_by(user_id=user_id, status='watched').count() if user_id else 0,
        'interested': Watchlist.query.filter_by(user_id=user_id, status='interested').count() if user_id else 0,
    }
    total = sum(counts.values())

    return render_template(
        'watchlist.html', movies=items, total=total, counts=counts, status=status
    )

@app.route('/person/<actor_name>')
def person_details(actor_name):
    from urllib.parse import unquote
    name = unquote(actor_name).replace('-', ' ')
    person = Person.query.filter(Person.name.ilike(name)).first()
    movies = Movie.query.filter(Movie.is_active == True, Movie.cast.ilike(f"%{name}%")).order_by(Movie.popularity.desc()).all()
    return render_template('person.html', person=person, person_name=name, movies=movies)


@app.route('/movie/<movie_identifier>')
def movie_detail(movie_identifier):
    # 1. Try numeric ID lookup (Fastest)
    if movie_identifier.isdigit():
        movie = Movie.query.filter_by(tmdb_id=int(movie_identifier)).first()
        if movie:
            slug = movie_slug_filter(movie.title)
            if slug and slug != movie_identifier:
                return redirect(url_for('movie_detail', movie_identifier=slug), code=301)
            # Break out to the rest of the function instead of returning early

    # 2. Try Slug/Title Lookup if ID wasn't found
    if 'movie' not in locals() or not movie:
        clean_title = movie_identifier.replace('-', ' ')
        movie = Movie.query.filter(Movie.is_active == True, Movie.title.ilike(clean_title)).first()

        # 3. Fallback: Fuzzy search
        if not movie:
            movie = Movie.query.filter(Movie.is_active == True, Movie.title.ilike(f"%{clean_title}%")).order_by(Movie.popularity.desc()).first()

    if not movie:
        return render_template('public/404.html'), 404

    # Real-time enrichment if missing critical data
    if not movie.ott_platforms or movie.ott_platforms == '{}' or not movie.overview or len(movie.overview or '') < 10:
        from core.discovery import OTTDiscovery
        fresh_data = OTTDiscovery.enrich_movie_metadata(movie.tmdb_id)
        for key, value in fresh_data.items():
            setattr(movie, key, value)
        movie.last_updated = datetime.now(timezone.utc)
        db.session.commit()

    # --- Prepare missing template variables ---
    import json
    try:
        ott_data = json.loads(movie.ott_platforms) if movie.ott_platforms else {}
    except Exception:
        ott_data = {}

    available_languages = {}

    similar_movies = Movie.query.filter(Movie.is_active == True, Movie.id != movie.id).order_by(Movie.popularity.desc()).limit(6).all()

    return render_template(
        'movie.html', 
        movie=movie, 
        ott_data=ott_data, 
        available_languages=available_languages, 
        similar_movies=similar_movies,
        status=get_movie_status(movie)
    )


# ===== EXTERNAL & AFFILIATE APIS =====
@app.route('/out')
def outbound_affiliate():
    url = request.args.get('url')
    platform = request.args.get('platform')
    movie_id = request.args.get('movie_id')
    try:
        AffiliateAnalytics.log_click(platform=platform, url=url, movie_id=movie_id, user_agent=request.headers.get('User-Agent'))
    except Exception as e:
        app_logger.error(f"Affiliate click logging failed: {str(e)}")
    if url and (url.startswith('http://') or url.startswith('https://')):
        return redirect(url, code=302)
    return render_template('public/404.html'), 404

@app.route('/api/actor-image/<actor_name>')
def get_actor_image(actor_name):
    api_key = os.getenv('TMDB_API_KEY')
    try:
        res = requests.get(
            "https://api.themoviedb.org/3/search/person",
            params={'api_key': api_key, 'query': actor_name},
            timeout=10
        )
        res.raise_for_status()
        results = res.json().get('results')
        if results:
            return jsonify({'profile_path': results[0].get('profile_path')})
    except requests.RequestException as e:
        app_logger.error(f"TMDB actor image API error: {e}")
    return jsonify({'profile_path': None})

@app.route('/api/fetch-trailer/<int:tmdb_id>')
def api_fetch_trailer(tmdb_id):
    api_key = os.getenv('TMDB_API_KEY')
    try:
        res = requests.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos?api_key={api_key}", timeout=10)
        res.raise_for_status()
        videos = res.json().get('results', [])
        for v in videos:
            if v['type'] == 'Trailer' and v['site'] == 'YouTube':
                movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
                if movie:
                    movie.youtube_trailer_id = v['key']
                    db.session.commit()
                    return jsonify({'trailer_id': v['key']})
        return jsonify({'error': 'Not found'}), 404
    except requests.RequestException as e:
        app_logger.error(f"TMDB trailer API error: {e}")
        return jsonify({'error': 'Trailer fetch failed'}), 503

@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1')).scalar()
        return jsonify({'status': 'healthy', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'db': 'disconnected', 'error': str(e)}), 500


# ===== BULK OTT & DIAGNOSTIC APIS =====
@app.route('/api/movies-without-ott')
@login_required
def api_movies_without_ott():
    movies = Movie.query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '{}') | (Movie.ott_platforms == '')).all()
    return jsonify({'movies': [m.to_dict_minimal() for m in movies]})

@app.route('/api/save-ott-entry', methods=['POST'])
@login_required
def api_save_ott_entry():
    data = request.get_json()
    movie = Movie.query.get(data.get('movie_id'))
    
    if movie:
        try: ott_data = json.loads(movie.ott_platforms or '{}')
        except: ott_data = {}
        
        platform = data.get('platform')
        link = data.get('ott_link')
        ott_release_date = data.get('ott_release_date')
        
        # Save Platform link
        if platform and link:
            ott_data[platform] = {
                'url': link, 
                'added_date': datetime.now(timezone.utc).isoformat()
            }
            movie.ott_platforms = json.dumps(ott_data)
        
        # Save OTT Release Date so "New on OTT" starts catching it
        if ott_release_date:
            movie.ott_release_date = ott_release_date
            
        movie.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Saved link and date for {movie.title}!'})
        
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.route('/api/ott-diagnostics')
@login_required
def api_ott_diagnostics():
    total = Movie.query.count()
    without_ott = Movie.query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}')).count()
    
    year_dist = db.session.query(
        func.substr(Movie.release_date, 1, 4).label('year'),
        func.count(Movie.id)
    ).filter(
        (Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}'),
        Movie.release_date != None
    ).group_by('year').order_by(desc('year')).all()
    
    lang_dist = db.session.query(
        Movie.language,
        func.count(Movie.id)
    ).filter(
        (Movie.ott_platforms == None) | (Movie.ott_platforms == '') | (Movie.ott_platforms == '{}')
    ).group_by(Movie.language).all()

    return jsonify({
        'total_movies': total, 
        'without_ott': without_ott, 
        'with_ott': total - without_ott,
        'year_distribution': {y[0]: y[1] for y in year_dist if y[0]},
        'language_distribution': {l[0]: l[1] for l in lang_dist if l[0]}
    })


# ===== ADMIN DASHBOARD & CORE ROUTES =====
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_admin():
            login_user(user)
            return redirect(url_for('admin'))
        flash('Invalid Credentials', 'error')
    return render_template('admin/admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin():
    from core.admin_utils import get_dashboard_metrics
    metrics = get_dashboard_metrics()
    integrity_stats, total, _, _ = get_db_integrity_stats()
    submissions = UserSubmission.query.order_by(UserSubmission.created_at.desc()).limit(10).all()

    platforms_query = db.session.query(Movie.ott_platforms).all()
    platforms_count = {}
    unique_platforms = set()
    free_movie_count = 0
    for row in platforms_query:
        if row[0]:
            try:
                p_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                if any(p.lower() == 'youtube' for p in p_data.keys()):
                    free_movie_count += 1
                for p in p_data.keys():
                    platforms_count[p] = platforms_count.get(p, 0) + 1
                    unique_platforms.add(p)
            except: continue
    stats = {
        'total_unique_platforms': len(unique_platforms),
        'platforms': platforms_count
    }

    return render_template('admin.html', metrics=metrics, integrity_stats=integrity_stats, integrity_total=total, submissions=submissions, stats=stats, free_movie_count=free_movie_count)

@app.route('/admin/data-integrity')
@login_required
def admin_data_integrity():
    stats, total, fields, filters = get_db_integrity_stats()
    incomplete = Movie.query.filter(or_(*filters)).order_by(Movie.popularity.desc()).limit(50).all()
    
    movies_with_missing = []
    for m in incomplete:
        missing = [field['label'] for field in fields if not getattr(m, field['key']) or getattr(m, field['key']) == 0 or getattr(m, field['key']) == '{}']
        movies_with_missing.append({'movie': m, 'missing_fields': missing})
    
    return render_template('admin/admin_integrity.html', stats=stats, total_movies=total, movies_with_missing=movies_with_missing, language_map=LANGUAGE_MAP)

@app.route('/admin/inventory')
@login_required
def admin_inventory():
    filter_type = request.args.get('filter', 'all')
    page = request.args.get('page', 1, type=int)
    query = Movie.query.filter_by(is_active=True)
    if filter_type == 'missing_trailer':
        query = query.filter((Movie.youtube_trailer_id == None) | (Movie.youtube_trailer_id == ''))
    elif filter_type == 'missing_ott':
        query = query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '{}'))
    elif filter_type == 'missing_poster':
        query = query.filter((Movie.poster == None) | (Movie.poster == ''))
    elif filter_type == 'missing_overview':
        query = query.filter((Movie.overview == None) | (Movie.overview == ''))
    elif filter_type == 'missing_cast':
        query = query.filter((Movie.cast == None) | (Movie.cast == ''))
    elif filter_type == 'missing_genres':
        query = query.filter((Movie.genres == None) | (Movie.genres == ''))
    elif filter_type == 'missing_runtime':
        query = query.filter((Movie.runtime == None) | (Movie.runtime == 0))
    elif filter_type == 'missing_rating':
        query = query.filter((Movie.rating == None) | (Movie.rating == 0))
    pagination = query.order_by(Movie.last_updated.desc()).paginate(page=page, per_page=50)
    return render_template('admin/admin_inventory.html', movies=pagination.items, pagination=pagination, language_map=LANGUAGE_MAP, filter_type=filter_type)

@app.route('/admin/telugu-sustain')
@app.route('/admin/telugu-audio-tracker')
@login_required
def admin_telugu_sustain():
    """Dashboard to fix the critical data gaps for Telugu content."""
    page = request.args.get('page', 1, type=int)
    query = Movie.query.filter((Movie.language == 'te') | (Movie.has_telugu_audio == True))
    
    gap_type = request.args.get('filter') or request.args.get('gap')
    if gap_type in ('date', 'no_date'):
        query = query.filter((Movie.ott_release_date == None) | (Movie.ott_release_date == ''))
    elif gap_type in ('platform', 'no_platforms'):
        query = query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '{}'))

    pagination = query.order_by(Movie.popularity.desc()).paginate(page=page, per_page=50)
    return render_template('admin/admin_inventory.html', movies=pagination.items, pagination=pagination, filter_type='telugu_sustain')

@app.route('/admin/ott')
@login_required
def admin_bulk_ott():
    """Manage movies missing OTT links in a bulk view."""
    # We load data straight from the DB into the template here
    year_str = request.args.get('year')
    year = int(year_str) if year_str and year_str.isdigit() else None
    
    query = Movie.query.filter((Movie.ott_platforms == None) | (Movie.ott_platforms == '{}') | (Movie.ott_platforms == ''))
    if year: query = query.filter(Movie.release_date.like(f"{year}%"))
    
    # We fetch enough so you have a good backlog to process
    movies = query.order_by(Movie.popularity.desc()).limit(150).all()
    return render_template('admin/admin_bulk_ott.html', movies=movies, current_year=year)


@app.route('/admin/submissions')
@app.route('/admin/all-submissions')
@login_required
def admin_submissions():
    page = request.args.get('page', 1, type=int)
    pagination = UserSubmission.query.order_by(UserSubmission.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/admin_submissions.html', submissions=pagination.items, pagination=pagination)

@app.route('/admin/submission/<int:id>/update', methods=['POST'])
@login_required
def admin_submission_update(id):
    submission = UserSubmission.query.get_or_404(id)
    action = request.form.get('action')
    if action == 'approve': submission.status = 'added'
    elif action == 'reject': submission.status = 'rejected'
    db.session.commit()
    flash(f'Submission {action}ed successfully.', 'success')
    return redirect(request.referrer or url_for('admin_submissions'))

@app.route('/admin/submission/<int:id>/delete', methods=['POST'])
@login_required
def admin_submission_delete(id):
    submission = UserSubmission.query.get_or_404(id)
    db.session.delete(submission)
    db.session.commit()
    flash('Submission deleted.', 'info')
    return redirect(request.referrer or url_for('admin_submissions'))

@app.route('/admin/operations')
@login_required
def admin_operations():
    from models import ScriptExecution
    submissions = UserSubmission.query.order_by(UserSubmission.created_at.desc()).limit(20).all()
    recent_scripts = ScriptExecution.query.order_by(ScriptExecution.started_at.desc()).limit(10).all()
    return render_template('admin/admin_operations.html', submissions=submissions, recent_scripts=recent_scripts)

@app.route('/admin/audit-log')
@login_required
def admin_audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template('admin/admin_audit_log.html', logs=logs)

@app.route('/admin/price-drops')
@login_required
def admin_price_drops():
    drops = PriceDrop.query.order_by(PriceDrop.detected_at.desc()).limit(100).all()
    return render_template('admin/admin_price_drops.html', price_drops=drops)

@app.route('/admin/person')
@login_required
def admin_person():
    query = request.args.get('q', '').strip()
    if query:
        persons = Person.query.filter(Person.name.ilike(f"%{query}%")).all()
    else:
        persons = Person.query.order_by(Person.popularity.desc()).limit(50).all()
    return render_template('admin/admin_person.html', persons=persons, search_query=query)

@app.route('/admin/person/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def admin_person_edit(id):
    person = Person.query.get_or_404(id)
    if request.method == 'POST':
        person.name = request.form.get('name', person.name)
        person.biography = request.form.get('biography', person.biography)
        person.popularity = float(request.form.get('popularity') or 0.0)
        db.session.commit()
        flash(f'Updated {person.name}', 'success')
        return redirect(url_for('admin_person'))
    return render_template('admin/admin_person_edit.html', person=person)

@app.route('/admin/affiliates')
@login_required
def admin_affiliate_manager():
    config = AffiliateConfig.query.first() or AffiliateConfig()
    dead_links = AffiliateAnalytics.get_dead_affiliate_links()
    price_drops = AffiliateAnalytics.get_high_potential_products()
    dead_link_count = len(dead_links) if dead_links else 0
    return render_template(
        'admin/admin_affiliates.html', 
        config=config, dead_links=dead_links, 
        price_drops=price_drops, dead_link_count=dead_link_count
    )

@app.route('/admin/affiliate/health-check', methods=['POST'])
@login_required
def admin_affiliate_health_check():
    flash('Affiliate link health check started!', 'info')
    return redirect(url_for('admin_affiliate_manager'))

# --- Affiliate Config Update Endpoint ---
@app.route('/admin/affiliate/update-config', methods=['POST'])
@login_required
def admin_affiliate_update_config():
    # Example logic: update AffiliateConfig from form
    config = AffiliateConfig.query.first() or AffiliateConfig()
    config.amazon_associate_id = request.form.get('amazon_associate_id')
    config.prime_cta_text = request.form.get('prime_cta_text')
    config.amazon_enabled = 'amazon_enabled' in request.form
    config.apple_affiliate_id = request.form.get('apple_affiliate_id')
    config.apple_enabled = 'apple_enabled' in request.form
    db.session.add(config)
    db.session.commit()
    flash('Affiliate configuration updated successfully!', 'success')
    return redirect(url_for('admin_affiliate_manager'))
# ===== ADMIN MOVIE EDITING & ACTIONS =====
@app.route('/admin/movie/search', methods=['GET', 'POST'])
@login_required
def admin_movie_search():
    query = request.form.get('search_query', '').strip() or request.args.get('q', '').strip()
    if not query:
        return render_template('admin/admin_edit_movie.html', movies=[], search_query="")

    movies = []
    # Search Local Database first
    if query.isdigit():
        tmdb_id = int(query)
        movies = Movie.query.filter_by(tmdb_id=tmdb_id).all()
        # If NOT found locally, search TMDB API directly
        if not movies:
            from core.discovery import OTTDiscovery
            fresh_data = OTTDiscovery.enrich_movie_metadata(tmdb_id)
            if fresh_data and fresh_data.get('overview'):
                new_movie = Movie(
                    tmdb_id=tmdb_id,
                    title=fresh_data.get('title', f"Movie {tmdb_id}"),
                    overview=fresh_data.get('overview'),
                    poster=fresh_data.get('poster'),
                    rating=fresh_data.get('rating', 0),
                    language=fresh_data.get('language', 'te'),
                    is_active=False
                )
                db.session.add(new_movie)
                db.session.commit()
                movies = [new_movie]
                flash(f'Movie {tmdb_id} found on TMDB and added to local database.', 'info')
    else:
        movies = Movie.query.filter(Movie.title.ilike(f"%{query}%")).order_by(Movie.popularity.desc()).all()

    return render_template('admin/admin_edit_movie.html', movies=movies, search_query=query)

@app.route('/admin/movie/edit/<int:tmdb_id>', methods=['GET', 'POST'])
@login_required
def admin_movie_edit(tmdb_id):
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first_or_404()
    if request.method == 'POST':
        movie.title = request.form.get('title')
        movie.overview = request.form.get('overview')
        movie.language = request.form.get('language')
        movie.certification = request.form.get('certification')
        movie.genres = request.form.get('genres')
        movie.cast = request.form.get('cast')
        movie.poster = request.form.get('poster')
        movie.backdrop = request.form.get('backdrop')
        movie.youtube_trailer_id = request.form.get('youtube_trailer_id')
        movie.media_type = request.form.get('media_type')
        movie.release_date = request.form.get('release_date')
        movie.ott_release_date = request.form.get('ott_release_date')
        movie.trailer = request.form.get('trailer')
        movie.status = request.form.get('status')
        movie.series_name = request.form.get('series_name')

        try: movie.rating = float(request.form.get('rating'))
        except: movie.rating = 0.0
        try: movie.popularity = float(request.form.get('popularity'))
        except: movie.popularity = 0.0
        try: movie.runtime = int(request.form.get('runtime'))
        except: movie.runtime = 0
        try:
            val = request.form.get('season_number')
            movie.season_number = int(val) if val else None
        except: pass
        try:
            val = request.form.get('episode_number')
            movie.episode_number = int(val) if val else None
        except: pass
        try:
            val = request.form.get('episode_count')
            movie.episode_count = int(val) if val else None
        except: pass

        movie.is_active = request.form.get('is_active') == 'on'
        movie.is_dubbed = request.form.get('is_dubbed') == 'on'
        movie.has_telugu_audio = request.form.get('has_telugu_audio') == 'on'

        raw_ott = request.form.get('ott_platforms', '{}')
        try:
            json.loads(raw_ott)
            movie.ott_platforms = raw_ott
        except Exception as e:
            flash(f'Invalid OTT JSON format: {str(e)}', 'error')

        movie.last_updated = datetime.now(timezone.utc)

        try:
            db.session.commit()
            flash(f'Successfully updated {movie.title}', 'success')
        except Exception as e:
            db.session.rollback()
            app_logger.error(f"Database error updating movie: {str(e)}")
            flash('Error saving to database. Please check your inputs.', 'error')

        return redirect(url_for('admin_movie_search', q=movie.tmdb_id))
    return render_template('admin/admin_edit_movie.html', movie=movie, movies=[])

@app.route('/admin/movie/bulk-actions', methods=['POST'])
@login_required
def admin_bulk_actions():
    movie_ids = request.form.getlist('movie_ids[]')
    action = request.form.get('action')
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
    elif action == 'refresh_ott':
        from core.discovery import OTTDiscovery
        movies_to_update = Movie.query.filter(Movie.id.in_(movie_ids)).all()
        for movie in movies_to_update:
            fresh_data = OTTDiscovery.enrich_movie_metadata(movie.tmdb_id)
            if fresh_data.get('ott_platforms'):
                movie.ott_platforms = fresh_data['ott_platforms']
                movie.last_checked = datetime.now(timezone.utc)
                movie.last_updated = datetime.now(timezone.utc)
                count += 1
    
    db.session.commit()
    flash(f'Successfully performed "{action}" on {count} movies', 'success')
    return redirect(request.referrer or url_for('admin_movie_search'))

@app.route('/admin/validate-json', methods=['POST'])
@login_required
@csrf.exempt
def admin_validate_json():
    data = request.get_json()
    try:
        json.loads(data.get('json_string', '{}'))
        return jsonify({'valid': True})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})


# ===== ADMIN SCRIPT ROUTING WITH CELERY =====
@app.route('/admin/run-script/<script_name>', methods=['POST'])
@login_required
@csrf.exempt  # Make sure this is exempt so AJAX works
def run_admin_script(script_name):
    allowed_scripts = {
        'discover': 'scripts/discover_new_movies.py',
        'enrich': 'scripts/enrich_metadata_trailers.py',
        'daily_check': 'scripts/daily_ott_checker.py',
        'export': 'scripts/export_db.py'
    }
    if script_name not in allowed_scripts:
        return jsonify({'success': False, 'error': 'Invalid script name'})
    try:
        script_path = os.path.join(app.root_path, allowed_scripts[script_name])
        cmd = [sys.executable, script_path]
        if script_name == 'discover' and request.is_json:
            data = request.get_json()
            if data.get('year'): cmd.extend(['--year', str(data['year'])])
            if data.get('language'): cmd.extend(['--language', str(data['language'])])
            if data.get('limit'): cmd.extend(['--limit', str(data['limit'])])
        subprocess.Popen(cmd)
        return jsonify({'success': True, 'message': f'{script_name} started on server!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@celery.task(name='tasks.run_discovery')
def celery_run_discovery(limit=20, language=None, year=None):
    from scripts.discover_new_movies import discover_movies
    discover_movies(year=year, language=language, limit=limit)
    return {'status': 'completed', 'script': 'discover'}

@celery.task(name='tasks.run_enrichment')
def celery_run_enrichment():
    from scripts.enrich_metadata_trailers import main as run_enrichment_logic
    run_enrichment_logic()
    return {'status': 'completed', 'script': 'enrich'}

@celery.task(name='tasks.run_daily_check')
def celery_run_daily_check(limit=50):
    from scripts.daily_ott_checker import check_daily_updates
    check_daily_updates(limit=limit)
    return {'status': 'completed', 'script': 'daily_check'}

@celery.task(name='tasks.run_export')
def celery_run_export():
    from scripts.export_db import export_database
    export_database()
    return {'status': 'completed', 'script': 'export'}


# ===== MAIN EXECUTION BLOCK =====
if __name__ == '__main__':
    with app.app_context():
        init_database(verbose=False)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False))