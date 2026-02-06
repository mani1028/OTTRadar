"""
Smart filtering and discovery logic for OTT movies.
DRY principle: All search and filtering logic centralized here.
"""

from sqlalchemy import and_, or_, func
from models import Movie, OTTSnapshot, Watchlist
from datetime import datetime, timedelta


class UnifiedSearch:
    """Unified search logic - eliminates code duplication"""
    
    @staticmethod
    def search_movies(query, max_results=None):
        """
        Smart search with word splitting and relevance sorting.
        Returns list of Movie objects.
        """
        if not query or len(query.strip()) < 2:
            return []
        
        query = query.strip()
        words = query.split()
        search_results = []
        
        if words:
            # Exact phrase match (highest priority)
            exact_matches = Movie.query.filter(
                Movie.is_active == True,
                Movie.title.ilike(f'%{query}%')
            ).all()
            search_results.extend(exact_matches)
            
            # Partial word matches (secondary priority)
            for word in words:
                if len(word) > 2:  # Only search words with 3+ characters
                    word_matches = Movie.query.filter(
                        Movie.is_active == True,
                        Movie.title.ilike(f'%{word}%')
                    ).all()
                    for movie in word_matches:
                        if movie not in search_results:
                            search_results.append(movie)
        
        # Sort by relevance (rating + popularity)
        search_results = sorted(
            search_results,
            key=lambda m: (m.rating or 0, m.popularity or 0),
            reverse=True
        )
        
        if max_results:
            search_results = search_results[:max_results]
        
        return search_results


def _sort_by_ott_release(movies):
    """Sort movies by OTT availability date (newest first)."""
    return sorted(
        movies,
        key=lambda m: m.get_ott_release_date() or datetime.min,
        reverse=True,
    )


def _is_released(movie, now=None):
    """Return True if movie has a release/OTT date not in the future."""
    check_time = now or datetime.utcnow()
    release_dt = movie.get_ott_release_date()
    return bool(release_dt and release_dt <= check_time)


