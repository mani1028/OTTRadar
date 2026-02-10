#!/usr/bin/env python3
"""
Background Scheduler for OTT Updates
Runs daily at midnight to check for newly released OTT movies

Usage: python scripts/scheduler_background.py
This runs in background and keeps the scheduled jobs going
"""

import sys
import time
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    print("[WARNING] APScheduler not installed. Install with: pip install apscheduler")


def run_daily_ott_check():
    """Run the daily OTT checker"""
    from scripts.daily_ott_checker import check_unreleased_releases, print_upcoming_summary
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SCHEDULER] Running scheduled OTT check...")
    
    try:
        check_unreleased_releases()
        print_upcoming_summary(days=31)
        print("[OK] Scheduled check complete")
    except Exception as e:
        print(f"[ERROR] in scheduled check: {e}")


def run_slow_sync_modern():
    """Discover 50 new Telugu movies from 2024-2025 (Slow Growth Strategy)"""
    import subprocess
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SLOW-SYNC] Discovering recent movies (2024-2025)...")
    
    try:
        # Accelerated: Increase limit and pages
        result = subprocess.run(
            [sys.executable, 'scripts/discover_new_movies.py', '--year', '2024', '--limit', '200', '--pages', '10'],
            capture_output=True,
            text=True,
            timeout=1200
        )
        if result.returncode == 0:
            print("[OK] Modern movies discovery complete")
        else:
            print(f"[WARNING] Discovery returned code {result.returncode}")
            if result.stderr:
                print(f"[ERROR] {result.stderr}")
    except Exception as e:
        print(f"[ERROR] in modern movies discovery: {e}")


def run_slow_sync_classic():
    """Discover 50 classic Telugu movies from 1990-2000 (Slow Growth Strategy)"""
    import subprocess
    import random
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SLOW-SYNC] Discovering classic movies (1990-2000)...")
    
    # Randomize year to distribute discovery over weeks
    classic_years = list(range(1990, 2001))
    selected_year = random.choice(classic_years)
    
    try:
        result = subprocess.run(
            [sys.executable, 'scripts/discover_new_movies.py', '--year', str(selected_year), '--limit', '200', '--pages', '10'],
            capture_output=True,
            text=True,
            timeout=1200
        )
        
        if result.returncode == 0:
            print(f"[OK] Classic movies discovery complete (year: {selected_year})")
        else:
            print(f"[WARNING] Discovery returned code {result.returncode}")
            if result.stderr:
                print(f"[ERROR] {result.stderr}")
    except Exception as e:
        print(f"[ERROR] in classic movies discovery: {e}")


def run_slow_sync_2020s():
    """Discover 50 Telugu movies from 2010-2020 (Middle era)"""
    import subprocess
    import random
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SLOW-SYNC] Discovering 2010s movies...")
    
    decade_years = list(range(2010, 2024))
    selected_year = random.choice(decade_years)
    
    try:
        result = subprocess.run(
            [sys.executable, 'scripts/discover_new_movies.py', '--year', str(selected_year), '--limit', '200', '--pages', '10'],
            capture_output=True,
            text=True,
            timeout=1200
        )
        
        if result.returncode == 0:
            print(f"[OK] 2010s movies discovery complete (year: {selected_year})")
        else:
            print(f"[WARNING] Discovery returned code {result.returncode}")
    except Exception as e:
        print(f"[ERROR] in 2010s movies discovery: {e}")


def run_slow_sync_hindi_dubbed():
    """Discover 50 popular Hindi movies to add as dubbed Telugu content"""
    import subprocess
    import random
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SLOW-SYNC] Discovering Hindi dubbed movies...")
    
    # Random year from 2015-2025 (peak Hindi movie production)
    hindi_years = list(range(2015, 2026))
    selected_year = random.choice(hindi_years)
    
    try:
        result = subprocess.run(
            [sys.executable, 'scripts/discover_new_movies.py', 
             '--year', str(selected_year), 
             '--language', 'hi', 
             '--dubbed',
             '--limit', '200', 
             '--pages', '10'],
            capture_output=True,
            text=True,
            timeout=1200
        )
        
        if result.returncode == 0:
            print(f"[OK] Hindi dubbed discovery complete (year: {selected_year})")
        else:
            print(f"[WARNING] Discovery returned code {result.returncode}")
            if result.stderr:
                print(f"[ERROR] {result.stderr}")
    except Exception as e:
        print(f"[ERROR] in Hindi dubbed discovery: {e}")


