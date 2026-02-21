"""
Movie discovery, filtering, and search utilities
Provides filtering, searching, and discovery methods for movies
"""

import json
import requests
import os
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, desc
from models import db, Movie



class MovieFilter:
    """Filter movies by various criteria"""

    def paginate(self, page, per_page=20):
        """Return a pagination object instead of a list"""
        return self.query.paginate(page=page, per_page=per_page, error_out=False)

    def __init__(self):
        self.query = Movie.query.filter_by(is_active=True)

    def by_language(self, languages):
        """Filter by one or multiple languages"""
        if isinstance(languages, list):
            conditions = [Movie.language.ilike(f'%{lang}%') for lang in languages if lang]
            if conditions:
                self.query = self.query.filter(or_(*conditions))
        else:
            self.query = self.query.filter(Movie.language.ilike(f'%{languages}%'))
        return self

    def by_year_range(self, year_from, year_to):
        if year_from:
            self.query = self.query.filter(Movie.release_date >= f"{year_from}-01-01")
        if year_to:
            self.query = self.query.filter(Movie.release_date <= f"{year_to}-12-31")
        return self

    def by_dubbed(self):
        self.query = self.query.filter(Movie.is_dubbed == True)
        return self
    
    def by_genre(self, genre):
        """Filter by genre"""
        self.query = self.query.filter(Movie.genres.ilike(f'%{genre}%'))
        return self
    
    def by_rating(self, min_rating):
        """Filter by minimum rating"""
        self.query = self.query.filter(Movie.rating >= min_rating)
        return self
    
    def by_year(self, year):
        """Filter by release year"""
        self.query = self.query.filter(Movie.release_date.like(f'{year}%'))
        return self
    
    def by_platform(self, platforms):
        """Filter by one or multiple OTT platforms"""
        if isinstance(platforms, list):
            # Create an OR condition for multiple platforms
            conditions = [Movie.ott_platforms.ilike(f'%{p}%') for p in platforms if p]
            if conditions:
                self.query = self.query.filter(or_(*conditions))
        else:
            self.query = self.query.filter(Movie.ott_platforms.ilike(f'%{platforms}%'))
        return self
    
    def with_ott(self):
        """Only movies with OTT platforms"""
        self.query = self.query.filter(Movie.ott_platforms != '{}')
        return self
    
    def sort_by_rating(self):
        """Sort by rating descending"""
        self.query = self.query.order_by(desc(Movie.rating))
        return self
    
    def sort_by_popularity(self):
        """Sort by popularity descending"""
        self.query = self.query.order_by(desc(Movie.popularity))
        return self

    def order_by_release_date(self, desc_order=True):
        """Order by release date (descending by default)"""
        if desc_order:
            self.query = self.query.order_by(desc(Movie.release_date))
        else:
            self.query = self.query.order_by(Movie.release_date)
        return self
    
    def limit(self, count):
        """Limit results"""
        self.query = self.query.limit(count)
        return self
    
    def all(self):
        """Get all results"""
        return self.query.all()
    
    def first(self):
        """Get first result"""
        return self.query.first()
    
    def count(self):
        """Count results"""
        return self.query.count()


