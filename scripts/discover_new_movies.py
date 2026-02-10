#!/usr/bin/env python3
"""
Discover New Movies - Slow Growth Strategy
Uses TMDB Discover API to find new Telugu movies by year and language.
Prevents duplicates and enriches with metadata.

Usage:
  python scripts/discover_new_movies.py --year 2024 --limit 50
  python scripts/discover_new_movies.py --year 1990 --limit 30
  python scripts/discover_new_movies.py --language te --year 2023 --limit 100

SAFETY FEATURES FOR SERVER DEPLOYMENT:
  - Duplicate detection (UNIQUE constraint handling)
  - Concurrent run prevention (lock file)
  - Partial failure recovery (continues on individual errors)
  - Atomic batch operations (all or nothing per movie)
  - Detailed statistics (duplicates, failures, additions)
"""

import sys
import os
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime, timezone

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, db
from models import Movie
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Load TMDB API key
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
if not TMDB_API_KEY:
    logger.error("TMDB_API_KEY not found in .env")
    sys.exit(1)


TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_DISCOVER_URL = f"{TMDB_BASE_URL}/discover/movie"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Lock file for concurrent run prevention
LOCK_FILE = Path(__file__).parent.parent / 'discover_new_movies.lock'

# Discovery batch tracker - prevents re-discovering same movies
DISCOVERY_STATE_FILE = Path(__file__).parent.parent / 'discovery_state.json'

import json as json_module


def acquire_lock(timeout=3600):
    """
    Acquire lock to prevent concurrent runs
    
    Args:
        timeout: How long to wait for existing lock to release (seconds)
    
    Returns:
        bool: True if lock acquired, False if locked by another process
    """
    # Check if lock exists and is stale
    if LOCK_FILE.exists():
        lock_age = time.time() - LOCK_FILE.stat().st_mtime
        
        if lock_age < timeout:
            # Lock is recent, another process is running
            locked_at = datetime.fromtimestamp(LOCK_FILE.stat().st_mtime)
            logger.error(
                f"Another discovery process is running (lock since {locked_at}). "
                f"Aborting to prevent race conditions."
            )
            return False
        else:
            # Lock is stale, remove it
            logger.warning(f"Removing stale lock file (age: {lock_age}s)")
            LOCK_FILE.unlink()
    
    # Create lock file
    try:
        LOCK_FILE.write_text(f"Locked at {datetime.now().isoformat()}\n")
        return True
    except Exception as e:
        logger.error(f"Failed to create lock: {e}")
        return False


def release_lock():
    """Release lock after completion"""
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception as e:
        logger.warning(f"Failed to remove lock: {e}")


def get_discovery_state():
    """Load discovery state (track pagination offsets per year)"""
    if not DISCOVERY_STATE_FILE.exists():
        return {}
    
    try:
        with open(DISCOVERY_STATE_FILE) as f:
            return json_module.load(f)
    except Exception as e:
        logger.warning(f"Failed to load discovery state: {e}")
        return {}


def save_discovery_state(state):
    """Save discovery state for next batch"""
    try:
        with open(DISCOVERY_STATE_FILE, 'w') as f:
            json_module.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save discovery state: {e}")


def get_next_offset(year):
    """
    Get next page offset for a year to avoid duplicate discoveries
    
    State file tracks: {year: offset, year: offset...}
    Each batch fetches 50 movies, so offset += 1 per day
    """
    state = get_discovery_state()
    key = f"year_{year}"
    
    # Get current offset (default 0 if first time)
    current_offset = state.get(key, 0)
    
    # Return current offset and prepare next one
    next_offset = current_offset + 1
    
    # Safety: reset after 10 pages (200 movies) to avoid going too far
    if next_offset >= 10:
        logger.info(f"  Year {year}: Reset offset (cycled through {next_offset * 20} movies)")
        next_offset = 0
    
    # Save new offset for next run
    state[key] = next_offset
    save_discovery_state(state)
    
    return current_offset, next_offset


def tmdb_get(path, params, retries=3, backoff=1.0):
    """Fetch from TMDB with retry logic and exponential backoff"""
    params['api_key'] = TMDB_API_KEY
    url = f"{TMDB_BASE_URL}{path}"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 429:  # Rate limit
                wait_time = backoff * (2 ** attempt)
                logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except (requests.ConnectionError, requests.Timeout) as e:
            wait_time = backoff * (2 ** attempt)
            if attempt < retries - 1:
                logger.warning(f"Connection error: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed after {retries} attempts: {e}")
                return None
    
    return None


