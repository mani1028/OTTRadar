"""
Enrich existing movies with missing metadata and OTT deep links
Usage: python -m scripts.enrich_existing
"""

import time
from datetime import datetime, timezone

from app import app, fetch_movie_details, fetch_movie_credits, fetch_movie_certification, has_telugu_translation
from models import db, Movie
from ott_links import fetch_justwatch_links


def needs_enrichment(movie):
    """Determine if a movie is missing key fields"""
    ott_data = movie.get_ott_platforms()
    has_ott_links = any((v or {}).get('link') or (v or {}).get('url') for v in ott_data.values())

    return (
        not movie.runtime or
        not movie.genres or
        not movie.cast or
        not movie.certification or
        not movie.backdrop or
        not movie.trailer or
        not has_ott_links
    )


def enrich_existing(limit=500):
    """Fill missing details for existing records"""
    with app.app_context():
        print("\nStarting enrichment of existing movies...")
        print("=" * 70)

        candidates = [m for m in Movie.query.filter_by(is_active=True).all() if needs_enrichment(m)]
        targets = candidates[:limit]

        print(f"Found {len(candidates)} candidates. Processing {len(targets)}...")

        updated = 0
        for idx, movie in enumerate(targets, 1):
            try:
                time.sleep(0.3)

                # Providers with deep links (JustWatch)
                providers = fetch_justwatch_links(movie.title, movie.release_date, country="IN")
                if providers:
                    movie.set_ott_platforms(providers)

                # Details, cast, certification
                details = fetch_movie_details(movie.tmdb_id, language='te')
                if details:
                    movie.runtime = movie.runtime or details.get('runtime', 0)
                    movie.genres = movie.genres or details.get('genres', '')
                    movie.overview = movie.overview or details.get('overview', '')
                    movie.language = movie.language or details.get('original_language', 'te')

                movie.cast = movie.cast or fetch_movie_credits(movie.tmdb_id)
                movie.certification = movie.certification or fetch_movie_certification(movie.tmdb_id)

                # Dubbing detection
                original_language = details.get('original_language') if details else movie.language
                telugu_translation = has_telugu_translation(movie.tmdb_id)
                if original_language and original_language != 'te' and telugu_translation:
                    movie.is_dubbed = True

                movie.last_checked = datetime.now(timezone.utc)
                movie.last_verified = datetime.now(timezone.utc)

                updated += 1

                if updated % 25 == 0:
                    db.session.commit()
                    print(f"Updated {updated}/{len(targets)}")

            except Exception:
                db.session.rollback()
                continue

        db.session.commit()
        print("=" * 70)
        print(f"Enrichment completed. Updated {updated} movies.")


if __name__ == '__main__':
    enrich_existing(limit=500)