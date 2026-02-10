#!/usr/bin/env python3
"""
OTT Release Features: Countdown & Reminders

This module demonstrates how to use the ott_release_date field for:
1. Countdown timers for upcoming OTT releases
2. Release reminders/notifications
3. "Coming Soon to OTT" listings
"""

import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Movie
from sqlalchemy import and_, or_


def get_upcoming_ott_releases(days_ahead=30):
    """Get movies releasing on OTT in the next N days
    
    Args:
        days_ahead: Number of days to look ahead (default: 30)
    
    Returns:
        list: Movies with upcoming OTT releases
    """
    today = datetime.now().date()
    future_date = today + timedelta(days=days_ahead)
    
    with app.app_context():
        movies = Movie.query.filter(
            and_(
                Movie.ott_release_date != None,
                Movie.ott_release_date != '',
                Movie.ott_release_date >= today.strftime('%Y-%m-%d'),
                Movie.ott_release_date <= future_date.strftime('%Y-%m-%d')
            )
        ).order_by(Movie.ott_release_date.asc()).all()
        
        return movies


def calculate_countdown(ott_release_date):
    """Calculate days/hours until OTT release
    
    Args:
        ott_release_date: Release date in YYYY-MM-DD format
    
    Returns:
        dict: {
            'days': int,
            'hours': int,
            'is_today': bool,
            'is_past': bool,
            'formatted': str (e.g., "5 days, 3 hours")
        }
    """
    if not ott_release_date:
        return None
    
    try:
        release_dt = datetime.strptime(ott_release_date, '%Y-%m-%d')
        now = datetime.now()
        
        diff = release_dt - now
        
        if diff.days < 0:
            return {
                'days': 0,
                'hours': 0,
                'is_today': False,
                'is_past': True,
                'formatted': 'Already released'
            }
        
        days = diff.days
        hours = diff.seconds // 3600
        
        is_today = days == 0
        
        if is_today:
            formatted = f"{hours} hours"
        elif days == 1:
            formatted = "Tomorrow"
        else:
            formatted = f"{days} days"
        
        return {
            'days': days,
            'hours': hours,
            'is_today': is_today,
            'is_past': False,
            'formatted': formatted
        }
    
    except:
        return None


def get_movies_releasing_today():
    """Get movies releasing on OTT today
    
    Returns:
        list: Movies releasing today
    """
    today = datetime.now().date().strftime('%Y-%m-%d')
    
    with app.app_context():
        movies = Movie.query.filter(
            Movie.ott_release_date == today
        ).all()
        
        return movies


def get_reminder_candidates(days_before=3):
    """Get movies that should trigger reminders
    
    Args:
        days_before: Send reminder N days before release (default: 3)
    
    Returns:
        list: Movies releasing in N days (reminder time)
    """
    reminder_date = (datetime.now().date() + timedelta(days=days_before)).strftime('%Y-%m-%d')
    
    with app.app_context():
        movies = Movie.query.filter(
            Movie.ott_release_date == reminder_date
        ).all()
        
        return movies


def format_ott_release_display(movie):
    """Format OTT release info for display
    
    Args:
        movie: Movie object
    
    Returns:
        dict: Display-ready information
    """
    if not movie.ott_release_date:
        return {
            'status': 'unknown',
            'message': 'OTT release date not available',
            'countdown': None
        }
    
    countdown = calculate_countdown(movie.ott_release_date)
    
    if not countdown:
        return {
            'status': 'error',
            'message': 'Invalid date format',
            'countdown': None
        }
    
    if countdown['is_past']:
        status = 'released'
        message = f"Released on OTT: {movie.ott_release_date}"
    elif countdown['is_today']:
        status = 'today'
        message = f"🔥 Releasing TODAY in {countdown['hours']} hours!"
    else:
        status = 'upcoming'
        message = f"📅 Releasing in {countdown['formatted']}"
    
    return {
        'status': status,
        'message': message,
        'countdown': countdown,
        'date': movie.ott_release_date
    }


# ============================================================
# Example Usage / Demo
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("OTT RELEASE FEATURES - DEMO")
    print("=" * 60)
    
    # 1. Upcoming releases in next 30 days
    print("\n📅 UPCOMING OTT RELEASES (Next 30 days):")
    print("-" * 60)
    upcoming = get_upcoming_ott_releases(days_ahead=30)
    
    if upcoming:
        for movie in upcoming[:10]:  # Show first 10
            display = format_ott_release_display(movie)
            print(f"\n[{movie.id}] {movie.title}")
            print(f"    {display['message']}")
            if display['countdown']:
                print(f"    Days: {display['countdown']['days']}, Hours: {display['countdown']['hours']}")
    else:
        print("No upcoming OTT releases found in the database")
        print("\nTo populate OTT release dates, run:")
        print("  python scripts/enrich_metadata_trailers.py --limit 500 --force")
    
    # 2. Movies releasing today
    print("\n\n🔥 RELEASING TODAY:")
    print("-" * 60)
    today_releases = get_movies_releasing_today()
    
    if today_releases:
        for movie in today_releases:
            print(f"[{movie.id}] {movie.title}")
            ott_platforms = movie.get_ott_platforms()
            if ott_platforms:
                platforms = ', '.join(ott_platforms.keys())
                print(f"    Available on: {platforms}")
    else:
        print("No movies releasing on OTT today")
    
    # 3. Reminder candidates (3 days before release)
    print("\n\n🔔 REMINDER CANDIDATES (releasing in 3 days):")
    print("-" * 60)
    reminders = get_reminder_candidates(days_before=3)
    
    if reminders:
        for movie in reminders:
            print(f"[{movie.id}] {movie.title} - {movie.ott_release_date}")
            print(f"    💡 Send reminder: '{movie.title}' releasing on OTT in 3 days!")
    else:
        print("No movies found releasing in exactly 3 days")
    
    print("\n" + "=" * 60)
    print("Feature ideas:")
    print("  1. Daily email: 'Movies releasing on OTT this week'")
    print("  2. Homepage widget: 'Coming Soon to OTT' with countdown")
    print("  3. WhatsApp/Telegram bot: Send reminders 3 days before")
    print("  4. Calendar export: Add OTT releases to Google Calendar")
    print("=" * 60)
