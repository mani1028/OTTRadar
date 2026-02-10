#!/usr/bin/env python3
"""
Database migration: Add ott_release_date column

This adds a new column to track when movies will be released on OTT platforms,
enabling countdown timers and release reminders.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db
from sqlalchemy import text

def migrate():
    """Add ott_release_date column to movies table"""
    
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM pragma_table_info('movies') WHERE name='ott_release_date'"
            ))
            exists = result.scalar() > 0
            
            if exists:
                print("✅ Column 'ott_release_date' already exists - skipping migration")
                return
            
            # Add the new column
            print("📝 Adding 'ott_release_date' column to movies table...")
            db.session.execute(text(
                "ALTER TABLE movies ADD COLUMN ott_release_date VARCHAR(10)"
            ))
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            print("   - Added: ott_release_date (VARCHAR(10)) - Format: YYYY-MM-DD")
            print("\nNext steps:")
            print("1. Run enrichment to populate OTT release dates:")
            print("   python scripts/enrich_metadata_trailers.py --limit 500 --force")
            print("\n2. Build features like:")
            print("   - Countdown timers for upcoming OTT releases")
            print("   - Email/notification reminders")
            print("   - 'Coming to OTT' page")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()

if __name__ == '__main__':
    migrate()
