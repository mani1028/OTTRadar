"""
Scraper Service for Telugu Movie OTT Tracker
Finds and adds new Telugu movie releases to the database
Usage: Called by scheduler.py daily
"""

import time
import requests
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from dotenv import load_dotenv

load_dotenv()

from app import app
from models import db, Movie

TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    return session

SESSION = create_session()

def fetch_movie_details(tmdb_id, language='te'):
    """Fetch runtime, genres, and original language for a movie"""
    if not TMDB_API_KEY:
        return {}

    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
        params = {'api_key': TMDB_API_KEY, 'language': language}
        response = SESSION.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if language != 'en' and not data.get('overview'):
            params['language'] = 'en'
            response = SESSION.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

        return {
            'runtime': data.get('runtime', 0),
            'genres': ", ".join([g.get('name', '') for g in data.get('genres', []) if g.get('name')]),
            'original_language': data.get('original_language', ''),
            'overview': data.get('overview', '')
        }
    except Exception:
        return {}

def fetch_movie_credits(tmdb_id):
    """Fetch top cast with names and profile images (returns JSON)"""
    if not TMDB_API_KEY:
        return ''

    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits"
        params = {'api_key': TMDB_API_KEY}
        response = SESSION.get(url, params=params, timeout=10)
        response.raise_for_status()
        cast_list = response.json().get('cast', [])[:8]
        
        # Return JSON with name and profile_path for zero-download architecture
        cast_data = [
            {
                'name': c.get('name', ''),
                'profile_path': c.get('profile_path')
            }
            for c in cast_list if c.get('name')
        ]
        
        # If cast_data exists, return as JSON string, otherwise comma-separated for backward compatibility
        if cast_data:
            import json
            return json.dumps(cast_data)
        else:
            # Fallback to old format if no profile_path available
            return ", ".join([c.get('name', '') for c in cast_list if c.get('name')])
    except Exception:
        return ''

def fetch_movie_certification(tmdb_id):
    """Fetch content certification (prefer India)"""
    if not TMDB_API_KEY:
        return ''

    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/release_dates"
        params = {'api_key': TMDB_API_KEY}
        response = SESSION.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get('results', [])

        india = next((r for r in data if r.get('iso_3166_1') == 'IN'), None)
        if india:
            for item in india.get('release_dates', []):
                cert = item.get('certification')
                if cert:
                    return cert

        for region in data:
            for item in region.get('release_dates', []):
                cert = item.get('certification')
                if cert:
                    return cert

        return ''
    except Exception:
        return ''

def has_telugu_translation(tmdb_id):
    """Check if Telugu translation exists"""
    if not TMDB_API_KEY:
        return False

    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/translations"
        params = {'api_key': TMDB_API_KEY}
        response = SESSION.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get('translations', [])
        return any(t.get('iso_639_1') == 'te' for t in data)
    except Exception:
        return False

def fetch_new_telugu_releases():
    """
    Fetch Telugu movies released in the last 7 days
    This is the "Daily" scraper for new releases
    """
    with app.app_context():
        try:
            # Calculate date range (last 7 days)
            today = datetime.now().strftime('%Y-%m-%d')
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            print(f"Fetching new releases from {seven_days_ago} to {today}")
            
            url = f"{TMDB_BASE_URL}/discover/movie"
            params = {
                'api_key': TMDB_API_KEY,
                'region': 'IN',
                'with_runtime.gte': 60,
                'primary_release_date.gte': seven_days_ago,
                'primary_release_date.lte': today,
                'sort_by': 'release_date.desc'
            }
            
            response = SESSION.get(url, params=params, timeout=10)
            movies = response.json().get('results', [])
            
            added = 0
            for movie in movies:
                tmdb_id = movie.get('id')
                original_language = movie.get('original_language', '')
                telugu_translation = has_telugu_translation(tmdb_id)
                if original_language != 'te' and not telugu_translation:
                    continue
                
                # Check if already exists
                if Movie.query.filter_by(tmdb_id=tmdb_id).first():
                    continue
                
                # Fetch providers
                time.sleep(0.3)
                providers = fetch_providers(tmdb_id)

                # Fetch enriched metadata
                details = fetch_movie_details(tmdb_id, language='te')
                cast = fetch_movie_credits(tmdb_id)
                certification = fetch_movie_certification(tmdb_id)
                original_language = details.get('original_language') or original_language
                is_dubbed = original_language != 'te' and telugu_translation
                
                try:
                    new_movie = Movie(
                        tmdb_id=tmdb_id,
                        title=movie.get('title', ''),
                        poster=f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}" if movie.get('poster_path') else '',
                        backdrop=f"https://image.tmdb.org/t/p/original{movie.get('backdrop_path', '')}" if movie.get('backdrop_path') else '',
                        overview=details.get('overview') or movie.get('overview', ''),
                        release_date=movie.get('release_date', ''),
                        rating=movie.get('vote_average', 0),
                        popularity=movie.get('popularity', 0),
                        language=original_language or 'te',
                        runtime=details.get('runtime', 0),
                        genres=details.get('genres', ''),
                        cast=cast,
                        certification=certification,
                        is_dubbed=is_dubbed,
                        fetch_source='scraper',
                        source='scraper',
                        is_active=True
                    )
                    
                    new_movie.set_ott_platforms(providers if providers else {})
                    db.session.add(new_movie)
                    added += 1
                    
                except Exception as e:
                    print(f"Error adding movie: {str(e)[:50]}")
                    continue
            
            db.session.commit()
            print(f"New releases scraper: Added {added} movies")
            return added
        
        except Exception as e:
            db.session.rollback()
            print(f"Error fetching new releases: {str(e)[:50]}")
            return 0