class OTTDiscovery:
    """Discover movies by OTT availability and other criteria"""

    @staticmethod
    def enrich_movie_metadata(tmdb_id):
        """
        Enrich a movie with TMDB (including watch/providers), OMDb, and RapidAPI. Focus on OTT platforms, release date, and Telugu audio.
        """
        results = {}
        api_key_tmdb = os.getenv('TMDB_API_KEY')
        api_key_omdb = os.getenv('OMDB_API_KEY')
        api_key_rapid = os.getenv('RAPID_API_KEY')

        # 1. TMDB: Core + Watch Providers
        try:
            tmdb_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={api_key_tmdb}&append_to_response=external_ids,videos,watch/providers"
            data = requests.get(tmdb_url, timeout=10).json()
            imdb_id = data.get('external_ids', {}).get('imdb_id')
            # OTT platforms for India
            watch_data = data.get('watch/providers', {}).get('results', {}).get('IN', {})
            ott_platforms = {}
            for provider in watch_data.get('flatrate', []):
                ott_platforms[provider['provider_name'].lower()] = {
                    'provider_id': provider['provider_id'],
                    'logo': f"https://image.tmdb.org/t/p/original{provider['logo_path']}"
                }
            results.update({
                'ott_platforms': json.dumps(ott_platforms),
                'poster': f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None,
                'overview': data.get('overview'),
                'runtime': data.get('runtime', 0),
                'genres': ", ".join([g['name'] for g in data.get('genres', [])]),
                'youtube_trailer_id': next((v['key'] for v in data.get('videos', {}).get('results', []) if v['site'] == 'YouTube'), None),
                'rating': data.get('vote_average', 0),
                'has_telugu_audio': data.get('original_language') == 'te'
            })
            # TMDB release_dates endpoint for OTT release date
            release_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/release_dates?api_key={api_key_tmdb}"
            rel_data = requests.get(release_url, timeout=10).json()
            for res in rel_data.get('results', []):
                if res['iso_3166_1'] == 'IN':
                    for rd in res['release_dates']:
                        if rd['type'] >= 4:  # Digital or Physical release
                            results['ott_release_date'] = rd['release_date'][:10]
                            break
        except Exception as e:
            print(f"Enrichment Error: {e}")
            imdb_id = None

        # 2. OMDb (Detailed Plot & Ratings)
        if imdb_id and api_key_omdb:
            try:
                omdb_url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key_omdb}"
                omdb_data = requests.get(omdb_url, timeout=10).json()
                if omdb_data.get("Response") == "True":
                    if omdb_data.get('imdbRating') != 'N/A':
                        results['rating'] = float(omdb_data.get('imdbRating'))
                    if not results.get('overview') or len(results.get('overview', '')) < 10:
                        results['overview'] = omdb_data.get('Plot')
                    results['certification'] = omdb_data.get('Rated')
            except Exception as e:
                print(f"OMDb Enrichment Error: {e}")


        # 3. RapidAPI (Streaming Availability for OTT links)
        if imdb_id and api_key_rapid:
            try:
                headers = {"X-RapidAPI-Key": api_key_rapid, "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com"}
                stream_data = requests.get(
                    "https://streaming-availability.p.rapidapi.com/v2/get/basic",
                    headers=headers,
                    params={"country":"in", "imdb_id": imdb_id},
                    timeout=10
                ).json()
                if 'result' in stream_data:
                    results['ott_platforms'] = json.dumps(stream_data['result']['streamingInfo'].get('in', {}))
            except Exception:
                pass

        return results

    @staticmethod
    def fetch_telugu_streaming_status(imdb_id):
        """Specific check for Telugu availability via RapidAPI."""
        api_key_rapid = os.getenv('RAPID_API_KEY')
        if not api_key_rapid or not imdb_id:
            return None
        url = "https://streaming-availability.p.rapidapi.com/v2/get/basic"
        headers = {"X-RapidAPI-Key": api_key_rapid}
        params = {"country": "in", "imdb_id": imdb_id}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10).json()
            info = res.get('result', {}).get('streamingInfo', {}).get('in', {})
            return info if info else None
        except:
            return None

    @staticmethod
    def fetch_new_movies(year=2024, language='te', limit=20, pages=1):
        """Fetch new movies directly from TMDB API"""
        api_key = os.getenv('TMDB_API_KEY')
        base_url = "https://api.themoviedb.org/3/discover/movie"
        all_results = []
        for page in range(1, pages + 1):
            params = {
                'api_key': api_key,
                'primary_release_year': year,
                'with_original_language': language,
                'sort_by': 'popularity.desc',
                'page': page
            }
            try:
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                for item in data.get('results', []):
                    all_results.append({
                        'tmdb_id': item['id'],
                        'title': item['title'],
                        'overview': item['overview'],
                        'poster': f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item['poster_path'] else None,
                        'release_date': item['release_date'],
                        'rating': item['vote_average'],
                        'popularity': item['popularity'],
                        'language': item['original_language']
                    })
                    if len(all_results) >= limit:
                        return all_results
            except Exception as e:
                print(f"TMDB API Error: {e}")
                break
                
        return all_results

    @staticmethod
    def new_on_ott(days=60, limit=50):
        """New on OTT: Only movies actually released on OTT in the last N days"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        today = now.strftime('%Y-%m-%d')
        cutoff = (now - timedelta(days=days)).strftime('%Y-%m-%d')
        query = Movie.query.filter(
            Movie.is_active == True,
            Movie.ott_release_date.isnot(None),
            Movie.ott_release_date != '',
            Movie.ott_release_date >= cutoff,
            Movie.ott_release_date <= today,
            Movie.ott_platforms != '{}'
        ).order_by(desc(Movie.ott_release_date)).limit(limit)
        return query.all()
    
    @staticmethod
    def free_movies(limit=50):
        """Get free movies (free OTT platforms)"""
        free_platforms = ['youtube', 'hotstar', 'voot', 'mx']
        filters = [Movie.ott_platforms.ilike(f'%"{platform}"%') for platform in free_platforms]
        query = Movie.query.filter(
            Movie.is_active == True,
            or_(*filters)
        ).order_by(Movie.popularity.desc()).limit(limit)
        return query.all()
    
    @staticmethod
    def hidden_gems(limit=50, min_rating=7.0):
        """Fetches high-rated, low-popularity movies in a random order to stay fresh."""
        from sqlalchemy.sql.expression import func as sql_func
        return Movie.query.filter(
            Movie.is_active == True,
            Movie.rating >= min_rating,
            Movie.popularity < 100, # Lower popularity = "Hidden"
            Movie.popularity > 5
        ).order_by(sql_func.random()).limit(limit).all()
    
    @staticmethod
    def trending_now(limit=50, days=365):
        """Trending: high popularity/rating from the last year"""
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        return Movie.query.filter(
            Movie.is_active == True,
            or_(
                and_(Movie.ott_release_date.isnot(None), Movie.ott_release_date >= cutoff),
                and_(Movie.release_date.isnot(None), Movie.release_date >= cutoff)
            ),
            Movie.rating.isnot(None),
            Movie.rating >= 6.0,
            Movie.popularity.isnot(None)
        ).order_by(desc(Movie.popularity)).limit(limit).all()
    
    @staticmethod
    def platform_stats():
        """Get statistics about OTT platform coverage"""
        total_movies = Movie.query.filter_by(is_active=True).count()
        movies_with_ott = Movie.query.filter(
            Movie.ott_platforms != '{}',
            Movie.is_active == True
        ).count()
        
        platform_counts = {}
        platforms = ['netflix', 'prime', 'hotstar', 'jiocinema', 'zee5', 
                     'sonyliv', 'apple', 'airtel', 'mxplayer', 'voot', 'aha', 'youtube']
        
        for platform in platforms:
            count = Movie.query.filter(
                Movie.ott_platforms.ilike(f'%{platform}%'),
                Movie.is_active == True
            ).count()
            if count > 0:
                platform_counts[platform] = count
        
        return {
            'total_movies': total_movies,
            'with_ott': movies_with_ott,
            'coverage_percent': (movies_with_ott / total_movies * 100) if total_movies > 0 else 0,
            'platforms': platform_counts
        }
    
    @staticmethod
    def homepage_data():
        """Get data for homepage display"""
        return {
            'featured': OTTDiscovery.trending_now(limit=8),
            'continue_watching': OTTDiscovery.trending_now(limit=6),
            'popular_on_radar': OTTDiscovery.trending_now(limit=12),
            'new_on_ott': OTTDiscovery.new_on_ott(days=30, limit=12),
            'hidden_gems': OTTDiscovery.hidden_gems(limit=12),
            'upcoming_hits': OTTDiscovery.free_movies(limit=8),
            'stats': OTTDiscovery.platform_stats()
        }


class UnifiedSearch:
    """Unified search across movies"""
    

    @staticmethod
    def search_movies_paginated(query, page=1, per_page=12):
        if not query:
            return None
        tokens = query.strip().split()
        filters = [Movie.title.ilike(f"%{token}%") for token in tokens]
        return Movie.query.filter(
            Movie.is_active == True,
            and_(*filters)
        ).order_by(Movie.popularity.desc()).paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def search_movies(query, limit=50, page=None, per_page=None):
        # Backward compatible: if page/per_page provided, use paginated
        if page and per_page:
            pagination = UnifiedSearch.search_movies_paginated(query, page, per_page)
            return pagination.items if pagination else []
        if not query:
            return []
        tokens = query.strip().split()
        if not tokens:
            return []
        filters = [Movie.title.ilike(f"%{token}%") for token in tokens]
        return Movie.query.filter(
            Movie.is_active == True,
            and_(*filters)
        ).order_by(Movie.popularity.desc()).limit(limit).all()
    
    @staticmethod
    def search_by_tmdb_id(tmdb_id):
        """Find movie by TMDB ID"""
        return Movie.query.filter_by(tmdb_id=tmdb_id, is_active=True).first()
    
    @staticmethod
    def search_by_title(title, limit=10):
        """Exact or fuzzy title search"""
        search_term = f'%{title}%'
        return Movie.query.filter(
            Movie.is_active == True,
            Movie.title.ilike(search_term)
        ).limit(limit).all()
    
    @staticmethod
    def search_by_platform(platform, limit=50):
        """Find movies available on specific platform"""
        return Movie.query.filter(
            Movie.is_active == True,
            Movie.ott_platforms.ilike(f'%{platform}%')
        ).order_by(desc(Movie.rating)).limit(limit).all()