def get_movie_details(tmdb_id):
    """Fetch full movie details from TMDB"""
    time.sleep(1)  # Rate limiting delay
    
    result = tmdb_get(f"/movie/{tmdb_id}", {
        'language': 'en-US'
    }, retries=2)
    
    if not result:
        return None
    
    poster_path = result.get('poster_path')
    backdrop_path = result.get('backdrop_path')
    full_poster_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None
    full_backdrop_url = f"{TMDB_IMAGE_BASE}{backdrop_path}" if backdrop_path else None
    return {
        'tmdb_id': tmdb_id,
        'title': result.get('title', ''),
        'overview': result.get('overview', ''),
        'poster': full_poster_url,
        'backdrop': full_backdrop_url,
        'release_date': result.get('release_date', ''),
        'rating': result.get('vote_average', 0),
        'runtime': result.get('runtime', 0),
        'genres': ','.join([str(g.get('name', '')) for g in result.get('genres', [])]),
        'popularity': result.get('popularity', 0),
    }


def movie_exists(tmdb_id):
    """Check if movie already in database"""
    return Movie.query.filter_by(tmdb_id=tmdb_id).first() is not None


def add_movie_to_db(movie_data, is_dubbed=False):
    """
    Add new movie to database with duplicate handling
    
    Args:
        movie_data: Dict with movie info from TMDB
        is_dubbed: If True, marks movie as dubbed with Telugu audio
    
    Returns:
        tuple: (success: bool, reason: str)
        - (True, 'added') - Movie successfully inserted
        - (False, 'duplicate') - Movie already exists (constraint violation)
        - (False, 'error') - Database or other error
    """
    try:
        movie = Movie(
            tmdb_id=movie_data['tmdb_id'],
            title=movie_data['title'],
            overview=movie_data['overview'],
            poster=movie_data['poster'],
            backdrop=movie_data['backdrop'],
            release_date=movie_data['release_date'],
            rating=movie_data['rating'],
            runtime=movie_data['runtime'],
            genres=movie_data['genres'],
            popularity=movie_data['popularity'],
            language='te',  # Always Telugu for filtering
            media_type='movie',
            fetch_source='discover_api',
            is_active=True,
            is_dubbed=is_dubbed,  # Mark as dubbed if applicable
            has_telugu_audio=is_dubbed,  # Assume dubbed means Telugu audio
            created_at=datetime.now(timezone.utc),
            last_updated=datetime.now(timezone.utc)
        )
        db.session.add(movie)
        db.session.commit()
        return (True, 'added')
        
    except Exception as e:
        error_str = str(e)
        
        # Check for UNIQUE constraint violation (duplicate tmdb_id)
        if 'UNIQUE' in error_str or 'unique' in error_str:
            logger.debug(f"Duplicate entry for TMDB {movie_data['tmdb_id']}: {movie_data.get('title')}")
            db.session.rollback()
            return (False, 'duplicate')
        
        # Other database errors
        logger.error(f"Error adding movie {movie_data.get('title')} (TMDB {movie_data['tmdb_id']}): {e}")
        db.session.rollback()
        return (False, 'error')


