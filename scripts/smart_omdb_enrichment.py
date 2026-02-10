#!/usr/bin/env python3
"""
Smart OMDb enrichment with API call tracking to avoid wasting the 1000/day limit.

This script:
1. Tracks which movies were already checked with OMDb
2. Skips movies that returned "Movie not found" from OMDb
3. Only processes movies that actually have a chance of improvement
4. Saves progress so you can run multiple batches

Usage:
    python scripts/smart_omdb_enrichment.py --limit 500
    python scripts/smart_omdb_enrichment.py --check-status  # See what can be improved
"""

import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Movie
from dotenv import load_dotenv

load_dotenv()

OMDB_API_KEY = os.getenv('OMDB_API_KEY', '5cad8aea')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
OMDB_BASE = 'http://www.omdbapi.com/'
TMDB_BASE = 'https://api.themoviedb.org/3'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKING_FILE = os.path.join(BASE_DIR, 'omdb_tracking.json')


def load_tracking():
    """Load OMDb tracking data (movies already checked)"""
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r') as f:
            return json.load(f)
    return {
        'last_run': None,
        'total_api_calls': 0,
        'checked_movies': {},  # tmdb_id -> {status, date, found_data}
        'not_found_in_omdb': []  # List of TMDB IDs not in OMDb
    }


def save_tracking(tracking):
    """Save OMDb tracking data"""
    tracking['last_run'] = datetime.now(timezone.utc).isoformat()
    with open(TRACKING_FILE, 'w') as f:
        json.dump(tracking, f, indent=2)


