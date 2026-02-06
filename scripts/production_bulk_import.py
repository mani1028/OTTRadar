"""
PRODUCTION BULK IMPORTER - Safe & Idempotent
===============================================
Can be run multiple times safely:
- Checks for existing movies (no duplicates)
- Only adds NEW movies
- Updates existing movies' OTT availability
- Supports multiple languages/regions

Usage:
    python -m scripts.production_bulk_import --language te --region IN
    python -m scripts.production_bulk_import --language ta --region IN
    python -m scripts.production_bulk_import --language hi --region IN
"""

import requests
import os
import sys
import time
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ott_links import fetch_justwatch_links

# Fix encoding for Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

# Create session with automatic retries
def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 429]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

SESSION = create_session()

def fetch_movies_by_popularity(language='te', region='IN', max_pages=200):
    """
    Fetch movies by popularity for a specific language and region
    This is the SAFEST method - always gets the same core dataset
    
    Args:
        language: ISO 639-1 language code (te, ta, hi, ml, kn)
        region: ISO 3166-1 region code (IN, US, etc.)
        max_pages: Maximum pages to fetch (20 movies per page)
    """
    if not TMDB_API_KEY:
        print("❌ TMDB_API_KEY not configured in .env file")
        return []
    
    all_movies = []
    page = 1
    
    print(f"\n🎬 Fetching {language.upper()} movies from region {region}...")
    print(f"📄 Target: {max_pages} pages (up to {max_pages * 20} movies)\n")
    
    while page <= max_pages:
        try:
            url = f"{TMDB_BASE_URL}/discover/movie"
            params = {
                'api_key': TMDB_API_KEY,
                'with_original_language': language,
                'region': region,
                'with_runtime.gte': 60,  # Feature films only
                'sort_by': 'popularity.desc',
                'page': page
            }
            
            response = SESSION.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                print(f"   ℹ️ No more movies found at page {page}")
                break
            
            # Add language metadata
            for movie in results:
                movie['source_language'] = language
                movie['source_region'] = region
                movie['is_dubbed'] = False  # Original language movies
            
            all_movies.extend(results)
            
            # Progress every 10 pages
            if page % 10 == 0:
                print(f"   📦 Page {page}/{max_pages}: {len(results)} movies | Total: {len(all_movies)}")
            
            # Check if we've reached the end
            total_pages = data.get('total_pages', 1)
            if page >= total_pages:
                print(f"   ✅ Reached end at page {page} (all available pages fetched)")
                break
            
            page += 1
            time.sleep(0.3)  # Rate limit protection
            
        except requests.exceptions.Timeout:
            print(f"   ⏱️ Timeout on page {page}, retrying...")
            time.sleep(3)
            continue
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Error on page {page}: {str(e)[:80]}")
            time.sleep(3)
            continue
        except Exception as e:
            print(f"   ❌ Unexpected error on page {page}: {str(e)[:80]}")
            break
    
    print(f"\n✅ Fetched {len(all_movies)} {language.upper()} movies\n")
    return all_movies

def fetch_watch_providers(title, release_date, region='IN'):
    """
    Fetch OTT watch providers with deep links using JustWatch
    Returns dict with provider info and deep links
    """
    return fetch_justwatch_links(title, release_date, country=region)
