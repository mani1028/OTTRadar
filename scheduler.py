"""
Scheduler for automated movie updates
Handles daily fetches and weekly OTT provider updates with robust error handling
"""

import schedule
import time
import threading
from datetime import datetime
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

# ============================================
# SESSION MANAGEMENT FOR API CALLS
# ============================================

def create_session():
    """Create requests session with retry strategy"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 429]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

API_SESSION = create_session()
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

def run_scheduled_jobs():
    """
    Run scheduled jobs in a separate thread
    Configure jobs in this function
    """
    
    # Schedule daily fetch at 9 AM
    schedule.every().day.at("09:00").do(daily_fetch_job)
    
    # Schedule weekly refresh on Sunday at 9 AM
    schedule.every().sunday.at("09:00").do(weekly_refresh_job)
    
    # Schedule daily OTT snapshot recording at 11 PM
    schedule.every().day.at("23:00").do(snapshot_recording_job)
    
    print("Scheduler initialized")
    
    # Keep running scheduler
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Scheduler error: {str(e)}")
            time.sleep(60)

def daily_fetch_job():
    """
    Daily job to fetch new Telugu movies with robust error handling
    """
    print(f"\nDaily fetch started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        from scripts.scraper_service import run_scraper
        run_scraper()
        print(f"Daily fetch completed\n")
    except Exception as e:
        print(f"Daily fetch failed: {str(e)}\n")

def weekly_refresh_job():
    """
    Weekly job to update OTT availability with robust error handling
    """
    print(f"\nWeekly refresh started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        from scripts.weekly_refresh import refresh_ott_providers
        refresh_ott_providers()
        print(f"Weekly refresh completed\n")
    except Exception as e:
        print(f"Weekly refresh failed: {str(e)}\n")

def snapshot_recording_job():
    """
    Daily job to record OTT platform statistics snapshot
    """
    print(f"\nSnapshot recording started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        from scripts.record_snapshot import record_daily_snapshot
        record_daily_snapshot()
        print(f"Snapshot recording completed\n")
    except Exception as e:
        print(f"Snapshot recording failed: {str(e)}\n")

def start_scheduler_thread():
    """
    Start scheduler in a background thread
    Called from Flask app
    """
    try:
        scheduler_thread = threading.Thread(target=run_scheduled_jobs, daemon=True)
        scheduler_thread.start()
        print("Scheduler thread started (background)")
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")

if __name__ == '__main__':
    # If running this file directly, start the scheduler
    print("Starting OTT Tracker Scheduler...")
    print("Press Ctrl+C to stop\n")
    
    try:
        run_scheduled_jobs()
    except KeyboardInterrupt:
        print("\n\nScheduler stopped")
