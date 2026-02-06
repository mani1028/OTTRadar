"""
Import movies from JSON backup file to database
Usage: python -m scripts.import_db exports/movies_backup_20260203_120000.json
"""

import json
import sys
import os

def import_database(filename=None):
    """Import movies from JSON file"""
    from app import app
    from models import db, Movie
    
    # Get filename from argument or use latest backup
    if not filename:
        if len(sys.argv) > 1:
            filename = sys.argv[1]
        else:
            # Find latest backup
            if os.path.exists('exports'):
                backups = [f for f in os.listdir('exports') if f.endswith('.json')]
                if backups:
                    filename = f'exports/{sorted(backups)[-1]}'
                else:
                    print("❌ No backup files found in exports/")
                    return
            else:
                print("❌ No exports directory found")
                print("💡 Usage: python -m scripts.import_db <filename>")
                return
    
    if not os.path.exists(filename):
        print(f"❌ File not found: {filename}")
        return
    
    with app.app_context():
        # Load JSON data
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        movies_data = data.get('movies', [])
        
        if not movies_data:
            print("⚠️  No movies found in backup file")
            return
        
        print("=" * 70)
        print(f"IMPORTING FROM: {filename}")
        print(f"Backup date: {data.get('export_date', 'Unknown')}")
        print(f"Movies in backup: {len(movies_data)}")
        print("=" * 70)
        
        added = 0
        updated = 0
        skipped = 0
        
        for movie_dict in movies_data:
            try:
                tmdb_id = movie_dict.get('tmdb_id')
                
                if not tmdb_id:
                    skipped += 1
                    continue
                
                # Check if movie exists
                existing = Movie.query.filter_by(tmdb_id=tmdb_id).first()
                
                if existing:
                    # Update existing movie
                    existing.title = movie_dict.get('title', existing.title)
                    existing.poster = movie_dict.get('poster', existing.poster)
                    existing.backdrop = movie_dict.get('backdrop', existing.backdrop)
                    existing.overview = movie_dict.get('overview', existing.overview)
                    existing.release_date = movie_dict.get('release_date', existing.release_date)
                    existing.rating = movie_dict.get('rating', existing.rating)
                    existing.language = movie_dict.get('language', existing.language)
                    existing.runtime = movie_dict.get('runtime', existing.runtime)
                    existing.genres = movie_dict.get('genres', existing.genres)
                    existing.cast = movie_dict.get('cast', existing.cast)
                    existing.certification = movie_dict.get('certification', existing.certification)
                    existing.popularity = movie_dict.get('popularity', existing.popularity)
                    existing.is_dubbed = movie_dict.get('is_dubbed', existing.is_dubbed)
                    existing.trailer = movie_dict.get('trailer', existing.trailer)
                    existing.set_ott_platforms(movie_dict.get('ott_platforms', {}))
                    updated += 1
                else:
                    # Create new movie
                    new_movie = Movie(
                        tmdb_id=tmdb_id,
                        title=movie_dict.get('title', ''),
                        poster=movie_dict.get('poster', ''),
                        backdrop=movie_dict.get('backdrop', ''),
                        overview=movie_dict.get('overview', ''),
                        release_date=movie_dict.get('release_date', ''),
                        rating=movie_dict.get('rating', 0),
                        language=movie_dict.get('language', 'te'),
                        runtime=movie_dict.get('runtime', 0),
                        genres=movie_dict.get('genres', ''),
                        cast=movie_dict.get('cast', ''),
                        certification=movie_dict.get('certification', ''),
                        popularity=movie_dict.get('popularity', 0),
                        is_dubbed=movie_dict.get('is_dubbed', False),
                        trailer=movie_dict.get('trailer', '')
                    )
                    new_movie.set_ott_platforms(movie_dict.get('ott_platforms', {}))
                    db.session.add(new_movie)
                    added += 1
                
                # Commit every 100 movies
                if (added + updated) % 100 == 0:
                    db.session.commit()
                    print(f"   Progress: {added + updated}/{len(movies_data)} movies...")
            
            except Exception as e:
                db.session.rollback()
                skipped += 1
                continue
        
        # Final commit
        db.session.commit()
        
        print("\n" + "=" * 70)
        print(f"✅ IMPORT COMPLETED!")
        print(f"   New movies added: {added}")
        print(f"   Existing updated: {updated}")
        print(f"   Skipped: {skipped}")
        print(f"   Total in database: {Movie.query.count()}")
        print("=" * 70)

if __name__ == '__main__':
    import_database()