class MovieFilter:
    """Smart filtering for movies"""
    
    def __init__(self, query=None):
        if query is None:
            self.query = Movie.query.filter_by(is_active=True)
        else:
            self.query = query
    
    def by_language(self, languages):
        """Filter by language(s)"""
        if not languages:
            return self
        if isinstance(languages, str):
            languages = [languages]
        self.query = self.query.filter(Movie.language.in_(languages))
        return self
    
    def by_platform(self, platforms):
        """Filter by OTT platform(s)"""
        if not platforms:
            return self
        if isinstance(platforms, str):
            platforms = [platforms]
        
        # This is complex since platforms are in JSON
        # We'll do this in-memory for now
        self._platform_filter = platforms
        return self
    
    def by_rating(self, min_rating=0, max_rating=10):
        """Filter by rating range"""
        self.query = self.query.filter(Movie.rating >= min_rating, Movie.rating <= max_rating)
        return self
    
    def by_year(self, start_year=None, end_year=None):
        """Filter by release year"""
        if start_year:
            self.query = self.query.filter(Movie.release_date >= f"{start_year}-01-01")
        if end_year:
            self.query = self.query.filter(Movie.release_date <= f"{end_year}-12-31")
        return self
    
    def by_genre(self, genres):
        """Filter by genre(s)"""
        if not genres:
            return self
        if isinstance(genres, str):
            genres = [genres]
        
        for genre in genres:
            self.query = self.query.filter(Movie.genres.ilike(f"%{genre}%"))
        return self
    
    def free_only(self):
        """Filter for free content only"""
        self._free_only = True
        return self
    
    def by_monetization(self, monetization_types):
        """Filter by monetization type (free, subscription, rent, buy)"""
        if not monetization_types:
            return self
        if isinstance(monetization_types, str):
            monetization_types = [monetization_types]
        
        self._monetization_filter = monetization_types
        return self
    
    def by_dubbed(self, dubbed=True):
        """Filter dubbed movies"""
        self.query = self.query.filter(Movie.is_dubbed == dubbed)
        return self
    
    def hidden_gems(self):
        """Filter hidden gems (high rating, low popularity)"""
        self.query = self.query.filter(
            Movie.rating >= 7.5,
            Movie.popularity < 100
        ).order_by(Movie.rating.desc())
        return self
    
    def trending_now(self):
        """Filter trending movies (recent with high rating + popularity)"""
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        self.query = self.query.filter(
            Movie.last_updated >= week_ago,
            Movie.rating >= 6.5
        ).order_by(Movie.popularity.desc(), Movie.rating.desc())
        return self
    
    def new_this_week(self):
        """Filter movies added/updated this week"""
        week_ago = datetime.utcnow() - timedelta(days=7)
        self.query = self.query.filter(Movie.last_updated >= week_ago)
        return self
    
    def order_by_rating(self, desc=True):
        """Order by rating"""
        order = Movie.rating.desc() if desc else Movie.rating
        self.query = self.query.order_by(order)
        return self
    
    def order_by_popularity(self, desc=True):
        """Order by popularity"""
        order = Movie.popularity.desc() if desc else Movie.popularity
        self.query = self.query.order_by(order)
        return self
    
    def order_by_newest(self):
        """Order by most recently updated"""
        self.query = self.query.order_by(Movie.last_updated.desc())
        return self
    
    def order_by_release_date(self, desc=True):
        """Order by release date (newest releases first by default)"""
        order = Movie.release_date.desc() if desc else Movie.release_date
        self.query = self.query.order_by(order)
        return self
    
    def limit(self, count):
        """Limit results"""
        self.query = self.query.limit(count)
        return self
    
    def execute(self):
        """Get filtered results and apply in-memory filters"""
        results = self.query.all()
        
        # In-memory platform filter
        if hasattr(self, '_platform_filter'):
            results = [m for m in results if self._has_platforms(m, self._platform_filter)]
        
        # In-memory free-only filter
        if hasattr(self, '_free_only') and self._free_only:
            results = [m for m in results if self._has_free_option(m)]
        
        # In-memory monetization filter
        if hasattr(self, '_monetization_filter'):
            results = [m for m in results if self._has_monetization(m, self._monetization_filter)]
        
        return results
    
    @staticmethod
    def _has_platforms(movie, platforms):
        """Check if movie has any of the given platforms"""
        ott_data = movie.get_ott_platforms()
        platform_names = [p.lower() for p in platforms]
        return any(name.lower() in platform_names for name in ott_data.keys())
    
    @staticmethod
    def _has_free_option(movie):
        """Check if movie has free option"""
        ott_data = movie.get_ott_platforms()
        return any((v or {}).get('is_free') for v in ott_data.values())
    
    @staticmethod
    def _has_monetization(movie, monetization_types):
        """Check if movie has any of the monetization types"""
        ott_data = movie.get_ott_platforms()
        monetization_types_lower = [mt.lower() for mt in monetization_types]
        return any(
            (v or {}).get('monetization_type', '').lower() in monetization_types_lower
            for v in ott_data.values()
        )


