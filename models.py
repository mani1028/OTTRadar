from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import secrets

db = SQLAlchemy()

class Movie(db.Model):
    """Movie model for the OTT tracker with expanded fields"""
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    poster = db.Column(db.String(500))
    backdrop = db.Column(db.String(500))
    overview = db.Column(db.Text)
    release_date = db.Column(db.String(10))  # YYYY-MM-DD format
    rating = db.Column(db.Float, default=0)
    language = db.Column(db.String(5), default='te')
    ott_platforms = db.Column(db.Text, default='{}')  # JSON format
    trailer = db.Column(db.String(500))
    youtube_trailer_id = db.Column(db.String(20))  # YouTube video ID (e.g., "dQw4w9WgXcQ")
    runtime = db.Column(db.Integer, default=0)
    genres = db.Column(db.String(255), default='')
    cast = db.Column(db.Text, default='')
    certification = db.Column(db.String(10), default='')
    popularity = db.Column(db.Float, default=0)  # TMDB popularity score
    is_active = db.Column(db.Boolean, default=True)  # For soft deletes
    fetch_source = db.Column(db.String(50), default='tmdb')  # Source: tmdb, scraper, manual, instant_scrape
    is_dubbed = db.Column(db.Boolean, default=False)  # Track dubbed vs original
    has_telugu_audio = db.Column(db.Boolean, default=False)  # Telugu audio available (for dubbed content)
    status = db.Column(db.String(50), default='')  # trending_hyderabad, new_on_ott, etc.
    source = db.Column(db.String(50), default='initial_import')  # initial_import or scraper
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)  # Last OTT check
    last_verified = db.Column(db.DateTime, default=datetime.utcnow)  # Last metadata verification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert movie object to dictionary for API responses"""
        try:
            ott_data = json.loads(self.ott_platforms) if self.ott_platforms else {}
        except:
            ott_data = {}
        
        return {
            'id': self.id,
            'tmdb_id': self.tmdb_id,
            'title': self.title,
            'poster': self.poster,
            'backdrop': self.backdrop,
            'overview': self.overview,
            'release_date': self.release_date,
            'rating': self.rating,
            'language': self.language,
            'ott_platforms': ott_data,
            'trailer': self.trailer,
            'youtube_trailer_id': self.youtube_trailer_id,
            'runtime': self.runtime,
            'genres': self.genres,
            'cast': self.cast,
            'certification': self.certification,
            'popularity': self.popularity,
            'is_active': self.is_active,
            'is_dubbed': self.is_dubbed,
            'fetch_source': self.fetch_source,
            'source': self.source,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'last_verified': self.last_verified.isoformat() if self.last_verified else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_dict_minimal(self):
        """Minimal dictionary for list views - fast loading"""
        try:
            ott_data = json.loads(self.ott_platforms) if self.ott_platforms else {}
        except:
            ott_data = {}
        
        return {
            'id': self.id,
            'tmdb_id': self.tmdb_id,
            'title': self.title,
            'poster': self.poster,
            'rating': self.rating,
            'ott_platforms': ott_data,
            'youtube_trailer_id': self.youtube_trailer_id
        }
    
    def get_primary_ott_platforms(self, limit=2):
        """Get top OTT platforms (max 2 primary) - for UI display"""
        ott_priority = {
            'netflix': 1,
            'prime': 2,
            'amazon': 2,
            'hotstar': 3,
            'jiocinema': 4,
            'zee5': 5,
            'airtel': 6
        }
        
        ott_data = self.get_ott_platforms()
        if not ott_data:
            return {}
        
        # Sort by priority and return top N
        sorted_otts = sorted(
            ott_data.items(),
            key=lambda x: ott_priority.get(x[0].lower(), 999)
        )
        return dict(sorted_otts[:limit])
    
    def get_ott_platforms(self):
        """Get OTT platforms as dictionary"""
        try:
            return json.loads(self.ott_platforms) if self.ott_platforms else {}
        except:
            return {}

    @staticmethod
    def _parse_ott_date(value):
        """Parse OTT availability date from int/float (epoch) or string."""
        if not value:
            return None

        if isinstance(value, (int, float)):
            timestamp = float(value)
            # Handle milliseconds vs seconds
            if timestamp > 1_000_000_000_000:
                timestamp = timestamp / 1000.0
            return datetime.utcfromtimestamp(timestamp)

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                # Handle ISO-like formats
                return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            except ValueError:
                pass
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(cleaned, fmt)
                except ValueError:
                    continue

        return None

    def get_ott_release_date(self):
        """Return the most recent OTT availability date if present, else release_date."""
        ott_data = self.get_ott_platforms()
        dates = []
        for info in (ott_data or {}).values():
            if not info:
                continue
            for key in ("available_from", "available_date", "ott_release_date"):
                parsed = self._parse_ott_date((info or {}).get(key))
                if parsed:
                    dates.append(parsed)

        if dates:
            return max(dates)

        return self._parse_ott_date(self.release_date)
    
    def set_ott_platforms(self, platforms_dict):
        """Set OTT platforms from dictionary"""
        if isinstance(platforms_dict, dict):
            self.ott_platforms = json.dumps(platforms_dict)
        else:
            self.ott_platforms = str(platforms_dict)


class UserSubmission(db.Model):
    """Unified model for user suggestions and movie requests"""
    __tablename__ = 'user_submissions'

    id = db.Column(db.Integer, primary_key=True)
    movie_title = db.Column(db.String(255), nullable=True, index=True)  # For movie requests
    language = db.Column(db.String(50), nullable=True)  # For movie requests
    platform_name = db.Column(db.String(100), nullable=True)  # For movie requests
    ott_link = db.Column(db.String(500), nullable=True)
    comment = db.Column(db.Text, nullable=True)  # Notes for movies or Description for features
    submission_type = db.Column(db.String(20), default='request')  # 'movie' or 'feature'
    category = db.Column(db.String(20), nullable=True)  # For feature suggestions: 'feature', 'ui', 'bug'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'added', 'rejected'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<UserSubmission {self.movie_title or self.submission_type}>'


class Watchlist(db.Model):
    """User watchlist for tracking movies"""
    __tablename__ = 'watchlist'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)  # Anonymous user ID or username
    email = db.Column(db.String(255), nullable=True, index=True)  # Optional: linked email for persistence
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False, index=True)
    movie = db.relationship('Movie', backref='watchlist_entries')
    status = db.Column(db.String(20), default='watchlist')  # 'watchlist', 'watched', 'interested'
    platforms_available = db.Column(db.JSON, default=list)  # List of platforms where available when added
    added_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    watched_at = db.Column(db.DateTime)
    linked_at = db.Column(db.DateTime, nullable=True)  # When watchlist was linked to email
    
    def __repr__(self):
        return f'<Watchlist {self.user_id}:{self.movie_id}>'


