"""
Affiliate Link Management & Monetization Utilities
Handles Prime Video & Apple Services affiliate links with smart CTA logic
"""

import requests
import json
from urllib.parse import urlencode, quote
from datetime import datetime, timezone
from models import AffiliateConfig, LinkHealthCheck, PriceDrop, Movie, db
import logging

logger = logging.getLogger(__name__)


class AffiliateManager:
    """Manages affiliate links and CTAs for Prime Video & Apple Services"""
    
    @staticmethod
    def get_config():
        """Get active affiliate configuration (or create default)"""
        config = AffiliateConfig.query.first()
        if not config:
            config = AffiliateConfig()
            db.session.add(config)
            db.session.commit()
        return config
    
    @staticmethod
    def build_amazon_affiliate_url(movie_title, associate_id=None, search_only=False):
        """
        Build Amazon/Prime Video affiliate URL with tag
        
        Args:
            movie_title: Movie title to search
            associate_id: Amazon Associate ID (e.g., "ottradarin-21")
            search_only: If True, return search link; if False, return Prime Video link
        
        Returns:
            dict with 'url', 'cta_text', 'platform'
        """
        config = AffiliateManager.get_config()
        
        if not config.amazon_associate_id and not associate_id:
            return None
        
        associate_id = associate_id or config.amazon_associate_id
        tag = associate_id.split('-')[0] if '-' in associate_id else associate_id
        
        # Build URL with proper encoding
        base_url = "https://www.amazon.in/s"
        params = {
            'k': movie_title,
            'ref': f'as_li_ss_tl',
            'tag': tag,
        }
        
        if search_only:
            # Return general Amazon search link
            url = base_url + '?' + urlencode(params)
        else:
            # Return with tracking for Prime Video specifically
            params['tag'] = f"{tag}-21"  # Standard Amazon affiliate tag format
            url = base_url + '?' + urlencode(params)
        
        return {
            'url': url,
            'cta_text': config.prime_cta_text,
            'platform': 'amazon_prime',
            'bounty_type': 'prime_trial' if not search_only else 'purchase',
            'cookie_duration': config.cookie_duration
        }
    
    @staticmethod
    def build_apple_affiliate_url(movie_title, apple_id=None):
        """
        Build Apple TV+ affiliate URL
        
        Args:
            movie_title: Movie title
            apple_id: Apple affiliate ID
        
        Returns:
            dict with 'url', 'cta_text', 'platform'
        """
        config = AffiliateManager.get_config()
        
        if not config.apple_affiliate_id and not apple_id:
            return None
        
        apple_id = apple_id or config.apple_affiliate_id
        campaign_token = config.apple_campaign_token or "ottradarin"
        
        # Apple TV search/content URL format
        # https://apps.apple.com/app/apple-tv/id898900795?pt={affiliate_id}&ct={campaign_token}
        
        # More direct: Apple TV+ direct link with campaign tracking
        base_url = "https://www.apple.com/apple-tv-plus/"
        
        # Apple uses different tracking - pt=affiliate_id, ct=campaign_token
        params = {
            'pt': apple_id,
            'ct': campaign_token,
        }
        
        url = base_url + '?' + urlencode(params)
        
        return {
            'url': url,
            'cta_text': config.apple_cta_text,
            'platform': 'apple_tv',
            'bounty_type': 'subscription_trial',
            'payout_range': '$5-$10 per trial'
        }
    
    @staticmethod
    def build_smart_cta(movie, ott_data):
        """
        Generate smart CTAs based on platform availability
        
        Args:
            movie: Movie object
            ott_data: Parsed OTT platforms data
        
        Returns:
            list of CTA dicts with platform, url, text, icon
        """
        config = AffiliateManager.get_config()
        ctas = []
        
        # Check which platforms have this movie
        has_prime = ott_data and any(
            'prime' in str(p).lower() or 'amazon' in str(p).lower() 
            for p in ott_data.keys()
        )
        
        has_apple = ott_data and any(
            'apple' in str(p).lower() 
            for p in ott_data.keys()
        )
        
        # Smart CTA 1: Prime Video (Free Trial angle)
        if has_prime and config.amazon_enabled and config.amazon_associate_id:
            amazon_cta = AffiliateManager.build_amazon_affiliate_url(movie.title)
            if amazon_cta:
                ctas.append({
                    'platform': 'amazon_prime',
                    'text': amazon_cta['cta_text'],
                    'url': amazon_cta['url'],
                    'icon': 'fas fa-amazon',
                    'color': '#FF9900',
                    'payout': 'High Volume (Free Trial Bounty)',
                    'order': 1
                })
        
        # Smart CTA 2: Apple TV+ (Own it angle)
        if has_apple and config.apple_enabled and config.apple_affiliate_id:
            apple_cta = AffiliateManager.build_apple_affiliate_url(movie.title)
            if apple_cta:
                ctas.append({
                    'platform': 'apple_tv',
                    'text': apple_cta['cta_text'],
                    'url': apple_cta['url'],
                    'icon': 'fas fa-apple',
                    'color': '#A2AAAD',
                    'payout': 'High Value (Subscription Bounty)',
                    'order': 2
                })
        
        return sorted(ctas, key=lambda x: x['order'])
    
    @staticmethod
    def check_link_health(movie_id, platform, url):
        """
        Check if affiliate link is alive (returns 200)
        
        Args:
            movie_id: Movie ID
            platform: 'amazon_prime' or 'apple_tv'
            url: Full affiliate URL
        
        Returns:
            dict with 'is_alive', 'status_code', 'error_message'
        """
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            is_alive = response.status_code == 200
            
            # Log health check in database
            check = LinkHealthCheck.query.filter_by(
                movie_id=movie_id,
                platform=platform
            ).first()
            
            if not check:
                check = LinkHealthCheck(
                    movie_id=movie_id,
                    platform=platform,
                    affiliate_url=url
                )
                db.session.add(check)
            
            check.status_code = response.status_code
            check.is_alive = is_alive
            check.error_message = None if is_alive else f"{response.status_code} Error"
            check.last_checked = datetime.now(timezone.utc)
            
            db.session.commit()
            
            return {
                'is_alive': is_alive,
                'status_code': response.status_code,
                'error_message': None if is_alive else f"{response.status_code}"
            }
        
        except requests.Timeout:
            return {'is_alive': False, 'status_code': 0, 'error_message': 'Timeout'}
        except Exception as e:
            logger.error(f"Link health check failed for {url}: {str(e)}")
            return {'is_alive': False, 'status_code': 0, 'error_message': str(e)}
    
    @staticmethod
    def detect_price_drop(movie_id, platform, old_price, new_price, currency='INR'):
        """
        Detect and log price drops for viral marketing opportunities
        
        Args:
            movie_id: Movie ID
            platform: 'amazon_prime' or 'apple_tv'
            old_price: Previous price
            new_price: Current price
        
        Returns:
            PriceDrop object if price dropped significantly
        """
        if old_price and new_price and old_price > new_price:
            discount = ((old_price - new_price) / old_price) * 100
            
            # Only track if significant drop (>10%)
            if discount > 10:
                price_drop = PriceDrop(
                    movie_id=movie_id,
                    platform=platform,
                    previous_price=old_price,
                    current_price=new_price,
                    discount_percentage=discount,
                    currency=currency
                )
                db.session.add(price_drop)
                db.session.commit()
                
                logger.info(f"Price drop detected: {platform} - {discount:.1f}% off")
                return price_drop
        
        return None
    
    @staticmethod
    def get_price_drops_for_posting(days=1):
        """
        Get recent price drops ready to post on Twitter/Telegram
        
        Args:
            days: How many days back to check
        
        Returns:
            list of PriceDrop objects
        """
        from sqlalchemy import func
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        drops = PriceDrop.query.filter(
            PriceDrop.detected_at >= cutoff,
            PriceDrop.posted_to_twitter == False
        ).order_by(PriceDrop.discount_percentage.desc()).all()
        
        return drops
    
    @staticmethod
    def format_price_drop_tweet(price_drop, movie):
        """
        Format price drop for Twitter posting
        
        Returns:
            str: Tweet text (max 280 chars)
        """
        discount = price_drop.discount_percentage
        old_price = price_drop.previous_price
        new_price = price_drop.current_price
        platform = '🎬 Apple TV+' if 'apple' in price_drop.platform else '📺 Prime Video'
        
        tweet = f"🔥 PRICE DROP! {movie.title}\n{platform}\n₹{old_price} → ₹{new_price} (-{discount:.0f}%)\n\n🎥 Watch now 👉 [link]"
        
        return tweet[:280]  # Ensure under 280 chars