def get_imdb_id_from_tmdb(tmdb_id):
    """Get IMDb ID from TMDB"""
    try:
        url = f"{TMDB_BASE}/movie/{tmdb_id}/external_ids"
        params = {'api_key': TMDB_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('imdb_id')
    except:
        pass
    return None


def omdb_get(imdb_id):
    """Fetch movie data from OMDb"""
    try:
        params = {'apikey': OMDB_API_KEY, 'i': imdb_id, 'plot': 'full'}
        response = requests.get(OMDB_BASE, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('Response') == 'True':
                return data
            elif data.get('Error') == 'Movie not found!':
                return 'NOT_FOUND'
    except Exception as e:
        print(f"    ⚠️ OMDb error: {e}")
    return None


def fill_from_omdb(movie, omdb_data):
    """Fill missing fields from OMDb data"""
    updated = False
    
    if not movie.overview and omdb_data.get('Plot') and omdb_data['Plot'] != 'N/A':
        movie.overview = omdb_data['Plot']
        updated = True
        print(f"      ✓ overview from OMDb")
    
    if not movie.poster and omdb_data.get('Poster') and omdb_data['Poster'] != 'N/A':
        movie.poster = omdb_data['Poster']
        updated = True
        print(f"      ✓ poster from OMDb")
    
    if (not movie.runtime or movie.runtime == 0) and omdb_data.get('Runtime'):
        runtime_str = omdb_data['Runtime'].replace(' min', '').replace(',', '')
        try:
            movie.runtime = int(runtime_str)
            updated = True
            print(f"      ✓ runtime from OMDb")
        except:
            pass
    
    if not movie.genres and omdb_data.get('Genre') and omdb_data['Genre'] != 'N/A':
        movie.genres = omdb_data['Genre']
        updated = True
        print(f"      ✓ genres from OMDb")
    
    if not movie.cast and omdb_data.get('Actors') and omdb_data['Actors'] != 'N/A':
        movie.cast = omdb_data['Actors']
        updated = True
        print(f"      ✓ cast from OMDb")
    
    if not movie.certification and omdb_data.get('Rated') and omdb_data['Rated'] != 'N/A':
        movie.certification = omdb_data['Rated']
        updated = True
        print(f"      ✓ certification from OMDb")
    
    if (not movie.rating or movie.rating == 0) and omdb_data.get('imdbRating'):
        try:
            rating = float(omdb_data['imdbRating'])
            if rating > 0:
                movie.rating = rating
                updated = True
                print(f"      ✓ rating from OMDb")
        except:
            pass
    
    if not movie.release_date and omdb_data.get('Released') and omdb_data['Released'] != 'N/A':
        # OMDb format: "DD MMM YYYY" -> convert to YYYY-MM-DD
        try:
            from datetime import datetime as dt
            date = dt.strptime(omdb_data['Released'], '%d %b %Y')
            movie.release_date = date.strftime('%Y-%m-%d')
            updated = True
            print(f"      ✓ release_date from OMDb")
        except:
            pass
    
    return updated


def get_missing_fields(movie):
    """Get list of missing critical fields"""
    missing = []
    if not movie.overview:
        missing.append('overview')
    if not movie.poster:
        missing.append('poster')
    if not movie.runtime or movie.runtime == 0:
        missing.append('runtime')
    if not movie.genres:
        missing.append('genres')
    if not movie.cast:
        missing.append('cast')
    if not movie.certification:
        missing.append('certification')
    if not movie.rating or movie.rating == 0:
        missing.append('rating')
    if not movie.release_date:
        missing.append('release_date')
    return missing


def check_status():
    """Check how many movies can be improved with OMDb"""
    tracking = load_tracking()
    
    with app.app_context():
        # Get all movies with missing fields
        from sqlalchemy import or_
        
        query = Movie.query.filter(
            Movie.tmdb_id != None,
            or_(
                or_(Movie.overview == None, Movie.overview == ''),
                or_(Movie.poster == None, Movie.poster == ''),
                or_(Movie.runtime == None, Movie.runtime == 0),
                or_(Movie.genres == None, Movie.genres == ''),
                or_(Movie.cast == None, Movie.cast == ''),
                or_(Movie.certification == None, Movie.certification == ''),
                or_(Movie.rating == None, Movie.rating == 0),
                or_(Movie.release_date == None, Movie.release_date == '')
            )
        )
        
        all_incomplete = query.all()
        
        # Categorize movies
        already_checked = []
        not_found = []
        ready_to_check = []
        
        for movie in all_incomplete:
            tmdb_str = str(movie.tmdb_id)
            
            if tmdb_str in tracking.get('not_found_in_omdb', []):
                not_found.append(movie)
            elif tmdb_str in tracking.get('checked_movies', {}):
                already_checked.append(movie)
            else:
                ready_to_check.append(movie)
        
        # Count missing fields for ready-to-check movies
        field_counts = {
            'overview': 0, 'poster': 0, 'runtime': 0, 'genres': 0,
            'cast': 0, 'certification': 0, 'rating': 0, 'release_date': 0
        }
        
        for movie in ready_to_check:
            missing = get_missing_fields(movie)
            for field in missing:
                if field in field_counts:
                    field_counts[field] += 1
        
        print("=" * 70)
        print("📊 OMDb ENRICHMENT STATUS")
        print("=" * 70)
        print(f"\n🎬 Total movies with missing data: {len(all_incomplete)}")
        print(f"   ├─ ✅ Already checked with OMDb: {len(already_checked)}")
        print(f"   ├─ ❌ Not found in OMDb: {len(not_found)}")
        print(f"   └─ 🆕 Ready to check (NEW): {len(ready_to_check)}")
        
        print(f"\n📈 Missing fields in {len(ready_to_check)} ready-to-check movies:")
        for field, count in sorted(field_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {field}: {count}")
        
        print(f"\n🔑 OMDb API Usage:")
        print(f"   • Total calls made: {tracking.get('total_api_calls', 0)}")
        print(f"   • Daily limit: 1000")
        print(f"   • Remaining today: {1000 - tracking.get('total_api_calls', 0)} (approx)")
        
        if tracking.get('last_run'):
            print(f"   • Last run: {tracking['last_run']}")
        
        print(f"\n💡 Recommendation:")
        if len(ready_to_check) == 0:
            print(f"   All movies have been checked! Run TMDB enrichment for new movies.")
        elif len(ready_to_check) <= 500:
            print(f"   Run: python scripts/smart_omdb_enrichment.py --limit {len(ready_to_check)}")
        else:
            print(f"   Run: python scripts/smart_omdb_enrichment.py --limit 500")
            print(f"   (Can run again tomorrow for next batch)")
        
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Smart OMDb enrichment with tracking')
    parser.add_argument('--limit', type=int, default=500, help='Limit number of movies to process (default: 500)')
    parser.add_argument('--check-status', action='store_true', help='Check enrichment status without processing')
    parser.add_argument('--reset-tracking', action='store_true', help='Reset tracking file (start fresh)')
    args = parser.parse_args()
    
    if not OMDB_API_KEY:
        print('❌ ERROR: OMDB_API_KEY not found in .env file')
        return
    
    if not TMDB_API_KEY:
        print('❌ ERROR: TMDB_API_KEY not found in .env file')
        return
    
    if args.reset_tracking:
        if os.path.exists(TRACKING_FILE):
            os.remove(TRACKING_FILE)
            print(f"✅ Tracking file reset: {TRACKING_FILE}")
        return
    
    if args.check_status:
        check_status()
        return
    
    # Load tracking data
    tracking = load_tracking()
    
    print("=" * 70)
    print("🎬 SMART OMDb ENRICHMENT (Rate-Limit Safe)")
    print("=" * 70)
    print(f"🔑 OMDb Key: {OMDB_API_KEY[:4]}...")
    print(f"📊 Limit: {args.limit} movies")
    print(f"📝 Tracking file: {TRACKING_FILE}")
    print(f"🔄 API calls this session: {tracking.get('total_api_calls', 0)}/1000")
    print("=" * 70)
    
    with app.app_context():
        # Get movies with missing fields that haven't been checked yet
        from sqlalchemy import or_
        
        query = Movie.query.filter(
            Movie.tmdb_id != None,
            or_(
                or_(Movie.overview == None, Movie.overview == ''),
                or_(Movie.poster == None, Movie.poster == ''),
                or_(Movie.runtime == None, Movie.runtime == 0),
                or_(Movie.genres == None, Movie.genres == ''),
                or_(Movie.cast == None, Movie.cast == ''),
                or_(Movie.certification == None, Movie.certification == ''),
                or_(Movie.rating == None, Movie.rating == 0),
                or_(Movie.release_date == None, Movie.release_date == '')
            )
        ).order_by(Movie.id.desc())
        
        all_movies = query.all()
        
        # Filter out movies already checked
        movies_to_check = []
        for movie in all_movies:
            tmdb_str = str(movie.tmdb_id)
            # Skip if already checked or known to not be in OMDb
            if tmdb_str in tracking.get('checked_movies', {}) or \
               tmdb_str in tracking.get('not_found_in_omdb', []):
                continue
            movies_to_check.append(movie)
            if len(movies_to_check) >= args.limit:
                break
        
        print(f"\n📊 Found {len(movies_to_check)} NEW movies to check (skipped {len(all_movies) - len(movies_to_check)} already checked)")
        
        if len(movies_to_check) == 0:
            print("\n✅ All movies have been checked! Nothing to do.")
            print("   Run --check-status to see statistics")
            return
        
        print(f"\nStarting enrichment...\n")
        
        success = 0
        not_found = 0
        api_calls = 0
        
        for idx, movie in enumerate(movies_to_check, 1):
            print(f"[{idx}/{len(movies_to_check)}] {movie.title} (ID: {movie.id}, TMDB: {movie.tmdb_id})")
            
            missing_before = get_missing_fields(movie)
            if not missing_before:
                print("    ✓ Already complete")
                continue
            
            print(f"    Missing: {', '.join(missing_before)}")
            
            # Get IMDb ID from TMDB
            imdb_id = get_imdb_id_from_tmdb(movie.tmdb_id)
            if not imdb_id:
                print(f"    ⚠️ No IMDb ID found")
                tracking['checked_movies'][str(movie.tmdb_id)] = {
                    'status': 'no_imdb_id',
                    'date': datetime.now(timezone.utc).isoformat()
                }
                continue
            
            print(f"    IMDb ID: {imdb_id}")
            
            # Fetch from OMDb
            omdb_data = omdb_get(imdb_id)
            api_calls += 1
            tracking['total_api_calls'] += 1
            
            if omdb_data == 'NOT_FOUND':
                print(f"    ❌ Not found in OMDb")
                not_found += 1
                tracking['not_found_in_omdb'].append(str(movie.tmdb_id))
                tracking['checked_movies'][str(movie.tmdb_id)] = {
                    'status': 'not_found',
                    'date': datetime.now(timezone.utc).isoformat(),
                    'imdb_id': imdb_id
                }
            elif omdb_data:
                # Fill missing fields from OMDb
                updated = fill_from_omdb(movie, omdb_data)
                if updated:
                    movie.last_verified = datetime.now(timezone.utc)
                    db.session.commit()
                    success += 1
                    print(f"    ✅ Updated from OMDb")
                else:
                    print(f"    ℹ️ No new data in OMDb")
                
                tracking['checked_movies'][str(movie.tmdb_id)] = {
                    'status': 'checked',
                    'date': datetime.now(timezone.utc).isoformat(),
                    'imdb_id': imdb_id,
                    'had_data': updated
                }
            else:
                print(f"    ⚠️ OMDb API error")
            
            # Save tracking periodically (every 50 movies)
            if idx % 50 == 0:
                save_tracking(tracking)
                print(f"\n    💾 Progress saved ({api_calls} API calls used)\n")
            
            # Small delay to be nice to the API
            time.sleep(0.1)
        
        # Final save
        save_tracking(tracking)
        
        print("\n" + "=" * 70)
        print("📊 ENRICHMENT COMPLETE")
        print("=" * 70)
        print(f"✅ Successfully enriched: {success}")
        print(f"❌ Not found in OMDb: {not_found}")
        print(f"🔄 API calls this run: {api_calls}")
        print(f"🔄 Total API calls today: {tracking['total_api_calls']}")
        print(f"📝 Tracking saved to: {TRACKING_FILE}")
        print("=" * 70)
        
        if len(movies_to_check) == args.limit:
            print(f"\n💡 More movies available! Run again to continue:")
            print(f"   python scripts/smart_omdb_enrichment.py --limit {args.limit}")


if __name__ == '__main__':
    main()
