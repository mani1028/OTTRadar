#!/usr/bin/env python3
"""
Missing Movies Tracker - Identify and enrich movies not yet in database

Generates a JSON file of movies from TMDB that need to be added to our DB.
Helps with bulk enrichment of new discoveries.

Usage:
  python scripts/track_missing_movies.py --find nlimit 100 --save
  python scripts/track_missing_movies.py --load
  python scripts/track_missing_movies.py --enrich-missing --skip-ott
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, db
from models import Movie
import requests

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE = 'https://api.themoviedb.org/3'
BASE_DIR = Path(__file__).parent.parent
MISSING_MOVIES_FILE = BASE_DIR / 'missing_movies.json'


def tmdb_get(path, params=None, retries=2):
    """Fetch from TMDB with retry"""
    params = params or {}
    params['api_key'] = TMDB_API_KEY
    url = f"{TMDB_BASE}{path}"
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return None
        except:
            pass
    
    return None


def find_missing_from_tmdb_discover(years=None, limit=500):
    """
    Find movies in TMDB that aren't in our database
    
    Args:
        years: List of years to check (default: 2020-2024)
        limit: Max to find
    
    Returns:
        dict of {tmdb_id: {title, year, popularity}}
    """
    if years is None:
        years = [2024, 2023, 2022, 2021, 2020]
    
    missing_candidates = {}
    found_count = 0
    
    with app.app_context():
        existing_tmdb_ids = set(Movie.query.with_entities(Movie.tmdb_id).all())
        existing_tmdb_ids = {id[0] for id in existing_tmdb_ids if id[0]}
    
    print(f"📊 Checking TMDB... (existing DB: {len(existing_tmdb_ids)} movies)")
    
    for year in years:
        page = 1
        year_found = 0
        
        while found_count < limit and year_found < 100:
            params = {
                'language': 'en-US',
                'primary_release_year': year,
                'sort_by': 'popularity.desc',
                'page': page
            }
            
            results = tmdb_get('/discover/movie', params=params)
            if not results or not results.get('results'):
                break
            
            for movie in results['results']:
                tmdb_id = movie.get('id')
                
                # Skip if already in our DB
                if tmdb_id in existing_tmdb_ids:
                    continue
                
                found_count += 1
                year_found += 1
                
                missing_candidates[str(tmdb_id)] = {
                    'title': movie.get('title', 'Unknown'),
                    'year': year,
                    'popularity': movie.get('popularity', 0),
                    'release_date': movie.get('release_date'),
                    'tmdb_id': tmdb_id
                }
                
                if found_count >= limit:
                    break
            
            page += 1
            print(f"  ✓ Year {year}: found {year_found} missing movies")
        
        if found_count >= limit:
            break
    
    return missing_candidates


def save_missing_movies(missing_dict):
    """Save missing movies to JSON file"""
    data = {
        'last_updated': datetime.now().isoformat(),
        'total_missing': len(missing_dict),
        'movies': missing_dict
    }
    
    with open(MISSING_MOVIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Saved {len(missing_dict)} missing movies to {MISSING_MOVIES_FILE}")
    return len(missing_dict)


def load_missing_movies():
    """Load missing movies from JSON file"""
    if not MISSING_MOVIES_FILE.exists():
        print(f"❌ {MISSING_MOVIES_FILE} not found")
        return {}
    
    with open(MISSING_MOVIES_FILE) as f:
        data = json.load(f)
    
    return data.get('movies', {})


def enrich_missing_movies(skip_ott=True, limit=None):
    """
    Enrich missing movies (from JSON) without adding OTT links
    
    This enriches metadata for movies that will be added to DB
    but skips OTT enrichment until they're actually in the database.
    
    Args:
        skip_ott: If True, skip OTT link enrichment
        limit: Max movies to enrich
    """
    missing = load_missing_movies()
    
    if not missing:
        print("❌ No missing movies file. Run --find first")
        return
    
    print(f"\n📥 Found {len(missing)} missing movies to enrich")
    print(f"   Skipping OTT links: {skip_ott}")
    
    if skip_ott:
        print("\n⚠️  NOTE: OTT links will be enriched AFTER movies are added to DB")
        print("   This is because OTT links need to be stored as JSON in the database")
    
    # This would be used to preview/prepare enrichment
    # Full enrichment happens in enrich_metadata_trailers.py with --from-json flag
    
    count = 0
    for tmdb_id, info in list(missing.items())[:limit] if limit else list(missing.items()):
        count += 1
        title = info.get('title')
        tmdb_id_int = info.get('tmdb_id')
        
        print(f"\n[{count}] {title} (TMDB {tmdb_id_int})")
        
        # Fetch metadata from TMDB
        details = tmdb_get(f"/movie/{tmdb_id_int}", params={'language': 'en-US'})
        if details:
            overview = details.get('overview', '')[:500] + '...' if details.get('overview') else 'N/A'
            rating = details.get('vote_average', 0)
            print(f"    Rating: {rating}/10")
            print(f"    Overview: {overview}")
        else:
            print(f"    ❌ Not found on TMDB")


def show_missing_report():
    """Show summary of missing movies"""
    missing = load_missing_movies()
    
    if not missing:
        print("❌ No missing movies file. Run --find first")
        return
    
    print("\n" + "=" * 60)
    print("MISSING MOVIES REPORT")
    print("=" * 60)
    print(f"Total missing: {len(missing)}")
    
    # Sort by year (newest first)
    by_year = {}
    for tmdb_id, info in missing.items():
        year = info.get('year')
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(info)
    
    for year in sorted(by_year.keys(), reverse=True):
        movies = by_year[year]
        print(f"\n📅 Year {year}: {len(movies)} movies")
        for m in sorted(movies, key=lambda x: x.get('popularity', 0), reverse=True)[:5]:
            print(f"   ⭐ {m['title'][:40]:40s} | Pop: {m.get('popularity', 0):.1f}")
        if len(movies) > 5:
            print(f"   ... and {len(movies) - 5} more")
    
    print("\n" + "=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Track and manage missing movies')
    parser.add_argument('--find', type=int, metavar='LIMIT', help='Find N missing movies from TMDB')
    parser.add_argument('--save', action='store_true', help='Save found movies to JSON')
    parser.add_argument('--load', action='store_true', help='Load and show missing movies')
    parser.add_argument('--report', action='store_true', help='Show missing movies report')
    parser.add_argument('--enrich-missing', action='store_true', help='Enrich missing movies (preview)')
    parser.add_argument('--skip-ott', action='store_true', default=True, help='Skip OTT enrichment (default: True)')
    parser.add_argument('--limit', type=int, help='Limit enrichment to N movies')
    
    args = parser.parse_args()
    
    if not TMDB_API_KEY:
        print('❌ TMDB_API_KEY not found in .env')
        return
    
    if args.find and args.save:
        print(f"\n🔍 Finding {args.find} missing movies...")
        missing = find_missing_from_tmdb_discover(limit=args.find)
        count = save_missing_movies(missing)
        print(f"✅ Ready to enrich! Use: python enrich_metadata_trailers.py --from-json")
    
    elif args.load or args.report:
        show_missing_report()
    
    elif args.enrich_missing:
        enrich_missing_movies(skip_ott=args.skip_ott, limit=args.limit)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