def production_bulk_import(language='te', region='IN', max_pages=200):
    """
    PRODUCTION BULK IMPORT - Safe to run multiple times
    
    Features:
    - Checks for existing movies by tmdb_id (NO DUPLICATES)
    - Only adds NEW movies
    - Updates OTT availability for existing movies
    - Commits in batches (safe crash recovery)
    - Shows detailed progress
    
    Args:
        language: ISO 639-1 code (te, ta, hi, ml, kn)
        region: Region code (IN, US, etc.)
        max_pages: Pages to fetch (default 200 = 4000 movies)
    """
    from app import app
    from models import db, Movie
    
    with app.app_context():
        print("=" * 80)
        print("🚀 PRODUCTION BULK IMPORT")
        print("=" * 80)
        print(f"   Language: {language.upper()}")
        print(f"   Region: {region}")
        print(f"   Max Pages: {max_pages}")
        print(f"   Database: instance/ott_tracker.db")
        print(f"   Current Movies: {Movie.query.count()}")
        print("=" * 80)
        
        # Fetch movies from TMDB
        movies = fetch_movies_by_popularity(
            language=language,
            region=region,
            max_pages=max_pages
        )
        
        if not movies:
            print("❌ No movies fetched. Check your TMDB_API_KEY")
            return
        
        print(f"📥 Processing {len(movies)} movies...\n")
        
        # Stats
        stats = {
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        for idx, movie in enumerate(movies, 1):
            try:
                tmdb_id = movie.get('id')
                
                # Check if movie already exists
                existing = Movie.query.filter_by(tmdb_id=tmdb_id).first()
                
                if existing:
                    # UPDATE existing movie's OTT platforms
                    providers = fetch_watch_providers(movie.get('title', ''), movie.get('release_date', ''), region)
                    if providers:
                        existing.set_ott_platforms(providers)
                        existing.last_updated = datetime.now(timezone.utc)
                        stats['updated'] += 1
                    else:
                        stats['skipped'] += 1
                else:
                    # ADD new movie
                    providers = fetch_watch_providers(movie.get('title', ''), movie.get('release_date', ''), region)
                    
                    new_movie = Movie(
                        tmdb_id=tmdb_id,
                        title=movie.get('title', ''),
                        poster=f"https://image.tmdb.org/t/p/w500{movie.get('poster_path', '')}" if movie.get('poster_path') else '',
                        backdrop=f"https://image.tmdb.org/t/p/w1280{movie.get('backdrop_path', '')}" if movie.get('backdrop_path') else '',
                        overview=movie.get('overview', ''),
                        release_date=movie.get('release_date', ''),
                        rating=movie.get('vote_average', 0),
                        popularity=movie.get('popularity', 0),
                        language=language,
                        is_dubbed=movie.get('is_dubbed', False)
                    )
                    
                    new_movie.set_ott_platforms(providers)
                    db.session.add(new_movie)
                    stats['added'] += 1
                
                # Commit every 50 movies (crash recovery)
                if (stats['added'] + stats['updated']) % 50 == 0:
                    db.session.commit()
                    print(f"   💾 [{stats['added']} new | {stats['updated']} updated] {idx}/{len(movies)} processed ({idx/len(movies)*100:.1f}%)")
                
            except Exception as e:
                db.session.rollback()
                stats['errors'] += 1
                if stats['errors'] < 5:  # Only show first 5 errors
                    print(f"   ⚠️ Error processing movie {tmdb_id}: {str(e)[:60]}")
                continue
        
        # Final commit
        db.session.commit()
        
        # Final report
        print("\n" + "=" * 80)
        print("✅ IMPORT COMPLETED!")
        print("=" * 80)
        print(f"   ➕ New movies added: {stats['added']}")
        print(f"   🔄 Existing updated: {stats['updated']}")
        print(f"   ⏭️ Skipped (no changes): {stats['skipped']}")
        print(f"   ❌ Errors: {stats['errors']}")
        print(f"   📊 Total in database: {Movie.query.count()}")
        print("=" * 80)
        
        # Language breakdown
        print(f"\n📈 Database Breakdown:")
        for lang in ['te', 'ta', 'hi', 'ml', 'kn']:
            count = Movie.query.filter_by(language=lang).count()
            if count > 0:
                print(f"   {lang.upper()}: {count} movies")
        
        dubbed = Movie.query.filter_by(is_dubbed=True).count()
        with_ott = Movie.query.filter(Movie.ott_platforms != '{}', Movie.ott_platforms != '').count()
        print(f"   Dubbed: {dubbed} movies")
        print(f"   With OTT: {with_ott} movies")
        print("=" * 80)

def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(
        description='Production Bulk Importer - Safe to run multiple times'
    )
    parser.add_argument(
        '--language',
        default='te',
        choices=['te', 'ta', 'hi', 'ml', 'kn', 'en'],
        help='Language code (te=Telugu, ta=Tamil, hi=Hindi, ml=Malayalam, kn=Kannada)'
    )
    parser.add_argument(
        '--region',
        default='IN',
        help='Region code (default: IN for India)'
    )
    parser.add_argument(
        '--pages',
        type=int,
        default=200,
        help='Maximum pages to fetch (default: 200)'
    )
    
    args = parser.parse_args()
    
    production_bulk_import(
        language=args.language,
        region=args.region,
        max_pages=args.pages
    )

if __name__ == '__main__':
    main()
