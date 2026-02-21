from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import json
import secrets

db = SQLAlchemy()
# Add UserMixin for Flask-Login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    poster = db.Column(db.String(500))
    backdrop = db.Column(db.String(500))
    overview = db.Column(db.Text)
    release_date = db.Column(db.String(10))  # YYYY-MM-DD format (theatrical release)
    ott_release_date = db.Column(db.String(10))  # YYYY-MM-DD format (OTT/streaming release)
    rating = db.Column(db.Float, default=0)
    language = db.Column(db.String(50), default='te')
    ott_platforms = db.Column(db.Text, default='{}')  # JSON format
    trailer = db.Column(db.String(500))
    youtube_trailer_id = db.Column(db.String(20))  # YouTube video ID (e.g., "dQw4w9WgXcQ")
    runtime = db.Column(db.Integer, default=0)
    genres = db.Column(db.String(255), default='')
    cast = db.Column(db.Text, default='')
    certification = db.Column(db.String(50), default='')
    popularity = db.Column(db.Float, default=0)  # TMDB popularity score
    is_active = db.Column(db.Boolean, default=True)  # For soft deletes
    fetch_source = db.Column(db.String(50), default='tmdb')  # Source: tmdb, scraper, manual, instant_scrape
    is_dubbed = db.Column(db.Boolean, default=False)  # Track dubbed vs original
    has_telugu_audio = db.Column(db.Boolean, default=False)  # Telugu audio available (for dubbed content)
    status = db.Column(db.String(50), default='')  # trending_hyderabad, new_on_ott, etc.
    source = db.Column(db.String(50), default='initial_import')  # initial_import or scraper
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Last OTT check
    last_verified = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Last metadata verification
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def quality_score(self):
        """Calculates a 0-100 score based on metadata completeness."""
        fields = [self.overview, self.poster, self.runtime, self.youtube_trailer_id, self.cast]
        filled = sum(1 for f in fields if f and f != '' and f != 0)
        ott_weight = 5 if (self.ott_platforms and self.ott_platforms != '{}') else 0
        return round(((filled + ott_weight) / (len(fields) + 5)) * 100)

    def get_completeness_score(self):
        """Calculates a score (0-100) based on critical sustain requirements."""
        score = 0
        if self.ott_release_date:
            score += 40  # Highest weight for missing OTT release date
        if self.ott_platforms and self.ott_platforms != '{}':
            score += 40  # For missing platforms
        if self.youtube_trailer_id:
            score += 20
        return score

    @property
    def quality_score(self):
        """Calculates a 0-100 score based on metadata completeness."""
        fields = [self.overview, self.poster, self.runtime, self.youtube_trailer_id, self.cast]
        filled = sum(1 for f in fields if f and f != '' and f != 0)
        ott_weight = 5 if (self.ott_platforms and self.ott_platforms != '{}') else 0
        return round(((filled + ott_weight) / (len(fields) + 5)) * 100)
    """Movie model for the OTT tracker with expanded fields"""
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    poster = db.Column(db.String(500))
    backdrop = db.Column(db.String(500))
    overview = db.Column(db.Text)
    release_date = db.Column(db.String(10))  # YYYY-MM-DD format (theatrical release)
    ott_release_date = db.Column(db.String(10))  # YYYY-MM-DD format (OTT/streaming release)
    rating = db.Column(db.Float, default=0)
    language = db.Column(db.String(50), default='te')
    ott_platforms = db.Column(db.Text, default='{}')  # JSON format
    trailer = db.Column(db.String(500))
    youtube_trailer_id = db.Column(db.String(20))  # YouTube video ID (e.g., "dQw4w9WgXcQ")
    runtime = db.Column(db.Integer, default=0)
    genres = db.Column(db.String(255), default='')
    cast = db.Column(db.Text, default='')
    certification = db.Column(db.String(50), default='')
    popularity = db.Column(db.Float, default=0)  # TMDB popularity score
    is_active = db.Column(db.Boolean, default=True)  # For soft deletes
    fetch_source = db.Column(db.String(50), default='tmdb')  # Source: tmdb, scraper, manual, instant_scrape
    is_dubbed = db.Column(db.Boolean, default=False)  # Track dubbed vs original
    has_telugu_audio = db.Column(db.Boolean, default=False)  # Telugu audio available (for dubbed content)
    status = db.Column(db.String(50), default='')  # trending_hyderabad, new_on_ott, etc.
    source = db.Column(db.String(50), default='initial_import')  # initial_import or scraper
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Last OTT check
    last_verified = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))  # Last metadata verification
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Series Support (for multi-part movies and TV shows)
    media_type = db.Column(db.String(50), default='movie')  # 'movie' or 'tv'
    series_name = db.Column(db.String(255))  # Base series name for grouping
    season_number = db.Column(db.Integer)  # Season number
    episode_number = db.Column(db.Integer)  # Episode or part number
    episode_count = db.Column(db.Integer)  # Total episodes/parts
    
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
            'ott_release_date': self.ott_release_date,
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
    
    def get_ott_links(self):
        """
        Get OTT watchable links with fallback strategy:
        1. If direct_url exists → use it
        2. Else → use fallback_search_url (auto-generated)
        
        Returns:
            list of dicts: [{
                'platform': 'netflix',
                'url': 'https://...',
                'link_type': 'direct' or 'search',
                'provider_name': 'Netflix',
                'logo': 'https://...'
            }]
        """
        ott_data = self.get_ott_platforms()
        if not ott_data:
            return []
        
        links = []
        for platform, info in ott_data.items():
            if not isinstance(info, dict):
                continue
            
            # Prefer direct URL if available, fallback to search URL
            url = info.get('direct_url') or info.get('url') or info.get('fallback_search_url')
            
            if not url:
                continue
            
            link_type = 'direct' if info.get('direct_url') or info.get('url') else 'search'
            
            links.append({
                'platform': platform,
                'url': url,
                'link_type': link_type,
                'provider_name': info.get('provider_name', platform.title()),
                'logo': info.get('logo_path'),
            })
        
        return links


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
    status = db.Column(db.String(50), default='pending')  # 'pending', 'added', 'rejected'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
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
    status = db.Column(db.String(50), default='watchlist')  # 'watchlist', 'watched', 'interested'
    platforms_available = db.Column(db.JSON, default=list)  # List of platforms where available when added
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
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


