#!/usr/bin/env python3
"""
Enrich movie metadata, trailer links, and OTT platform availability from TMDB.

Enriches:
  - Metadata: overview, poster, backdrop, runtime, genres, rating, popularity, release_date
  - Trailers: YouTube trailer IDs
  - Cast & Certification: Actor names and ratings
  - OTT Platforms: Available streaming platforms (Netflix, Prime, Hotstar, etc.)

Usage:
  python scripts/enrich_metadata_trailers.py --limit 25
  python scripts/enrich_metadata_trailers.py --all
  python scripts/enrich_metadata_trailers.py --force
"""

import os
import sys
import time
import json
import argparse
import requests
from sqlalchemy import or_
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Movie
from dotenv import load_dotenv
from scripts.ott_link_builder import OTT_SEARCH_URLS, get_platform_display_name
from urllib.parse import quote

load_dotenv()

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
OMDB_API_KEY = os.getenv('OMDB_API_KEY', '5cad8aea')  # OMDb API for missing data
TMDB_BASE = 'https://api.themoviedb.org/3'
OMDB_BASE = 'http://www.omdbapi.com/'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSING_REPORT_PATH = os.path.join(BASE_DIR, 'enrichment_missing_fields.json')

DETAILS_FIELDS = {
    'overview',
    'poster',
    'backdrop',
    'runtime',
    'genres',
    'rating',
    'popularity',
    'release_date'
}

# OTT Platform mapping from TMDB provider names
OTT_PLATFORM_MAP = {
    'Netflix': 'netflix',
    'Amazon Prime Video': 'prime',
    'Amazon Video': 'prime',
    'Prime Video': 'prime',
    'Disney Plus': 'disney',
    'Disney+': 'disney',
    'Hotstar': 'hotstar',
    'Jio Cinema': 'jiocinema',
    'JioCinema': 'jiocinema',
    'ZEE5': 'zee5',
    'Zee5': 'zee5',
    'Apple TV Plus': 'apple',
    'Apple TV': 'apple',
    'YouTube': 'youtube',
    'Airtel Xstream': 'airtel',
    'Airtel': 'airtel',
    'Voot': 'voot',
    'MX Player': 'mx_player',
    'SonyLIV': 'sony_liv'
}


