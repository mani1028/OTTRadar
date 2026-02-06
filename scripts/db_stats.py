"""
Database stats summary for movies.
Usage: python -m scripts.db_stats
"""

from collections import Counter

from app import app
from models import Movie


def has_ott_links(movie):
    ott_data = movie.get_ott_platforms()
    return any((v or {}).get("link") or (v or {}).get("url") for v in ott_data.values())


def needs_enrichment(movie):
    return (
        not movie.runtime or
        not movie.genres or
        not movie.cast or
        not movie.certification or
        not movie.backdrop or
        not movie.trailer or
        not has_ott_links(movie)
    )


def main():
    with app.app_context():
        movies = Movie.query.filter_by(is_active=True).all()
        total = len(movies)

        lang_counts = Counter((m.language or "").upper() for m in movies)
        dubbed_count = sum(1 for m in movies if m.is_dubbed)
        with_ott_count = sum(1 for m in movies if has_ott_links(m))
        full_details_count = sum(1 for m in movies if not needs_enrichment(m))
        missing_details_count = total - full_details_count
        trailer_count = sum(1 for m in movies if m.trailer)
        no_trailer_count = total - trailer_count
        free_content_count = sum(1 for m in movies if any((v or {}).get('is_free') for v in (m.get_ott_platforms() or {}).values()))

        print("\nDatabase Breakdown:")
        print(f"   Total: {total} movies")
        for key in ["TE", "TA", "HI", "ML", "KN"]:
            print(f"   {key}: {lang_counts.get(key, 0)} movies")
        print(f"   Dubbed: {dubbed_count} movies")
        print(f"   With OTT: {with_ott_count} movies")
        print(f"   Full details: {full_details_count} movies")
        print(f"   Missing details: {missing_details_count} movies")
        print(f"   Trailer: {trailer_count} movies")
        print(f"   No trailer: {no_trailer_count} movies")
        print(f"   Free content: {free_content_count} movies")


if __name__ == "__main__":
    main()