def setup_scheduler():
    """Setup background scheduler"""
    if not HAS_SCHEDULER:
        print("[ERROR] APScheduler required for scheduling")
        return None
    
    scheduler = BackgroundScheduler()
    
    # Run daily at midnight (00:00)
    scheduler.add_job(
        run_daily_ott_check,
        trigger=CronTrigger(hour=0, minute=0),
        id='daily_ott_check',
        name='Daily OTT Release Check',
        replace_existing=True
    )
    
    # Also run on startup
    scheduler.add_job(
        run_daily_ott_check,
        id='startup_ott_check',
        name='Startup OTT Check',
        replace_existing=True
    )
    
    # ===== SMART SLOW GROWTH STRATEGY (4 Batches Per Day) =====
    # Smart offset tracking prevents re-discovering same movies
    # Each batch targets different era: Modern, 2010s, 2000s, Classic
    
    # Accelerated: Run all jobs every 2 hours for 1 week
    for hour in range(0, 24, 2):
        scheduler.add_job(
            run_slow_sync_modern,
            trigger=CronTrigger(hour=hour, minute=0),
            id=f'accel_sync_modern_{hour}',
            name=f'Accelerated Sync - Modern Movies (2024-2025) [{hour}:00]',
            replace_existing=True
        )
        scheduler.add_job(
            run_slow_sync_2020s,
            trigger=CronTrigger(hour=hour, minute=10),
            id=f'accel_sync_2010s_{hour}',
            name=f'Accelerated Sync - 2010s Movies [{hour}:10]',
            replace_existing=True
        )
        scheduler.add_job(
            run_slow_sync_classic,
            trigger=CronTrigger(hour=hour, minute=20),
            id=f'accel_sync_classic_{hour}',
            name=f'Accelerated Sync - Classic Movies (1990-2000) [{hour}:20]',
            replace_existing=True
        )
        scheduler.add_job(
            run_slow_sync_hindi_dubbed,
            trigger=CronTrigger(hour=hour, minute=30),
            id=f'accel_sync_hindi_{hour}',
            name=f'Accelerated Sync - Hindi Dubbed (2015-2025) [{hour}:30]',
            replace_existing=True
        )
        # Add parallel multi-language discovery (English, Tamil, Malayalam)
        for lang, min_ in [('en', 40), ('ta', 45), ('ml', 50)]:
            def make_lang_job(language):
                def job():
                    import subprocess, random
                    year = random.choice(range(2010, 2026))
                    subprocess.run([
                        sys.executable, 'scripts/discover_new_movies.py',
                        '--year', str(year),
                        '--language', language,
                        '--limit', '200',
                        '--pages', '10'
                    ], timeout=1200)
                return job
            scheduler.add_job(
                make_lang_job(lang),
                trigger=CronTrigger(hour=hour, minute=min_),
                id=f'accel_sync_{lang}_{hour}',
                name=f'Accelerated Sync - {lang.upper()} [{hour}:{min_}]',
                replace_existing=True
            )
    
    scheduler.start()
    
    print("=" * 70)
    print("[SCHEDULER] BACKGROUND SCHEDULER STARTED")
    print("=" * 70)
    print("[OK] Daily OTT check scheduled for: 00:00 (Midnight)")
    print("")
    print("SMART SLOW GROWTH STRATEGY (5 batches/day):")
    print("  02:00 AM ─ Telugu Originals (2024-2025) - 50 movies")
    print("  06:00 AM ─ Telugu Originals (random 2010-2023) - 50 movies")
    print("  10:00 AM ─ Telugu Originals (random 2000-2010) - 50 movies")
    print("  14:00 PM ─ Telugu Originals (random 1990-2000) - 50 movies")
    print("  18:00 PM ─ Hindi Dubbed (2015-2025) - 50 movies [NEW]")
    print("")
    print("Expected Growth:")
    print("  ├─ ~200-250 NEW movies/day (Telugu + Hindi dubbed)")
    print("  ├─ ~6,000-7,500 new movies/month")
    print("  ├─ Smart offset tracking prevents re-discovering")
    print("  ├─ Hindi dubs marked with: is_dubbed=True, has_telugu_audio=True")
    print("  └─ Timeline to 25,000: ~4 months")
    print("")
    print("Keep this window open for scheduled jobs to run")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    
    try:
        # Keep scheduler running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Scheduler stopped")
        scheduler.shutdown()


def main():
    """Main entry point"""
    if not HAS_SCHEDULER:
        print("\n[ERROR] APScheduler not found!")
        print("Install it with: pip install apscheduler")
        print("\nOr run the checker manually:")
        print("  python scripts/daily_ott_checker.py")
        return
    
    setup_scheduler()


if __name__ == '__main__':
    main()

