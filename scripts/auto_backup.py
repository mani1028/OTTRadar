"""
Automatic database backup scheduler
Runs daily to prevent data loss
Can be scheduled with Windows Task Scheduler or run manually
Usage: python -m scripts.auto_backup
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path

def cleanup_old_backups(max_backups=7):
    """Keep only the latest N backups"""
    exports_dir = Path('exports')
    if not exports_dir.exists():
        return
    
    backups = sorted(exports_dir.glob('movies_backup_*.json'))
    
    # Delete old backups
    if len(backups) > max_backups:
        for backup in backups[:-max_backups]:
            backup.unlink()
            print(f"   Deleted old backup: {backup.name}")

def auto_backup():
    """Create automatic backup and cleanup old ones"""
    from app import app
    from models import Movie
    
    with app.app_context():
        movies = Movie.query.all()
        
        if not movies:
            print("⚠️  Database is empty - skipping backup")
            return
        
        # Create exports directory
        os.makedirs('exports', exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'exports/movies_backup_{timestamp}.json'
        
        # Export data
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_movies': len(movies),
            'movies': [movie.to_dict() for movie in movies]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print("=" * 70)
        print(f"✅ AUTO-BACKUP COMPLETED")
        print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   File: {filename}")
        print(f"   Movies: {len(movies)}")
        print(f"   Size: {os.path.getsize(filename) / 1024:.1f} KB")
        print("=" * 70)
        
        # Cleanup old backups (keep last 7)
        cleanup_old_backups(max_backups=7)
        
        # Also create a "latest" symlink/copy for easy access
        latest_file = 'exports/movies_backup_latest.json'
        shutil.copy2(filename, latest_file)
        print(f"   Latest backup: {latest_file}")

if __name__ == '__main__':
    auto_backup()