class OTTDiscovery:
    """Discover movies and trends"""
    
    @staticmethod
    def new_on_ott(days=7):
        """Movies added/available in the last N days - sorted by release date"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        movies = Movie.query.filter_by(is_active=True).all()
        filtered = [
            m for m in movies
            if (m.get_ott_release_date() or datetime.min) >= cutoff
            and _is_released(m)
        ]
        return _sort_by_ott_release(filtered)
    
    @staticmethod
    def free_movies(limit=None):
        """Get all free movies"""
        free_movies = []
        all_movies = Movie.query.filter_by(is_active=True).all()
        
        for movie in all_movies:
            ott_data = movie.get_ott_platforms()
            if any((v or {}).get('is_free') for v in ott_data.values()):
                free_movies.append(movie)
        
        # Sort by OTT availability date - newest first
        free_movies = _sort_by_ott_release(free_movies)
        
        if limit:
            free_movies = free_movies[:limit]
        
        return free_movies
    
    @staticmethod
    def hidden_gems(limit=20):
        """High-rated but low-visibility movies - sorted by release date"""
        movies = MovieFilter()\
            .by_rating(min_rating=7.5)\
            .limit(limit)\
            .execute()
        return _sort_by_ott_release(movies)
    
    @staticmethod
    def trending_now(limit=20):
        """Currently trending movies - sorted by release date"""
        movies = MovieFilter()\
            .by_rating(min_rating=6.0)\
            .limit(limit)\
            .execute()
        released = [m for m in movies if _is_released(m)]
        return _sort_by_ott_release(released)
    
    @staticmethod
    def platform_stats():
        """Get platform availability stats"""
        all_movies = Movie.query.filter_by(is_active=True).all()
        platform_counts = {}
        free_count = 0
        
        for movie in all_movies:
            ott_data = movie.get_ott_platforms()
            for platform, info in ott_data.items():
                if platform:
                    platform_counts[platform] = platform_counts.get(platform, 0) + 1
                if (info or {}).get('is_free'):
                    free_count += 1
        
        return {
            'platforms': platform_counts,
            'free_count': free_count,
            'total_movies': len(all_movies),
            'total_unique_platforms': len(platform_counts)
        }
    
    @staticmethod
    def homepage_data():
        """
        Get all homepage data in one unified call.
        Optimized for mobile-first app-like experience.
        
        Section Order:
        1. Continue Watching (Personalization)
        2. Popular on Radar (Trending)
        3. New on OTT (Freshness - 7 days)
        4. Hidden Gems (Discovery)
        5. Upcoming Hits (Anticipation)
        """
        from datetime import date, timedelta
        from flask import session
        
        # 1. Continue Watching - Personalized from watchlist
        continue_watching = []
        if 'user_id' in session:
            user_id = session['user_id']
            watchlist_items = Watchlist.query.filter(
                Watchlist.user_id == user_id,
                Watchlist.status.in_(['watchlist', 'interested'])
            ).order_by(Watchlist.added_at.desc()).limit(15).all()
            continue_watching = [item.movie for item in watchlist_items if item.movie and item.movie.is_active]
        
        # 2. Popular on Radar (Trending) - High rating + High popularity
        popular_on_radar = Movie.query.filter_by(is_active=True) \
            .filter(Movie.rating >= 6.5) \
            .order_by(Movie.popularity.desc()).limit(15).all()
        popular_on_radar = _sort_by_ott_release(popular_on_radar)
        popular_on_radar = [m for m in popular_on_radar if _is_released(m)]
        
        # 3. New on OTT (Freshness) - Consolidates "Recently Added" and "Just Added"
        new_on_ott = [m for m in OTTDiscovery.new_on_ott(days=7) if _is_released(m)][:15]
        
        # 4. Hidden Gems (Discovery) - High rating, low popularity
        hidden_gems = Movie.query.filter_by(is_active=True) \
            .filter(Movie.rating >= 7.5, Movie.popularity < 100) \
            .order_by(Movie.rating.desc()).limit(15).all()
        hidden_gems = [m for m in hidden_gems if _is_released(m)]
        
        # 5. Upcoming Hits (Anticipation) - Future releases
        upcoming_hits = Movie.query.filter_by(is_active=True) \
            .filter(Movie.release_date > date.today().strftime('%Y-%m-%d')) \
            .order_by(Movie.release_date.asc()).limit(15).all()
        
        # Featured/Hero movie - highest rated recent movie for desktop
        featured = Movie.query.filter_by(is_active=True) \
            .filter(Movie.rating >= 7.5) \
            .order_by(Movie.popularity.desc()).first()
        
        return {
            'featured': featured,
            'continue_watching': continue_watching,
            'popular_on_radar': popular_on_radar,
            'new_on_ott': new_on_ott,
            'hidden_gems': hidden_gems,
            'upcoming_hits': upcoming_hits,
            # Legacy keys for backward compatibility (desktop view)
            'today_on_ott': new_on_ott,
            'trending': popular_on_radar,
            'new_releases': new_on_ott,
            'upcoming': upcoming_hits
        }