class WatchlistAlert(db.Model):
    """Alerts for watchlist items (when movie becomes free/available)"""
    __tablename__ = 'watchlist_alert'
    
    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey('watchlist.id'), nullable=False, index=True)
    watchlist = db.relationship('Watchlist', backref='alerts')
    alert_type = db.Column(db.String(50), default='available')  # 'available', 'price_drop', 'free_available'
    platform = db.Column(db.String(100))  # Netflix, Prime, etc.
    price = db.Column(db.Float)  # For price drop alerts
    is_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<WatchlistAlert {self.watchlist_id}:{self.alert_type}>'


class UserWatchlistEmail(db.Model):
    """Persist anonymous watchlists by linking to email - prevents data loss on cookie clear"""
    __tablename__ = 'user_watchlist_email'
    
    id = db.Column(db.Integer, primary_key=True)
    anonymous_user_id = db.Column(db.String(100), nullable=False, index=True)  # Original session user_id
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)  # Verified email
    verification_token = db.Column(db.String(100), unique=True)  # For email verification
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    linked_at = db.Column(db.DateTime, nullable=True)  # When email was verified and linked
    
    def __repr__(self):
        return f'<UserWatchlistEmail {self.email}>'


class OTTSnapshot(db.Model):
    """Daily snapshot of OTT availability for analytics"""
    __tablename__ = 'ott_snapshot'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, index=True, unique=True)
    netflix_count = db.Column(db.Integer, default=0)
    prime_count = db.Column(db.Integer, default=0)
    hotstar_count = db.Column(db.Integer, default=0)
    total_count = db.Column(db.Integer, default=0)
    free_count = db.Column(db.Integer, default=0)  # Free movies
    platforms_json = db.Column(db.Text, default='{}')  # All platforms with counts
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_platforms(self):
        """Get platforms dict"""
        try:
            return json.loads(self.platforms_json) if self.platforms_json else {}
        except:
            return {}
    
    def set_platforms(self, platforms_dict):
        """Set platforms dict"""
        if isinstance(platforms_dict, dict):
            self.platforms_json = json.dumps(platforms_dict)
    
    def __repr__(self):
        return f'<OTTSnapshot {self.date}>'

