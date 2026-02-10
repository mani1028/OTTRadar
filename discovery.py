"""
Movie discovery, filtering, and search utilities
Provides filtering, searching, and discovery methods for movies
"""

import json
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, desc
from models import db, Movie


class MovieFilter:
    """Filter movies by various criteria"""
    
    def __init__(self):
        self.query = Movie.query.filter_by(is_active=True)
    
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
    
    def by_platform(self, platform):
        """Filter by OTT platform"""
        self.query = self.query.filter(Movie.ott_platforms.ilike(f'%{platform}%'))
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

    def order_by_release_date(self, desc=True):
        """Order by release date (descending by default)"""
        if desc:
            self.query = self.query.order_by(db.desc(Movie.release_date))
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
    def new_on_ott(days=60, limit=50):
        """New on OTT: Only movies actually released on OTT in the last N days"""
        from datetime import datetime, timedelta
        today = datetime.utcnow().strftime('%Y-%m-%d')
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
        # Only include movies with a valid ott_release_date in the past (or today) and with at least one OTT platform
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
        """Get free movies (free OTT platforms like YouTube, Hotstar free tier)"""
        free_platforms = ['youtube', 'hotstar', 'voot', 'mx']
        query = Movie.query.filter_by(is_active=True)
        
        movies = []
        for movie in query.limit(500).all():
            ott_data = movie.get_ott_platforms()
            for platform in ott_data.keys():
                if any(free in platform.lower() for free in free_platforms):
                    movies.append(movie)
                    break
            if limit is not None and len(movies) >= limit:
                break
        return movies[:limit] if limit is not None else movies
    
    @staticmethod
    def hidden_gems(limit=50, min_rating=7.0):
        """Hidden Gems: High rating, lower popularity, any era"""
        return Movie.query.filter(
            Movie.is_active == True,
            Movie.rating != None,
            Movie.rating >= min_rating,
            Movie.popularity != None,
            Movie.popularity < 200,
            Movie.popularity > 5
        ).order_by(desc(Movie.rating)).limit(limit).all()
    
    @staticmethod
    def trending_now(limit=50, days=365):
        """Trending: high popularity/rating from the last year"""
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
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
    def search_movies(query, limit=50):
        from sqlalchemy import and_
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
