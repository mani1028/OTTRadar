"""
Daily fetch script for new Telugu movie releases
Fetches today's and this week's releases automatically
Usage: python -m scripts.daily_fetch
Or run via: python scheduler.py (runs daily at 09:00)
"""

import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from ott_links import fetch_justwatch_links

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

def has_telugu_translation(tmdb_id):
    """Check if Telugu translation exists"""
    try:
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/translations"
        params = {'api_key': TMDB_API_KEY}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json().get('translations', [])
        return any(t.get('iso_639_1') == 'te' for t in data)
    except Exception:
        return False

def get_app():
    """Get Flask app context"""
    from app import app
    return app

def fetch_watch_providers(title, release_date, region='IN'):
    """
    Fetch OTT watch providers with deep links using JustWatch
    """
    try:
        return fetch_justwatch_links(title, release_date, country=region)
    except Exception as e:
        print(f"⚠️  Error fetching providers for {title}: {str(e)}")
        return {}
def fetch_new_movies():
    """
    Fetch new Telugu movies released in the last 7 days
    This runs daily automatically
    """
    app = get_app()
    
    from models import db, Movie
    
    with app.app_context():
        print(f"\n🎬 Daily fetch started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not TMDB_API_KEY:
            print("❌ TMDB_API_KEY not configured")
            return
        
        try:
            # Calculate date range: last 7 days
            today = datetime.now()
            seven_days_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
            today_str = today.strftime('%Y-%m-%d')
            
            # Fetch from TMDB Discover API
            url = f"{TMDB_BASE_URL}/discover/movie"
            params = {
                'api_key': TMDB_API_KEY,
                'region': 'IN',
                'with_runtime.gte': 60,
                'primary_release_date.gte': seven_days_ago,
                'primary_release_date.lte': today_str,
                'sort_by': 'release_date.desc',
                'page': 1
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            movies = response.json().get('results', [])
            
            if not movies:
                print("   ℹ️  No new Telugu movies found in the last 7 days")
                return
            
            print(f"   Found {len(movies)} Telugu movies from last 7 days")
            
            added_count = 0
            updated_count = 0
            
            for movie in movies:
                try:
                    tmdb_id = movie.get('id')
                    original_language = movie.get('original_language', '')
                    telugu_translation = has_telugu_translation(tmdb_id)
                    if original_language != 'te' and not telugu_translation:
                        continue

                    # Check if movie already exists
                    existing = Movie.query.filter_by(tmdb_id=tmdb_id).first()
                    
                    if existing:
                        # Update providers if not already set
                        existing_providers = existing.get_ott_platforms()
                        if not existing_providers:
                            providers = fetch_watch_providers(movie.get('title', ''), movie.get('release_date', ''), 'IN')
                            if providers:
                                existing.set_ott_platforms(providers)
                                db.session.commit()
                                updated_count += 1
                        continue
                    
                    # Fetch watch providers
                    providers = fetch_watch_providers(movie.get('title', ''), movie.get('release_date', ''), 'IN')
                    
                    # Create new movie
                    new_movie = Movie(
                        tmdb_id=movie['id'],
                        title=movie.get('title', ''),
                        poster=f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}" if movie.get('poster_path') else '',
                        backdrop=f"https://image.tmdb.org/t/p/w1280{movie.get('backdrop_path', '')}" if movie.get('backdrop_path') else '',
                        overview=movie.get('overview', ''),
                        release_date=movie.get('release_date', ''),
                        rating=movie.get('vote_average', 0),
                        language=original_language or 'te',
                        runtime=0,
                        genres='',
                        is_dubbed=(original_language != 'te' and telugu_translation)
                    )
                    
                    # Set OTT platforms
                    new_movie.set_ott_platforms(providers if providers else {})
                    
                    db.session.add(new_movie)
                    added_count += 1
                    
                except Exception as e:
                    print(f"   ⚠️  Error processing movie: {str(e)}")
                    continue
            
            # Commit all at once
            if added_count > 0 or updated_count > 0:
                db.session.commit()
            
            print(f"   ✅ Added {added_count} new movies")
            if updated_count > 0:
                print(f"   ✅ Updated {updated_count} movies")
            
            print(f"✅ Daily fetch completed successfully\n")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API Error: {str(e)}\n")
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")
            db.session.rollback()

if __name__ == '__main__':
    fetch_new_movies()