class AffiliateAnalytics:
    """Track affiliate performance and earnings"""
    
    @staticmethod
    def get_healthy_affiliate_links():
        """Get all live affiliate links (not dead)"""
        return LinkHealthCheck.query.filter_by(is_alive=True).all()
    
    @staticmethod
    def get_dead_affiliate_links():
        """Alert if any affiliate links are dead (need to fix)"""
        dead_links = LinkHealthCheck.query.filter_by(is_alive=False).all()
        
        if dead_links:
            logger.warning(f"⚠️ {len(dead_links)} dead affiliate links detected!")
            for link in dead_links:
                movie = Movie.query.get(link.movie_id)
                logger.warning(f"  - {movie.title} ({link.platform}): {link.error_message}")
        
        return dead_links
    
    @staticmethod
    def get_high_potential_products():
        """Get movies with highest price drops for focused marketing"""
        top_drops = PriceDrop.query.order_by(
            PriceDrop.discount_percentage.desc()
        ).limit(10).all()
        
        return top_drops


# Initialize on app startup
def init_affiliate_config(app):
    """Initialize affiliate system on app startup"""
    with app.app_context():
        config = AffiliateManager.get_config()
        
        # Log affiliate setup status
        if config.amazon_associate_id:
            logger.info(f"✓ Amazon affiliate setup: {config.amazon_associate_id}")
        else:
            logger.warning("⚠️ Amazon affiliate ID not configured")
        
        if config.apple_affiliate_id:
            logger.info(f"✓ Apple affiliate setup: {config.apple_affiliate_id}")
        else:
            logger.warning("⚠️ Apple affiliate ID not configured")
        
        # Run link health checks on startup
        if config.link_health_check_enabled:
            logger.info("🔗 Running affiliate link health checks...")
            _run_health_checks()


def _run_health_checks():
    """Internal: Run health checks on all affiliate links"""
    # This will be called periodically by scheduler
    pass