class AuditLog(db.Model):
    """Track all admin actions for accountability and debugging"""
    __tablename__ = 'audit_log'
    
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(100), nullable=False, index=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)  # 'movie_edit', 'bulk_update', 'script_run', etc.
    target_type = db.Column(db.String(50))  # 'movie', 'person', 'submission', etc.
    target_id = db.Column(db.Integer)  # ID of affected entity
    description = db.Column(db.Text)  # Human-readable description
    changes_json = db.Column(db.Text)  # JSON of changed fields (before/after)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def get_changes(self):
        """Get changes dict"""
        try:
            return json.loads(self.changes_json) if self.changes_json else {}
        except:
            return {}
    
    def set_changes(self, changes_dict):
        """Set changes dict"""
        if isinstance(changes_dict, dict):
            self.changes_json = json.dumps(changes_dict)
    
    def __repr__(self):
        return f'<AuditLog {self.admin_username}:{self.action_type}>'


class ScriptExecution(db.Model):
    """Track script executions triggered from admin panel"""
    __tablename__ = 'script_execution'
    
    id = db.Column(db.Integer, primary_key=True)
    script_name = db.Column(db.String(100), nullable=False, index=True)
    triggered_by = db.Column(db.String(100), nullable=False)  # Admin username
    status = db.Column(db.String(50), default='running', index=True)  # 'running', 'success', 'failed', 'cancelled'
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    output_log = db.Column(db.Text)  # Capture stdout/stderr
    error_message = db.Column(db.Text)
    success_count = db.Column(db.Integer, default=0)  # For scripts that process items
    error_count = db.Column(db.Integer, default=0)
    pid = db.Column(db.Integer, nullable=True, index=True)  # Process ID for running system processes
    
    def __repr__(self):
        return f'<ScriptExecution {self.script_name}:{self.status}>'