def discover_movies(year=None, language='te', per_page=20, max_pages=3):
    """
    Discover new movies using TMDB Discover API with smart pagination
    
    SMART OFFSET TRACKING:
    - Tracks last pagination offset per year
    - Each day fetches NEXT batch (not same 20 movies again)
    - Rotates through TMDB results over 10 days (~200 movies per year)
    - Then resets for next year
    
    Args:
        year: Release year (e.g., 2024)
        language: ISO 639-1 language code (e.g., 'te' for Telugu, 'hi' for Hindi)
        per_page: Results per page (max 20)
        max_pages: How many pages to fetch (1 page = 20 movies)
    
    Returns:
        List of discovered movie TMDb IDs (hopefully new ones)
    """
    discovered = []
    
    # Get smart pagination offset for this year
    current_offset, next_offset = get_next_offset(year if year else 0)
    start_page = current_offset + 1  # Pages are 1-indexed
    
    lang_name = {'te': 'Telugu', 'hi': 'Hindi', 'ta': 'Tamil', 'ml': 'Malayalam', 'en': 'English'}.get(language, language.upper())
    logger.info(f"[DISCOVER] {lang_name}, year={year}, offset={current_offset}, fetching pages {start_page}-{start_page + max_pages - 1}")
    
    params = {
        'sort_by': 'release_date.desc',
        'with_original_language': language,
        'per_page': per_page,
    }
    
    if year:
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"
        params['release_date.gte'] = year_start
        params['release_date.lte'] = year_end
    
    # Fetch from offset position (not page 1)
    for relative_page in range(max_pages):
        page_num = start_page + relative_page
        params['page'] = page_num
        
        logger.info(f"  Fetching page {page_num} (offset {current_offset + relative_page})...")
        result = tmdb_get('/discover/movie', params)
        
        if not result or 'results' not in result:
            logger.error(f"  Failed to fetch page {page_num}")
            break
        
        movies = result.get('results', [])
        if not movies:
            logger.info(f"  No more movies found at page {page_num}")
            break
        
        for movie in movies:
            tmdb_id = movie.get('id')
            title = movie.get('title', 'Unknown')
            
            if movie_exists(tmdb_id):
                logger.debug(f"  [DUP] {title} (ID: {tmdb_id}) - Already exists")
                continue
            
            discovered.append(tmdb_id)
            logger.info(f"  [NEW] {title} (ID: {tmdb_id})")
            time.sleep(0.5)  # Don't hammer API
        
        time.sleep(2)  # Delay between pages
    
    return discovered