def tmdb_get(path, params=None, retries=3, backoff=1.0):
    """Fetch from TMDB with exponential backoff retry"""
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
            if response.status_code == 401:
                raise RuntimeError("TMDB 401: Invalid API key")
            if response.status_code == 429:
                wait_time = backoff * (2 ** attempt)
                print(f"    ⏳ Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            # Other bad status
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise RuntimeError(f"TMDB {response.status_code}")
        except (requests.ConnectionError, requests.Timeout, ConnectionResetError) as e:
            if attempt < retries - 1:
                wait_time = backoff * (2 ** attempt)
                time.sleep(wait_time)
                continue
            return None
    return None


def pick_trailer(videos):
    if not videos:
        return None
    items = videos.get('results', [])
    # Prefer YouTube Trailer, then Teaser
    for kind in ('Trailer', 'Teaser'):
        for v in items:
            if v.get('site') == 'YouTube' and v.get('type') == kind and v.get('key'):
                return v.get('key')
    return None


def pick_cast(credits, limit=12):
    if not credits:
        return ''
    cast = credits.get('cast', [])
    names = [c.get('name') for c in cast if c.get('name')]
    return ', '.join(names[:limit])


def pick_certification(release_dates, country_order=('IN', 'US')):
    if not release_dates:
        return ''
    results = release_dates.get('results', [])
    by_country = {r.get('iso_3166_1'): r for r in results}
    for country in country_order:
        entry = by_country.get(country)
        if not entry:
            continue
        for item in entry.get('release_dates', []):
            cert = item.get('certification')
            if cert:
                return cert
    return ''


def pick_ott_release_date(release_dates, country_order=('IN', 'US')):
    """Extract OTT/Digital release date from TMDB release_dates endpoint
    
    Args:
        release_dates: Response from /movie/{id}/release_dates
        country_order: Tuple of country codes to check in order
    
    Returns:
        str: OTT release date in YYYY-MM-DD format or empty string
    
    Release type codes from TMDB:
        1 = Premiere
        2 = Theatrical (limited)
        3 = Theatrical
        4 = Digital (VOD/Streaming) ← This is what we want for OTT
        5 = Physical (DVD/Blu-ray)
        6 = TV
    """
    if not release_dates:
        return ''
    
    results = release_dates.get('results', [])
    by_country = {r.get('iso_3166_1'): r for r in results}
    
    for country in country_order:
        entry = by_country.get(country)
        if not entry:
            continue
        
        # Look for Digital/Streaming release (type 4)
        for item in entry.get('release_dates', []):
            release_type = item.get('type')
            release_date = item.get('release_date')
            
            # Type 4 = Digital (OTT/VOD/Streaming)
            if release_type == 4 and release_date:
                # Extract date part (YYYY-MM-DD) from datetime string
                try:
                    date_part = release_date.split('T')[0]
                    return date_part
                except:
                    pass
    
    return ''


def omdb_get(imdb_id, retries=3, backoff=1.0):
    """Fetch movie data from OMDb API using IMDb ID
    
    Args:
        imdb_id: IMDb ID (e.g., 'tt1234567')
        retries: Number of retry attempts
        backoff: Initial backoff time in seconds
    
    Returns:
        dict: OMDb response data or None if failed
    """
    if not OMDB_API_KEY:
        return None
    
    if not imdb_id or not imdb_id.startswith('tt'):
        return None
    
    params = {
        'i': imdb_id,
        'apikey': OMDB_API_KEY,
        'plot': 'full'  # Get full plot
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(OMDB_BASE, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('Response') == 'True':
                    return data
                return None
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            return None
        except (requests.ConnectionError, requests.Timeout, ConnectionResetError) as e:
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            return None
    return None


def get_imdb_id_from_tmdb(tmdb_id):
    """Get IMDb ID for a TMDB movie
    
    Args:
        tmdb_id: TMDB movie ID
    
    Returns:
        str: IMDb ID (e.g., 'tt1234567') or None
    """
    external_ids = tmdb_get(f"/movie/{tmdb_id}/external_ids", retries=2)
    if external_ids:
        return external_ids.get('imdb_id')
    return None


def fill_from_omdb(movie, omdb_data, force=False):
    """Fill missing movie fields from OMDb data
    
    Args:
        movie: Movie model instance
        omdb_data: OMDb API response dict
        force: Whether to overwrite existing data
    
    Returns:
        bool: True if any field was updated
    """
    if not omdb_data:
        return False
    
    updated = False
    
    # Overview (Plot)
    if (force or not movie.overview) and omdb_data.get('Plot') and omdb_data.get('Plot') != 'N/A':
        movie.overview = omdb_data['Plot']
        updated = True
    
    # Poster
    if (force or not movie.poster) and omdb_data.get('Poster') and omdb_data.get('Poster') != 'N/A':
        movie.poster = omdb_data['Poster']
        updated = True
    
    # Runtime
    if (force or not movie.runtime or movie.runtime == 0) and omdb_data.get('Runtime'):
        runtime_str = omdb_data['Runtime'].replace(' min', '').strip()
        try:
            movie.runtime = int(runtime_str)
            updated = True
        except ValueError:
            pass
    
    # Genres
    if (force or not movie.genres) and omdb_data.get('Genre') and omdb_data.get('Genre') != 'N/A':
        movie.genres = omdb_data['Genre'].replace(', ', ', ')  # Already comma-separated
        updated = True
    
    # Cast (Actors)
    if (force or not movie.cast) and omdb_data.get('Actors') and omdb_data.get('Actors') != 'N/A':
        movie.cast = omdb_data['Actors']
        updated = True
    
    # Certification (Rated)
    if (force or not movie.certification) and omdb_data.get('Rated') and omdb_data.get('Rated') != 'N/A':
        movie.certification = omdb_data['Rated']
        updated = True
    
    # Release Date (Released)
    if (force or not movie.release_date) and omdb_data.get('Released') and omdb_data.get('Released') != 'N/A':
        try:
            # OMDb format: '14 Jan 2011'
            from datetime import datetime as dt
            release_obj = dt.strptime(omdb_data['Released'], '%d %b %Y')
            movie.release_date = release_obj.strftime('%Y-%m-%d')
            updated = True
        except Exception:
            pass
    
    # Rating (IMDb Rating)
    if (force or not movie.rating or movie.rating == 0) and omdb_data.get('imdbRating'):
        try:
            imdb_rating = float(omdb_data['imdbRating'])
            if imdb_rating > 0:
                movie.rating = imdb_rating
                updated = True
        except ValueError:
            pass
    
    return updated


def pick_ott_platforms(watch_providers, movie_title='', countries=('IN',)):
    """Extract OTT platforms from TMDB watch/providers endpoint
    
    Args:
        watch_providers: Response from /movie/{id}/watch/providers
        movie_title: Movie title for fallback search URL generation
        countries: Tuple of country codes to check (default: India only)
    
    Returns:
        dict: {platform_name: {
            'provider_name': '...',
            'provider_id': ...,
            'logo_path': '...',
            'country': '...',
            'fallback_search_url': '...'  ← Automatic fallback
        }}
    """
    if not watch_providers:
        return {}
    
    results = watch_providers.get('results', {})
    ott_data = {}
    
    for country_code in countries:
        country_data = results.get(country_code)
        if not country_data:
            continue
        
        # Priority: Subscription (flatrate) > Rent > Buy
        providers_list = (
            country_data.get('flatrate', []) or
            country_data.get('rent', []) or
            country_data.get('buy', [])
        )
        
        for provider in providers_list:
            provider_name = provider.get('provider_name', '')
            provider_id = provider.get('provider_id')
            logo_path = provider.get('logo_path')
            
            if not provider_name:
                continue
            
            # Map to normalized platform name
            normalized_name = OTT_PLATFORM_MAP.get(provider_name, provider_name.lower().replace(' ', '_'))
            
            # Only add if not already present (subscription takes priority)
            if normalized_name not in ott_data:
                ott_entry = {
                    'provider_name': provider_name,
                    'provider_id': provider_id,
                    'logo_path': f"https://image.tmdb.org/t/p/original{logo_path}" if logo_path else None,
                    'country': country_code
                }
                
                # Add fallback search URL automatically
                if movie_title and normalized_name in OTT_SEARCH_URLS:
                    fallback_url = OTT_SEARCH_URLS[normalized_name].format(query=quote(movie_title))
                    ott_entry['fallback_search_url'] = fallback_url
                
                ott_data[normalized_name] = ott_entry
    
    return ott_data


def get_missing_fields(movie):
    missing = []
    if not movie.overview:
        missing.append('overview')
    if not movie.poster:
        missing.append('poster')
    if not movie.backdrop:
        missing.append('backdrop')
    if not movie.runtime or movie.runtime == 0:
        missing.append('runtime')
    if not movie.genres:
        missing.append('genres')
    if not movie.cast:
        missing.append('cast')
    if not movie.certification:
        missing.append('certification')
    if not movie.youtube_trailer_id:
        missing.append('youtube_trailer_id')
    if not movie.release_date:
        missing.append('release_date')
    if not movie.rating or movie.rating == 0:
        missing.append('rating')
    if not movie.popularity or movie.popularity == 0:
        missing.append('popularity')
    # Check for missing OTT platforms
    ott_data = movie.get_ott_platforms()
    if not ott_data:
        missing.append('ott_platforms')
    return missing


def write_missing_report(movies, path):
    missing_by_id = {}
    complete_ids = []
    for movie in movies:
        missing = get_missing_fields(movie)
        if missing:
            missing_by_id[str(movie.tmdb_id)] = missing
        else:
            complete_ids.append(movie.tmdb_id)

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_movies': len(movies),
        'complete_tmdb_ids': complete_ids,
        'missing_by_tmdb_id': missing_by_id
    }

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=True, indent=2)
    return missing_by_id, complete_ids


def enrich_movie(movie, force=False, skip_ott=False, use_omdb=False):
    print(f"\n[{movie.id}] {movie.title} - TMDB {movie.tmdb_id}")

    if not movie.tmdb_id:
        print("    ⚠ No TMDB ID - skipping")
        return False

    missing = get_missing_fields(movie)
    if not force and not missing:
        print("    ℹ Already complete - skipping")
        return False

    if movie.youtube_trailer_id and not movie.trailer:
        movie.trailer = f"https://www.youtube.com/watch?v={movie.youtube_trailer_id}"
        db.session.commit()

    details = None
    if force or (set(missing) & DETAILS_FIELDS):
        details = tmdb_get(f"/movie/{movie.tmdb_id}", params={'language': 'en-US'})
        if not details:
            print("    ⚠ TMDB movie not found")
            return False

    updated = False

    if details and (force or not movie.overview):
        overview = details.get('overview')
        if overview:
            movie.overview = overview
            updated = True
    if details and (force or not movie.poster):
        poster_path = details.get('poster_path')
        if poster_path:
            movie.poster = f"https://image.tmdb.org/t/p/w500{poster_path}"
            updated = True
    if details and (force or not movie.backdrop):
        backdrop_path = details.get('backdrop_path')
        if backdrop_path:
            movie.backdrop = f"https://image.tmdb.org/t/p/w780{backdrop_path}"
            updated = True
    if details and (force or not movie.runtime):
        runtime = details.get('runtime') or 0
        if runtime:
            movie.runtime = runtime
            updated = True
    if details and (force or not movie.genres):
        genres = details.get('genres') or []
        genre_list = [g.get('name') for g in genres if g.get('name')]
        if genre_list:
            movie.genres = ', '.join(genre_list)
            updated = True
    if details and (force or not movie.rating):
        rating = details.get('vote_average') or 0
        if rating:
            movie.rating = float(rating)
            updated = True
    if details and (force or not movie.popularity):
        popularity = details.get('popularity') or 0
        if popularity:
            movie.popularity = float(popularity)
            updated = True
    if details and (force or not movie.release_date):
        release_date = details.get('release_date')
        if release_date:
            movie.release_date = release_date
            updated = True

    if force or not movie.cast:
        credits = tmdb_get(f"/movie/{movie.tmdb_id}/credits", retries=2)
        if credits:
            cast_names = pick_cast(credits)
            if cast_names:
                movie.cast = cast_names
                updated = True

    if force or not movie.certification:
        release_dates = tmdb_get(f"/movie/{movie.tmdb_id}/release_dates", retries=2)
        if release_dates:
            certification = pick_certification(release_dates)
            if certification:
                movie.certification = certification
                updated = True
            
            # Also extract OTT release date from the same API call
            if force or not movie.ott_release_date:
                ott_release_date = pick_ott_release_date(release_dates)
                if ott_release_date:
                    movie.ott_release_date = ott_release_date
                    updated = True
                    print(f"    📅 OTT Release: {ott_release_date}")

    if force or not movie.youtube_trailer_id:
        videos = tmdb_get(f"/movie/{movie.tmdb_id}/videos", params={'language': 'en-US'}, retries=2)
        if videos:
            trailer_key = pick_trailer(videos)
            if trailer_key:
                movie.youtube_trailer_id = trailer_key
                movie.trailer = f"https://www.youtube.com/watch?v={trailer_key}"
                updated = True

    # Fetch OTT platforms from TMDB watch/providers
    ott_data = movie.get_ott_platforms()
    if not skip_ott and (force or not ott_data):
        watch_providers = tmdb_get(f"/movie/{movie.tmdb_id}/watch/providers", retries=2)
        if watch_providers:
            new_ott_data = pick_ott_platforms(watch_providers, movie_title=movie.title, countries=('IN', 'US'))
            if new_ott_data:
                # Merge with existing OTT data (preserve existing entries)
                if ott_data:
                    # Keep any existing OTT entries and add new ones from TMDB
                    for platform, info in new_ott_data.items():
                        if platform not in ott_data:
                            ott_data[platform] = info
                else:
                    ott_data = new_ott_data
                
                movie.set_ott_platforms(ott_data)
                updated = True
                # Show platform names with link type indicator
                platform_names = []
                for platform_key, platform_info in ott_data.items():
                    # Check if we have a direct URL or fallback search URL
                    if platform_info.get('fallback_search_url'):
                        platform_names.append(f"{platform_key} (search link)")
                    else:
                        platform_names.append(platform_key)
                platform_list = ', '.join(platform_names)
                print(f"    📺 Found OTT platforms: {platform_list}")
                if any('search link' in p for p in platform_names):
                    print(f"    ℹ️  'search link' = Opens search page (no direct link available)")

    # OMDb API fallback for missing fields
    # Only use if explicitly enabled (--use-omdb flag) to manage rate limit (1000/day)
    # Strategy: Run TMDB enrichment first (--all), then check missing fields,
    # then run OMDb enrichment only on missing data (--use-omdb --limit <count>)
    missing_after_tmdb = get_missing_fields(movie)
    critical_missing = {'overview', 'poster', 'runtime', 'genres', 'cast', 'certification', 'rating', 'release_date'}
    
    if use_omdb and (set(missing_after_tmdb) & critical_missing):
        # Try to get IMDb ID and fetch from OMDb
        imdb_id = get_imdb_id_from_tmdb(movie.tmdb_id)
        if imdb_id:
            omdb_data = omdb_get(imdb_id)
            if omdb_data:
                omdb_updated = fill_from_omdb(movie, omdb_data, force=force)
                if omdb_updated:
                    updated = True
                    print(f"    🎬 Filled gaps from OMDb (IMDb: {imdb_id})")

    if updated:
        movie.last_verified = datetime.now(timezone.utc)
        db.session.commit()
        status_msg = "✅ Updated metadata/trailer/OTT platforms"
        if use_omdb and missing_after_tmdb and (set(missing_after_tmdb) & critical_missing):
            status_msg += " (+ OMDb)"
        print(f"    {status_msg}")
        return True

    print("    ℹ No updates needed")
    return False


def main():
    parser = argparse.ArgumentParser(description='Enrich movie metadata and trailer links from TMDB')
    parser.add_argument('--limit', type=int, help='Limit number of movies to process')
    parser.add_argument('--all', action='store_true', help='Process all movies')
    parser.add_argument('--force', action='store_true', help='Overwrite existing metadata')
    parser.add_argument('--from-json', action='store_true', help='Enrich movies from missing_movies.json')
    parser.add_argument('--skip-ott', action='store_true', help='Skip OTT link enrichment')
    parser.add_argument('--use-omdb', action='store_true', help='Use OMDb API to fill gaps (after TMDB). Rate limit: 1000/day')
    parser.add_argument('--start-id', type=int, help='Start processing from this movie ID (goes backwards if --reverse)')
    parser.add_argument('--reverse', action='store_true', help='Process in reverse order (descending ID)')
    args = parser.parse_args()

    if not TMDB_API_KEY:
        print('❌ ERROR: TMDB_API_KEY not found in .env file')
        return

    try:
        tmdb_get('/configuration')
    except Exception as exc:
        print(f"❌ ERROR: TMDB auth failed: {exc}")
        return

    limit = None if args.all else (args.limit or 25)

    with app.app_context():
        # Handle --from-json mode (enrich from missing_movies.json)
        if args.from_json:
            missing_movies_file = os.path.join(BASE_DIR, 'missing_movies.json')
            if not os.path.exists(missing_movies_file):
                print(f"❌ {missing_movies_file} not found. Run: python scripts/track_missing_movies.py --find 100 --save")
                return
            
            try:
                with open(missing_movies_file) as f:
                    data = json.load(f)
                missing_movies = data.get('movies', {})
            except Exception as e:
                print(f"❌ Error reading {missing_movies_file}: {e}")
                return
            
            # Create Movie objects from missing movies data (don't save yet)
            movies_to_process = []
            for tmdb_id_str, info in missing_movies.items():
                try:
                    tmdb_id = int(tmdb_id_str)
                    # Create in-memory Movie object for enrichment preview
                    movie = Movie()
                    movie.tmdb_id = tmdb_id
                    movie.title = info.get('title', 'Unknown')
                    movies_to_process.append(movie)
                except:
                    pass
            
            print("=" * 60)
            print("ENRICHMENT: MISSING MOVIES (from missing_movies.json)")
            print("=" * 60)
            print(f"📊 Movies to enrich: {len(movies_to_process)}")
            print(f"⚠️  Mode: Preview only (not saving to DB)")
            print(f"🚫 OTT links: {'SKIPPED' if args.skip_ott else 'INCLUDED'}")
            print("=" * 60)
            
            success = 0
            for movie in movies_to_process[:limit] if limit else movies_to_process:
                try:
                    print(f"\n[{movie.tmdb_id}] {movie.title}")
                    # Fetch details to preview
                    details = tmdb_get(f"/movie/{movie.tmdb_id}", params={'language': 'en-US'})
                    if not details:
                        print("    ⚠ Not found on TMDB")
                        continue
                    
                    overview = details.get('overview', '')[:100] + '...' if details.get('overview') else 'N/A'
                    rating = details.get('vote_average', 0)
                    popularity = details.get('popularity', 0)
                    print(f"    Rating: {rating}/10 | Popularity: {popularity:.1f}")
                    print(f"    Overview: {overview}")
                    success += 1
                except Exception as exc:
                    print(f"    ✗ Error: {exc}")
            
            print("\n" + "=" * 60)
            print(f"PREVIEW: {success} movies ready to add")
            print("Next step: Run: python scripts/discover_new_movies.py")
            print("          (to actually add them to the database)")
            print("=" * 60)
            return
        
        # Regular mode: enrich movies in DB
        query = Movie.query.filter(Movie.tmdb_id != None)
        
        # Handle --start-id for starting from specific movie
        if args.start_id:
            if args.reverse:
                # Go backwards from start_id
                query = query.filter(Movie.id <= args.start_id)
                query = query.order_by(Movie.id.desc())
                print(f"📍 Starting from Movie ID {args.start_id}, going BACKWARDS (reverse order)")
            else:
                # Go forwards from start_id
                query = query.filter(Movie.id >= args.start_id)
                query = query.order_by(Movie.id.asc())
                print(f"📍 Starting from Movie ID {args.start_id}, going FORWARDS (normal order)")
        else:
            # Default: order by last_updated (desc)
            query = query.order_by(Movie.last_updated.desc())
        
        if not args.force:
            missing_conditions = [
                or_(Movie.overview == None, Movie.overview == ''),
                or_(Movie.poster == None, Movie.poster == ''),
                or_(Movie.backdrop == None, Movie.backdrop == ''),
                or_(Movie.runtime == None, Movie.runtime == 0),
                or_(Movie.genres == None, Movie.genres == ''),
                or_(Movie.cast == None, Movie.cast == ''),
                or_(Movie.certification == None, Movie.certification == ''),
                or_(Movie.youtube_trailer_id == None, Movie.youtube_trailer_id == ''),
                or_(Movie.release_date == None, Movie.release_date == ''),
                or_(Movie.rating == None, Movie.rating == 0),
                or_(Movie.popularity == None, Movie.popularity == 0)
            ]
            query = query.filter(or_(*missing_conditions))

        if limit:
            query = query.limit(limit)
        movies = query.all()

        missing_by_id, complete_ids = write_missing_report(movies, MISSING_REPORT_PATH)

        if args.force:
            movies_to_process = movies
        else:
            movies_to_process = [m for m in movies if str(m.tmdb_id) in missing_by_id]

        print("=" * 60)
        print("METADATA + TRAILER ENRICHMENT (TMDB + OMDb)")
        print("=" * 60)
        print(f"📊 Movies to process: {len(movies_to_process)}")
        print(f"📝 Missing-field report: {MISSING_REPORT_PATH}")
        print(f"🔑 TMDB Key: {TMDB_API_KEY[:10]}...")
        print(f"🎬 OMDb Mode: {'ENABLED (will fill gaps)' if args.use_omdb else 'DISABLED (TMDB only)'}")
        if args.use_omdb:
            print(f"   OMDb Key: {OMDB_API_KEY[:4]}... (Rate limit: 1000/day)")
        if args.skip_ott:
            print("🚫 OTT enrichment: SKIPPED (using existing data)")
        else:
            print("📺 OTT enrichment: ENABLED (will fetch from TMDB)")
        print("=" * 60)

        success = 0
        for movie in movies_to_process:
            try:
                if enrich_movie(movie, force=args.force, skip_ott=args.skip_ott, use_omdb=args.use_omdb):
                    success += 1
            except Exception as exc:
                print(f"    ✗ Error: {exc}")
                db.session.rollback()

        print("\n" + "=" * 60)
        print(f"DONE. Updated: {success}/{len(movies)}")
        print("=" * 60)
        
        # Guide for two-phase enrichment
        if not args.use_omdb:
            print("\n📋 NEXT STEPS (Two-Phase Enrichment):")
            print("=" * 60)
            print("Phase 1 (TMDB only) ✅ COMPLETE")
            print("\nPhase 2 (Fill gaps with OMDb):")
            print("  1. Check missing fields below ↓")
            print("  2. Run: python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit 500")
            print("     (OMDb fills gaps, --skip-ott prevents re-fetching OTT data)")
            print("  3. OMDb has rate limit: 1000 requests/day")
            print("     (So process up to 500-700 movies max per day)")
            print("\n💡 TIP: Use --skip-ott in Phase 2 since OTT is already filled from TMDB")
            print("=" * 60)
        
        # Show what's still missing
        print(f"\n📊 MISSING DATA SUMMARY (After TMDB enrichment):")
        print("=" * 60)
        all_movies = Movie.query.filter(Movie.tmdb_id != None).all()
        fields = ['overview', 'poster', 'backdrop', 'runtime', 'genres', 'cast', 'certification', 'youtube_trailer_id', 'release_date', 'rating', 'popularity', 'ott_platforms']
        for field in fields:
            if field == 'ott_platforms':
                missing = Movie.query.filter(
                    or_(
                        Movie.ott_platforms == None,
                        Movie.ott_platforms == '',
                        Movie.ott_platforms == '{}'
                    )
                ).count()
            else:
                col = getattr(Movie, field)
                if field in ['runtime', 'rating', 'popularity']:
                    missing = Movie.query.filter(or_(col == None, col == 0)).count()
                else:
                    missing = Movie.query.filter(or_(col == None, col == '')).count()
            if missing > 0:
                print(f"{field}: {missing}")
        print("=" * 60)


if __name__ == '__main__':
    main()
