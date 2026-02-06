"""
Daily OTT Snapshot Recording
Records platform statistics for dashboard time-series analysis
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from models import db, Movie, OTTSnapshot
from datetime import datetime, timezone
from sqlalchemy import func

def record_daily_snapshot():
    """Record daily platform statistics"""
    with app.app_context():
        print("🎬 Recording Daily OTT Snapshot...")
        
        try:
            # Get all movies with OTT data
            all_movies = Movie.query.all()
            
            # Count by platform
            platform_counts = {}
            free_count = 0
            total_with_ott = 0
            
            for movie in all_movies:
                if movie.ott_data:
                    platforms = movie.get_ott_platforms()
                    if platforms:
                        total_with_ott += 1
                        
                        for platform_name, data in platforms.items():
                            # Count by platform
                            if platform_name not in platform_counts:
                                platform_counts[platform_name] = 0
                            platform_counts[platform_name] += 1
                            
                            # Count free content
                            if isinstance(data, dict) and data.get('is_free'):
                                free_count += 1
                                break  # Only count movie once for free
            
            # Extract individual platform counts
            netflix_count = platform_counts.get('Netflix', 0)
            prime_count = platform_counts.get('Prime Video', 0)
            hotstar_count = platform_counts.get('Disney+ Hotstar', 0)
            
            # Create snapshot
            snapshot = OTTSnapshot(
                date=datetime.now(timezone.utc).date(),
                netflix_count=netflix_count,
                prime_count=prime_count,
                hotstar_count=hotstar_count,
                total_count=total_with_ott,
                free_count=free_count
            )
            snapshot.set_platforms(platform_counts)
            
            # Check if snapshot for today already exists
            existing = OTTSnapshot.query.filter_by(date=snapshot.date).first()
            if existing:
                # Update existing
                existing.netflix_count = netflix_count
                existing.prime_count = prime_count
                existing.hotstar_count = hotstar_count
                existing.total_count = total_with_ott
                existing.free_count = free_count
                existing.set_platforms(platform_counts)
                print(f"✓ Updated snapshot for {snapshot.date}")
            else:
                # Create new
                db.session.add(snapshot)
                print(f"✓ Created snapshot for {snapshot.date}")
            
            db.session.commit()
            
            print(f"\n📊 Snapshot Summary:")
            print(f"  Total movies with OTT: {total_with_ott}")
            print(f"  Netflix: {netflix_count}")
            print(f"  Prime Video: {prime_count}")
            print(f"  Disney+ Hotstar: {hotstar_count}")
            print(f"  Free content: {free_count}")
            print(f"  Unique platforms: {len(platform_counts)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error recording snapshot: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    success = record_daily_snapshot()
    sys.exit(0 if success else 1)
