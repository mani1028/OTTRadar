"""
Database Initialization Module
Automatically creates database and folder structure on app startup
Can also be called directly for manual initialization

Usage:
    From Python: from db_init import init_database; init_database()
    Manual: python -c "from db_init import init_database; init_database()"
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def ensure_folders():
    """Create necessary folders if they don't exist"""
    folders = ['instance', 'logs', 'exports', 'static/css', 'static/js', 'templates']
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)


def ensure_env_file():
    """Create .env file if it doesn't exist"""
    env_path = Path('.env')
    
    if not env_path.exists():
        print("[DB_INIT] Creating .env file...")
        env_path.write_text(
            "# OTT RADAR Environment Variables\n"
            "# Replace 'your-key-here' with actual values\n\n"
            "# Flask Secret Key (auto-generated below)\n"
            "SECRET_KEY=change-me-to-a-real-secret-key\n\n"
            "# TMDB API Key (get from https://www.themoviedb.org/settings/api)\n"
            "TMDB_API_KEY=your-tmdb-api-key-here\n\n"
            "# Admin Credentials\n"
            "ADMIN_USERNAME=admin\n"
            "ADMIN_PASSWORD=admin\n\n"
            "# Environment\n"
            "FLASK_ENV=development\n"
            "DEBUG=True\n"
        )
        print("[DB_INIT] ✅ Created .env file (edit with your API keys)")
    
    # Ensure SECRET_KEY is set
    load_dotenv()
    if not os.getenv('SECRET_KEY') or os.getenv('SECRET_KEY') == 'change-me-to-a-real-secret-key':
        import secrets
        new_key = secrets.token_hex(32)
        with open('.env', 'r') as f:
            content = f.read()
        content = content.replace('SECRET_KEY=change-me-to-a-real-secret-key', f'SECRET_KEY={new_key}')
        with open('.env', 'w') as f:
            f.write(content)
        os.environ['SECRET_KEY'] = new_key
        print(f"[DB_INIT] ✅ Generated SECRET_KEY")


def init_database(verbose=False):
    """
    Initialize database tables if they don't exist
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create folders
        ensure_folders()
        
        # Ensure .env exists
        ensure_env_file()
        
        # Import app and create tables
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Count existing movies
            from models import Movie
            movie_count = Movie.query.count()
            
            if verbose:
                print("[DB_INIT] ✅ Database initialized")
                print(f"[DB_INIT] 📊 Movies in database: {movie_count}")
            
            return True
    
    except Exception as e:
        if verbose:
            print(f"[DB_INIT] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    init_database(verbose=True)