def main():
    parser = argparse.ArgumentParser(
        description='Discover new movies from TMDB and add to database'
    )
    parser.add_argument('--year', type=int, help='Release year (e.g., 2024)')
    parser.add_argument('--language', default='te', help='Language code (default: te for Telugu)')
    parser.add_argument('--limit', type=int, default=50, help='Max movies to add (default: 50)')
    parser.add_argument('--pages', type=int, default=3, help='Max pages to fetch (default: 3 = 60 movies)')
    parser.add_argument('--force', action='store_true', help='Re-fetch movies that already exist')
    parser.add_argument('--dubbed', action='store_true', help='Mark as dubbed with Telugu audio (for Hindi/Tamil/etc)')
    parser.add_argument('--import-from-json', action='store_true', help='Import from missing_movies.json (created by track_missing_movies.py)')
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("[TMDB DISCOVER] New Movie Discovery")
    print("="*70)
    
    # Handle --import-from-json mode
    if args.import_from_json:
        print("Mode: IMPORT FROM missing_movies.json")
        missing_movies_file = Path(__file__).parent.parent / 'missing_movies.json'
        
        if not missing_movies_file.exists():
            print(f"❌ File not found: {missing_movies_file}")
            print("   Run: python scripts/track_missing_movies.py --find 100 --save")
            sys.exit(1)
        
        try:
            with open(missing_movies_file, 'r', encoding='utf-8') as f:
                missing_data = json_module.load(f)
            
            # movies can be a dict or list depending on how it was saved
            movies_raw = missing_data.get('movies', [])
            
            # Convert dict to list of values if needed
            if isinstance(movies_raw, dict):
                movies_to_import = list(movies_raw.values())
            else:
                movies_to_import = movies_raw if isinstance(movies_raw, list) else []
            
            print(f"Found: {len(movies_to_import)} movies to import")
            print("="*70)
            
            if not movies_to_import:
                print("❌ No movies found in missing_movies.json")
                sys.exit(1)
            
            if not acquire_lock():
                print("\n⚠️  Another process is already running.")
                sys.exit(1)
            
            try:
                with app.app_context():
                    stats = {
                        'processed': 0,
                        'added': 0,
                        'duplicates': 0,
                        'fetch_failed': 0,
                        'db_error': 0
                    }
                    
                    # Limit to --limit flag (default 50)
                    movies_to_process = movies_to_import[:args.limit]
                    
                    for movie_data in movies_to_process:
                        tmdb_id = movie_data.get('tmdb_id') or movie_data.get('id')
                        title = movie_data.get('title', 'Unknown')
                        
                        stats['processed'] += 1
                        
                        # Fetch full details from TMDB
                        details = get_movie_details(tmdb_id)
                        
                        if not details:
                            logger.warning(f"Failed to fetch details for {title} (TMDB {tmdb_id})")
                            stats['fetch_failed'] += 1
                            continue
                        
                        # Try to add to database
                        success, reason = add_movie_to_db(details, is_dubbed=args.dubbed)
                        
                        if success:
                            dubbed_label = " (DUBBED)" if args.dubbed else ""
                            print(f"✅ Added: {title}{dubbed_label}")
                            stats['added'] += 1
                        elif reason == 'duplicate':
                            print(f"⚠️  Already exists: {title}")
                            stats['duplicates'] += 1
                        else:
                            print(f"❌ Database error: {title}")
                            stats['db_error'] += 1
                        
                        time.sleep(0.5)  # Rate limit
                    
                    # Summary
                    print("\n" + "="*70)
                    print("[SUMMARY] Import Results")
                    print("="*70)
                    print(f"Processed:        {stats['processed']}")
                    print(f"  ✅ Added:       {stats['added']} (NEW)")
                    print(f"  ⚠️  Duplicates: {stats['duplicates']} (already exist)")
                    print(f"  ❌ Failed:      {stats['fetch_failed'] + stats['db_error']}")
                    print("="*70)
                    
                    total_movies = Movie.query.count()
                    print(f"\nDatabase now contains: {total_movies:,} movies")
                    
                    if stats['added'] > 0:
                        print(f"✅ SUCCESS: Added {stats['added']} new movies")
                    else:
                        print("⚠️  No new movies added")
                    
                    print("="*70 + "\n")
            finally:
                release_lock()
        
        except json_module.JSONDecodeError as e:
            print(f"❌ Error reading JSON file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        return
    
    print(f"Year: {args.year if args.year else 'Any'}")
    print(f"Language: {args.language}")
    print(f"Target: {args.limit} new movies")
    print("="*70)
    
    # Prevent concurrent runs on server
    if not acquire_lock():
        print("\n⚠️  Another discovery process is already running.")
        print("Skipping to prevent race conditions and duplicate inserts.")
        sys.exit(1)
    
    try:
        with app.app_context():
            # Discover new movies
            discovered = discover_movies(
                year=args.year,
                language=args.language,
                max_pages=args.pages,
                per_page=min(20, args.limit // args.pages + 1)
            )
            
            if not discovered:
                logger.info("\n✗ No new movies discovered")
                print("\n" + "="*70)
                print("[DONE] No new movies found in TMDB")
                print("="*70)
                return
            
            logger.info(f"\n[STATS] Discovered {len(discovered)} new TMDb IDs. Fetching details...")
            
            # Statistics tracking
            stats = {
                'discovered': len(discovered),
                'added': 0,
                'duplicates': 0,
                'fetch_failed': 0,
                'db_error': 0,
                'processed': 0
            }
            
            for i, tmdb_id in enumerate(discovered[:args.limit], 1):
                print(f"\n[{i}/{min(args.limit, len(discovered))}] Fetching movie {tmdb_id}...")
                
                details = get_movie_details(tmdb_id)
                stats['processed'] += 1
                
                if not details:
                    logger.warning(f"Failed to fetch details for TMDB ID {tmdb_id}")
                    stats['fetch_failed'] += 1
                    continue
                
                # Try to add to database
                success, reason = add_movie_to_db(details, is_dubbed=args.dubbed)
                
                if success:
                    dubbed_label = " (HINDI DUBBED)" if args.dubbed else ""
                    logger.info(f"[NEW] Added: {details['title']}{dubbed_label}")
                    stats['added'] += 1
                elif reason == 'duplicate':
                    logger.info(f"[DUP] Already exists: {details['title']} (TMDB {tmdb_id})")
                    stats['duplicates'] += 1
                else:  # reason == 'error'
                    logger.error(f"[ERR] Database error: {details['title']}")
                    stats['db_error'] += 1
            
            # Final summary report
            print("\n" + "="*70)
            print("[SUMMARY] Movie Discovery Results")
            print("="*70)
            print(f"Discovered from TMDB:  {stats['discovered']}")
            print(f"Details fetched:       {stats['processed']}")
            print(f"  |- Successfully added: {stats['added']} (NEW)")
            print(f"  |- Already existed:    {stats['duplicates']} (DUP)")
            print(f"  |- Fetch failed:       {stats['fetch_failed']} (ERR)")
            print(f"  |- DB errors:          {stats['db_error']} (ERR)")
            print("="*70)
            
            # Database size update
            total_movies = Movie.query.count()
            print(f"\nDatabase now contains: {total_movies:,} total movies")
            
            if stats['added'] > 0:
                print(f"SUCCESS: Imported {stats['added']} new movies")
            else:
                print("WARNING: No new movies were added (duplicates or errors)")
            
            print("="*70 + "\n")
    
    finally:
        # Always release lock, even if error occurs
        release_lock()


if __name__ == '__main__':
    main()
