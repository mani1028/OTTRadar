"""
Refresh all OTT links from JustWatch and wipe TMDB links.
Run this to update all movies with fresh deep links.
Supports resume from last checkpoint if interrupted.
Usage: python -m scripts.refresh_ott_links
"""

import time
import json
import os
from datetime import datetime, timezone

from app import app
from models import db, Movie
from ott_links import fetch_justwatch_links


CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), '..', 'refresh_checkpoint.json')


def load_checkpoint():
    """Load progress from checkpoint file"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None


def save_checkpoint(data):
    """Save progress to checkpoint file"""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def refresh_all_links(resume=True):
    """Refresh OTT links for all movies from JustWatch with resume capability"""
    with app.app_context():
        print("\n🔄 Refreshing OTT links from JustWatch...")
        print("=" * 70)

        movies = Movie.query.filter_by(is_active=True).all()
        total = len(movies)

        if total == 0:
            print("⚠️  No movies in database.")
            return

        # Load checkpoint if resuming
        checkpoint = None
        start_idx = 0
        if resume:
            checkpoint = load_checkpoint()
            if checkpoint:
                start_idx = checkpoint.get('last_processed_idx', 0)
                print(f"📌 Resuming from movie {start_idx}/{total}")
                print(f"   Previously found: {checkpoint.get('found_links', 0)} with links")
                print(f"   Previous failures: {checkpoint.get('failed', 0)}\n")

        print(f"📺 Processing {total - start_idx} remaining movies (out of {total})...\n")

        updated = 0
        found_links = checkpoint.get('found_links', 0) if checkpoint else 0
        no_links = 0
        failed = checkpoint.get('failed', 0) if checkpoint else 0

        for idx in range(start_idx, total):
            movie = movies[idx]
            try:
                # Fetch fresh links from JustWatch
                providers = fetch_justwatch_links(
                    movie.title, movie.release_date, country="IN"
                )

                if providers:
                    movie.set_ott_platforms(providers)
                    found_links += 1
                    updated += 1
                else:
                    # Clear old TMDB links if no JustWatch links found
                    movie.ott_platforms = "{}"
                    no_links += 1
                    updated += 1

                movie.last_updated = datetime.now(timezone.utc)

                # Save checkpoint after every movie (for safety)
                if (idx + 1) % 10 == 0:  # Show progress every 10 movies
                    db.session.commit()
                    percent = ((idx + 1) / total) * 100
                    print(f"   ✅ {idx + 1:>6}/{total} ({percent:>5.1f}%) - {found_links:>4} links")
                    
                    # Save checkpoint for resume capability
                    save_checkpoint({
                        'last_processed_idx': idx + 1,
                        'found_links': found_links,
                        'no_links': no_links,
                        'failed': failed,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                else:
                    # Commit after every movie but show progress less frequently
                    db.session.commit()
                    save_checkpoint({
                        'last_processed_idx': idx + 1,
                        'found_links': found_links,
                        'no_links': no_links,
                        'failed': failed,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })

                # Small delay to be respectful
                time.sleep(0.1)

            except Exception as e:
                failed += 1
                print(f"   ⚠️  Error on {movie.title}: {str(e)[:50]}")
                db.session.rollback()
                continue

        # Final commit
        db.session.commit()

        # Clear checkpoint on successful completion
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            print("\n✓ Checkpoint cleared (completed successfully)")

        print("\n" + "=" * 70)
        print(f"✅ Refresh completed!")
        print(f"   Total processed: {updated}/{total}")
        print(f"   Found links: {found_links}")
        print(f"   No links: {no_links}")
        print(f"   Failed: {failed}")
        
        # Count free content
        all_movies = Movie.query.filter_by(is_active=True).all()
        free_count = sum(1 for m in all_movies if any((v or {}).get('is_free') for v in (m.get_ott_platforms() or {}).values()))
        print(f"   Free content: {free_count}")


if __name__ == "__main__":
    refresh_all_links(resume=True)
