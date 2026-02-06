"""
Database Initialization & Setup Script
One-command setup for OTT RADAR project

Usage:
    python init_db.py                    # Create DB only
    python init_db.py --import           # Create DB + import Telugu movies
    python init_db.py --import --all     # Create DB + import all languages
"""

import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def check_env_file():
    """Check if .env file exists and has required keys"""
    env_path = Path('.env')
    
    if not env_path.exists():
        print_header("⚠️  .env File Not Found")
        print("\nCreating .env file with template...\n")
        
        with open('.env', 'w') as f:
            f.write("# OTT RADAR Environment Variables\n")
            f.write("# Replace 'your-key-here' with actual values\n\n")
            f.write("# Flask Secret Key (generate with: python -c 'import secrets; print(secrets.token_hex(32))')\n")
            f.write("SECRET_KEY=your-secret-key-here\n\n")
            f.write("# TMDB API Key (get from https://www.themoviedb.org/settings/api)\n")
            f.write("TMDB_API_KEY=your-tmdb-api-key-here\n\n")
            f.write("# Admin Credentials\n")
            f.write("ADMIN_USERNAME=admin\n")
            f.write("ADMIN_PASSWORD=your-admin-password-here\n\n")
            f.write("# Environment\n")
            f.write("FLASK_ENV=development\n")
            f.write("DEBUG=True\n")
        
        print("✅ Created .env file")
        print("\n⚠️  IMPORTANT: Edit .env and add your API keys before continuing!\n")
        print("   1. Get TMDB API key from: https://www.themoviedb.org/settings/api")
        print("   2. Generate SECRET_KEY: python -c 'import secrets; print(secrets.token_hex(32))'")
        print("   3. Set ADMIN_PASSWORD for admin panel access\n")
        
        # Try to load existing keys if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            if not os.getenv('TMDB_API_KEY') or os.getenv('TMDB_API_KEY') == 'your-tmdb-api-key-here':
                print("⛔ Cannot continue without valid TMDB_API_KEY")
                sys.exit(1)
        except:
            print("⛔ Please install python-dotenv: pip install python-dotenv")
            sys.exit(1)
    else:
        print("✅ .env file found")


def create_database():
    """Create database tables"""
    print_header("📦 Creating Database")
    
    try:
        from app import app, db
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("\n✅ Database tables created successfully!")
            print("   - movies")
            print("   - user_submissions")
            print("   - watchlist")
            print("   - ott_snapshots")
            
            # Check if database has movies
            from models import Movie
            movie_count = Movie.query.count()
            print(f"\n📊 Current database: {movie_count} movies")
            
            if movie_count == 0:
                print("\n💡 Database is empty. You can import movies with:")
                print("   python init_db.py --import")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False


def import_movies(all_languages=False):
    """Import movies from TMDB"""
    
    if all_languages:
        print_header("🎬 Importing Movies (All Languages)")
        languages = [
            ('te', 'Telugu'),
            ('ta', 'Tamil'),
            ('hi', 'Hindi'),
            ('ml', 'Malayalam'),
            ('kn', 'Kannada'),
            ('en', 'English')
        ]
    else:
        print_header("🎬 Importing Telugu Movies")
        languages = [('te', 'Telugu')]
    
    for lang_code, lang_name in languages:
        print(f"\n📥 Importing {lang_name} movies...")
        print(f"   This may take 10-30 minutes per language...\n")
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'scripts.production_bulk_import', '--language', lang_code],
                check=True,
                capture_output=False
            )
            
            if result.returncode == 0:
                print(f"\n✅ {lang_name} movies imported successfully!")
            else:
                print(f"\n⚠️  {lang_name} import had issues (exit code: {result.returncode})")
                
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error importing {lang_name} movies: {e}")
            continue
        except FileNotFoundError:
            print(f"\n❌ Could not find production_bulk_import script")
            break
    
    print_header("✅ Import Complete")
    print("\n💡 Next steps:")
    print("   1. Run enrichment: python -m scripts.enrich_existing")
    print("   2. Start the app: python app.py")
    print("   3. Visit: http://127.0.0.1:5000\n")


def main():
    """Main setup workflow"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize OTT RADAR database')
    parser.add_argument('--import', dest='do_import', action='store_true',
                        help='Import Telugu movies after creating database')
    parser.add_argument('--all', dest='all_languages', action='store_true',
                        help='Import all languages (use with --import)')
    
    args = parser.parse_args()
    
    print_header("🎬 OTT RADAR - Database Initialization")
    print("\nThis script will set up your database and optionally import movies.\n")
    
    # Step 1: Check environment
    print("Step 1: Checking environment...")
    check_env_file()
    
    # Step 2: Create database
    print("\nStep 2: Creating database tables...")
    if not create_database():
        print("\n❌ Database creation failed. Please fix errors and try again.")
        sys.exit(1)
    
    # Step 3: Import movies (if requested)
    if args.do_import:
        print("\nStep 3: Importing movies...")
        import_movies(all_languages=args.all_languages)
    else:
        print_header("✅ Database Ready")
        print("\n💡 Database created! Next steps:")
        print("   1. Import movies: python init_db.py --import")
        print("   2. Or start app: python app.py (will have empty database)")
        print("   3. Visit: http://127.0.0.1:5000\n")


if __name__ == '__main__':
    main()
