#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily OTT Release Checker
Monitors unreleased OTT movies and moves them to active/trending when released

Usage: python scripts/daily_ott_checker.py
Or add to scheduler: python -m scripts.daily_ott_checker
"""

import sys
import io
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json

# Fix Unicode on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from models import db, Movie


def check_unreleased_releases():
    """Check if any unreleased OTT movies are now available"""
    
    with app.app_context():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        updated_count = 0
        
        # Get all movies with OTT data
        all_movies = Movie.query.filter_by(is_active=True).all()
        
        for movie in all_movies:
            ott_data = movie.get_ott_platforms()
            if not ott_data:
                continue
            
            # Check each OTT platform for release dates
            release_date = movie.get_ott_release_date()
            
            if release_date and release_date <= now:
                # Movie should be released - update last_verified timestamp
                if not movie.last_verified or (now - movie.last_verified).days >= 1:
                    movie.last_verified = datetime.now(timezone.utc).replace(tzinfo=None)
                    movie.last_checked = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.session.add(movie)
                    updated_count += 1
                    
                    # Get platform list
                    platforms = ', '.join(ott_data.keys())
                    print(f"[RELEASED] {movie.title[:50]} | Platforms: {platforms}")
        
        if updated_count > 0:
            db.session.commit()
            print(f"\n[UPDATE] {updated_count} movies marked as released")
        else:
            print("[OK] No newly released OTT movies to update")
        
        return updated_count


def get_upcoming_releases(days=31):
    """Get movies that will be released in next N days"""
    
    with app.app_context():
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now + timedelta(days=days)
        
        upcoming = []
        all_movies = Movie.query.filter_by(is_active=True).all()
        
        for movie in all_movies:
            ott_data = movie.get_ott_platforms()
            if not ott_data:
                continue
            
            release_date = movie.get_ott_release_date()
            
            # If release date is in future but within our window
            if release_date and now < release_date <= cutoff:
                platforms = ', '.join(ott_data.keys())
                days_until = (release_date - now).days
                upcoming.append({
                    'title': movie.title,
                    'release_date': release_date.strftime('%Y-%m-%d'),
                    'platforms': platforms,
                    'days_until': days_until
                })
        
        return upcoming


def print_upcoming_summary(days=31):
    """Print upcoming releases"""
    upcoming = get_upcoming_releases(days)
    
    if not upcoming:
        print(f"[OK] No upcoming OTT releases in next {days} days")
        return
    
    print(f"\n[UPCOMING] OTT RELEASES (Next {days} days):")
    print("=" * 70)
    
    # Sort by days until release
    upcoming = sorted(upcoming, key=lambda x: x['days_until'])
    
    for item in upcoming[:10]:  # Show top 10
        print(f"  [{item['days_until']:2d}d] {item['title'][:45]:45s} | {item['platforms']}")
    
    if len(upcoming) > 10:
        print(f"  ... and {len(upcoming) - 10} more")
    
    print("=" * 70)


def main():
    """Run daily checks"""
    print("=" * 70)
    print(f"[CHECKER] DAILY OTT RELEASE CHECKER")
    print(f"          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Check released movies
    print("\n[CHECKING] for movies that are now released...")
    print("-" * 70)
    check_unreleased_releases()
    
    # Show upcoming
    print()
    print_upcoming_summary(days=31)
    
    print("\n[DONE] Daily check complete!")



if __name__ == '__main__':
    main()
