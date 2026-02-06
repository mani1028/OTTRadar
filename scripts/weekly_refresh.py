"""
Weekly refresh script for OTT provider updates
Updates watch provider information for all movies in database
Runs weekly on Sunday at 9 AM
Usage: python -m scripts.weekly_refresh
"""

import requests
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from ott_links import fetch_justwatch_links

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

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
def refresh_ott_providers():
    """
    Update OTT provider information for all movies in database
    This runs weekly (Sunday 9 AM)
    """
    app = get_app()
    
    from models import db, Movie
    
    with app.app_context():
        print(f"\n📺 Weekly OTT refresh started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not TMDB_API_KEY:
            print("❌ TMDB_API_KEY not configured")
            return
        
        try:
            # Get all movies from database
            all_movies = Movie.query.all()
            
            if not all_movies:
                print("   ℹ️  No movies in database to refresh")
                return
            
            print(f"   Updating OTT info for {len(all_movies)} movies...")
            
            updated_count = 0
            error_count = 0
            
            for movie in all_movies:
                try:
                    # Fetch latest watch provider data
                    providers = fetch_watch_providers(movie.title, movie.release_date, 'IN')
                    
                    # Update movie if providers found
                    if providers:
                        movie.set_ott_platforms(providers)
                        updated_count += 1
                    
                    # Update timestamp
                    movie.last_updated = datetime.now(timezone.utc)
                    
                    # Commit every 50 movies
                    if updated_count % 50 == 0:
                        db.session.commit()
                        print(f"   ✅ Updated {updated_count} movies...")
                    
                except Exception as e:
                    print(f"   ⚠️  Error updating movie {movie.title}: {str(e)}")
                    error_count += 1
                    continue
            
            # Final commit
            db.session.commit()
            
            print(f"   ✅ Updated {updated_count} movies with fresh OTT data")
            if error_count > 0:
                print(f"   ⚠️  {error_count} errors during update")
            
            print(f"✅ Weekly refresh completed successfully\n")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")
            db.session.rollback()

if __name__ == '__main__':
    refresh_ott_providers()