def update_ott_links_for_pending():
    """
    Smart refresh: Coming Soon movies every 2 days, older movies every 7 days
    """
    with app.app_context():
        try:
            # PRIORITY 1: "Coming Soon" movies (no OTT) - check every 2 days
            two_days_ago = datetime.utcnow() - timedelta(days=2)
            coming_soon = Movie.query.filter(
                (Movie.ott_platforms == '{}'),
                (Movie.last_verified < two_days_ago) | (Movie.last_verified == None)
            ).limit(15).all()
            
            # PRIORITY 2: Older movies with OTT - check every 7 days
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            older_movies = Movie.query.filter(
                Movie.ott_platforms != '{}',
                (Movie.last_verified < seven_days_ago) | (Movie.last_verified == None)
            ).limit(10).all()
            
            all_pending = coming_soon + older_movies
            print(f"Smart refresh: {len(coming_soon)} Coming Soon, {len(older_movies)} older movies")
            
            updated = 0
            for movie in all_pending:
                time.sleep(0.3)
                
                providers = fetch_providers(movie.tmdb_id)
                if providers:
                    movie.set_ott_platforms(providers)
                    movie.last_verified = datetime.utcnow()
                    updated += 1
            
            db.session.commit()
            print(f"OTT update: Updated {updated} movies")
            return updated
        
        except Exception as e:
            db.session.rollback()
            print(f"Error updating OTT links: {str(e)[:50]}")
            return 0

def fetch_providers(tmdb_id):
    """Fetch OTT providers for a specific movie (India region)"""
    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/watch/providers"
        params = {'api_key': TMDB_API_KEY}
        
        response = SESSION.get(url, params=params, timeout=10)
        results = response.json().get('results', {}).get('IN', {})
        watch_link = results.get('link')
        
        providers = {}
        
        if 'flatrate' in results:
            for provider in results['flatrate']:
                name = provider.get('provider_name', 'Unknown')
                providers[name] = {'flatrate': True, 'url': watch_link, 'region': 'IN'}
        
        if 'rent' in results:
            for provider in results['rent']:
                name = provider.get('provider_name', 'Unknown')
                if name in providers:
                    providers[name]['rent'] = True
                    providers[name]['url'] = providers[name].get('url') or watch_link
                    providers[name]['region'] = providers[name].get('region') or 'IN'
                else:
                    providers[name] = {'rent': True, 'url': watch_link, 'region': 'IN'}

        if 'buy' in results:
            for provider in results['buy']:
                name = provider.get('provider_name', 'Unknown')
                if name in providers:
                    providers[name]['buy'] = True
                    providers[name]['url'] = providers[name].get('url') or watch_link
                    providers[name]['region'] = providers[name].get('region') or 'IN'
                else:
                    providers[name] = {'buy': True, 'url': watch_link, 'region': 'IN'}
        
        return providers
    
    except Exception as e:
        return {}

def run_scraper():
    """Run all scraper tasks"""
    print("\nRunning scraper tasks...")
    print("=" * 70)
    
    # 1. Fetch new releases
    new_count = fetch_new_telugu_releases()
    
    # 2. Update pending OTT links
    updated_count = update_ott_links_for_pending()
    
    print("=" * 70)
    print(f"Scraper completed: {new_count} new, {updated_count} updated\n")

if __name__ == "__main__":
    run_scraper()
