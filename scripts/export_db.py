"""
Export all movies from database to JSON file
Creates a timestamped backup that can be imported later
Usage: python -m scripts.export_db
"""

import json
import os
from datetime import datetime

def export_database():
    """Export all movies to JSON file"""
    from app import app
    from models import Movie
    
    with app.app_context():
        movies = Movie.query.all()
        
        if not movies:
            print("⚠️  Database is empty - nothing to export")
            return
        
        # Create exports directory if it doesn't exist
        os.makedirs('exports', exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'exports/movies_backup_{timestamp}.json'
        
        # Convert movies to dict
        export_data = {
            'export_date': datetime.now().isoformat(),
            'total_movies': len(movies),
            'movies': [movie.to_dict() for movie in movies]
        }
        
        # Write to JSON file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print("=" * 70)
        print(f"✅ DATABASE EXPORTED SUCCESSFULLY")
        print(f"   File: {filename}")
        print(f"   Movies: {len(movies)}")
        print(f"   Size: {os.path.getsize(filename) / 1024:.1f} KB")
        print("=" * 70)
        print(f"\n💡 To restore: python -m scripts.import_db {filename}")

if __name__ == '__main__':
    export_database()