class Person(db.Model):
    """Actor/Director/Crew person metadata"""
    __tablename__ = 'person'
    
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    profile_path = db.Column(db.String(500))  # TMDB profile image path
    biography = db.Column(db.Text)
    birthday = db.Column(db.String(10))  # YYYY-MM-DD
    place_of_birth = db.Column(db.String(255))
    known_for_department = db.Column(db.String(50))  # Acting, Directing, etc.
    popularity = db.Column(db.Float, default=0)
    gender = db.Column(db.Integer)  # TMDB gender code (1=F, 2=M)
    is_verified = db.Column(db.Boolean, default=False)  # Manually verified by admin
    custom_bio = db.Column(db.Text)  # Admin override for biography
    custom_profile_url = db.Column(db.String(500))  # Admin override for profile image
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def get_profile_url(self, size='w185'):
        """Get TMDB profile image URL"""
        if self.custom_profile_url:
            return self.custom_profile_url
        if self.profile_path:
            return f'https://image.tmdb.org/t/p/{size}{self.profile_path}'
        return '/static/img/no-profile.png'
    
    def get_bio(self):
        """Get biography (custom override or TMDB)"""
        return self.custom_bio if self.custom_bio else self.biography
    
    def __repr__(self):
        return f'<Person {self.name}>'


class AffiliateConfig(db.Model):
    """Affiliate configuration for monetization (Prime Video & Apple Services)"""
    __tablename__ = 'affiliate_config'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Amazon/Prime Video
    amazon_associate_id = db.Column(db.String(255), default='')  # e.g., "ottradarin-21"
    amazon_tag = db.Column(db.String(100), default='')  # Legacy, derived from associate_id
    amazon_enabled = db.Column(db.Boolean, default=True)
    
    # Apple Services
    apple_affiliate_id = db.Column(db.String(255), default='')  # AppleID from Apple's affiliate program
    apple_campaign_token = db.Column(db.String(100), default='')  # Campaign token for tracking
    apple_enabled = db.Column(db.Boolean, default=True)
    
    # Prime Channels (LionsGate, Discovery+, MGM+, etc.)
    prime_channels_enabled = db.Column(db.Boolean, default=True)
    
    # Apple TV+ Bundle tracking
    apple_bundle_enabled = db.Column(db.Boolean, default=True)
    
    # Settings
    cookie_duration = db.Column(db.Integer, default=24)  # Hours (Amazon: 24h, Apple: varies)
    link_health_check_enabled = db.Column(db.Boolean, default=True)
    price_tracking_enabled = db.Column(db.Boolean, default=True)
    
    # CTA Customization
    prime_cta_text = db.Column(db.String(255), default='Watch for Free with Prime Trial')
    apple_cta_text = db.Column(db.String(255), default='Add to Apple Library')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(100), default='system')  # Track who changed it
    
    def __repr__(self):
        return f'<AffiliateConfig Amazon:{self.amazon_associate_id} Apple:{self.apple_affiliate_id}>'


class LinkHealthCheck(db.Model):
    """Track affiliate link health to detect dead links"""
    __tablename__ = 'link_health_checks'
    
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 'amazon_prime' or 'apple_tv'
    affiliate_url = db.Column(db.String(500), nullable=False)
    status_code = db.Column(db.Integer)  # Last HTTP status (200, 404, etc.)
    is_alive = db.Column(db.Boolean, default=True)
    last_checked = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    error_message = db.Column(db.String(500))  # e.g., "404 Not Found"
    
    def __repr__(self):
        return f'<LinkHealthCheck {self.platform}:{self.status_code}>'


class PriceDrop(db.Model):
    """Track price drops for movies on OTT platforms"""
    __tablename__ = 'price_drops'
    
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    platform = db.Column(db.String(50), nullable=False)  # 'amazon_prime' or 'apple_tv'
    previous_price = db.Column(db.Float)  # In INR
    current_price = db.Column(db.Float)  # In INR
    discount_percentage = db.Column(db.Float)  # Calculated percentage
    currency = db.Column(db.String(5), default='INR')
    detected_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    posted_to_twitter = db.Column(db.Boolean, default=False)
    posted_to_telegram = db.Column(db.Boolean, default=False)
    twitter_post_id = db.Column(db.String(255))  # Tweet ID
    
    def __repr__(self):
        return f'<PriceDrop {self.platform}: ₹{self.previous_price} → ₹{self.current_price}>'
