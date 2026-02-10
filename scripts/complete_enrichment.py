#!/usr/bin/env python3
"""
Complete Database Enrichment - Fill ALL Missing Fields

This script runs a comprehensive two-phase enrichment:
Phase 1: TMDB fills everything possible (unlimited API calls)
Phase 2: OMDb fills remaining gaps (rate-limited 1000/day)

Goal: Reduce ALL missing fields to 0 (or as close as possible)
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Movie
from sqlalchemy import or_


def count_missing_fields():
    """Count movies with missing fields"""
    with app.app_context():
        total = Movie.query.count()
        
        missing = {
            'total_movies': total,
            'overview': Movie.query.filter(or_(Movie.overview == None, Movie.overview == '')).count(),
            'poster': Movie.query.filter(or_(Movie.poster == None, Movie.poster == '')).count(),
            'backdrop': Movie.query.filter(or_(Movie.backdrop == None, Movie.backdrop == '')).count(),
            'runtime': Movie.query.filter(or_(Movie.runtime == None, Movie.runtime == 0)).count(),
            'genres': Movie.query.filter(or_(Movie.genres == None, Movie.genres == '')).count(),
            'cast': Movie.query.filter(or_(Movie.cast == None, Movie.cast == '')).count(),
            'certification': Movie.query.filter(or_(Movie.certification == None, Movie.certification == '')).count(),
            'youtube_trailer_id': Movie.query.filter(or_(Movie.youtube_trailer_id == None, Movie.youtube_trailer_id == '')).count(),
            'release_date': Movie.query.filter(or_(Movie.release_date == None, Movie.release_date == '')).count(),
            'rating': Movie.query.filter(or_(Movie.rating == None, Movie.rating == 0)).count(),
            'popularity': Movie.query.filter(or_(Movie.popularity == None, Movie.popularity == 0)).count(),
            'ott_platforms': Movie.query.filter(or_(Movie.ott_platforms == None, Movie.ott_platforms == '', Movie.ott_platforms == '{}')).count(),
        }
        
        return missing


def print_missing_summary(missing, title="Missing Data Summary"):
    """Print missing field counts"""
    print("\n" + "=" * 70)
    print(f"📊 {title.upper()}")
    print("=" * 70)
    print(f"Total Movies: {missing['total_movies']}")
    print()
    
    # Calculate total missing across all fields
    total_missing = sum(v for k, v in missing.items() if k != 'total_movies')
    
    # Group fields by category
    critical_fields = ['overview', 'poster', 'runtime', 'genres', 'cast', 'rating']
    tmdb_only_fields = ['backdrop', 'youtube_trailer_id', 'popularity']
    other_fields = ['certification', 'release_date', 'ott_platforms']
    
    print("🔴 CRITICAL FIELDS (OMDb can fill):")
    for field in critical_fields:
        count = missing[field]
        pct = (count / missing['total_movies'] * 100) if missing['total_movies'] > 0 else 0
        status = "✅" if count == 0 else "⚠️" if count < 100 else "❌"
        print(f"  {status} {field:20s}: {count:4d} missing ({pct:5.1f}%)")
    
    print("\n🟡 TMDB-ONLY FIELDS (OMDb cannot fill):")
    for field in tmdb_only_fields:
        count = missing[field]
        pct = (count / missing['total_movies'] * 100) if missing['total_movies'] > 0 else 0
        status = "✅" if count == 0 else "⚠️" if count < 100 else "❌"
        print(f"  {status} {field:20s}: {count:4d} missing ({pct:5.1f}%)")
    
    print("\n🟢 OTHER FIELDS:")
    for field in other_fields:
        count = missing[field]
        pct = (count / missing['total_movies'] * 100) if missing['total_movies'] > 0 else 0
        status = "✅" if count == 0 else "⚠️" if count < 100 else "❌"
        print(f"  {status} {field:20s}: {count:4d} missing ({pct:5.1f}%)")
    
    print("\n" + "=" * 70)
    print(f"Total Missing Fields: {total_missing}")
    
    # Calculate completion percentage
    max_possible = missing['total_movies'] * 12  # 12 fields tracked
    filled = max_possible - total_missing
    completion = (filled / max_possible * 100) if max_possible > 0 else 0
    
    print(f"Database Completion: {completion:.1f}%")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Complete database enrichment workflow')
    parser.add_argument('--phase', choices=['1', '2', 'both'], default='both',
                        help='Which phase to run (1=TMDB, 2=OMDb, both=auto)')
    parser.add_argument('--limit', type=int, help='Limit movies per phase')
    parser.add_argument('--start-id', type=int, help='Start from movie ID')
    parser.add_argument('--reverse', action='store_true', help='Process in reverse order')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎬 COMPLETE DATABASE ENRICHMENT")
    print("=" * 70)
    print("Goal: Fill ALL missing fields from TMDB and OMDb")
    print()
    
    # Show initial state
    print("📋 INITIAL STATE:")
    missing_before = count_missing_fields()
    print_missing_summary(missing_before, "Before Enrichment")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made")
        print("\nRecommended commands:")
        print("\n# Phase 1: Fill from TMDB (unlimited)")
        if args.start_id:
            cmd1 = f"python scripts/enrich_metadata_trailers.py --all --start-id {args.start_id}"
            if args.reverse:
                cmd1 += " --reverse"
            print(f"  {cmd1}")
        else:
            print("  python scripts/enrich_metadata_trailers.py --all")
        
        print("\n# Phase 2: Fill gaps from OMDb (rate-limited 1000/day)")
        if args.limit:
            cmd2 = f"python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit {args.limit}"
        else:
            cmd2 = "python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit 500"
        
        if args.start_id:
            cmd2 += f" --start-id {args.start_id}"
            if args.reverse:
                cmd2 += " --reverse"
        
        print(f"  {cmd2}")
        
        # Show potential improvement
        print("\n📊 EXPECTED IMPROVEMENTS:")
        print("\n🔴 CRITICAL FIELDS (will be filled by TMDB + OMDb):")
        for field in ['overview', 'poster', 'runtime', 'genres', 'cast', 'rating']:
            count = missing_before[field]
            # Estimate: TMDB fills ~80%, OMDb fills ~70% of remaining
            after_tmdb = int(count * 0.2)
            after_omdb = int(after_tmdb * 0.3)
            print(f"  {field:20s}: {count:4d} → ~{after_tmdb:3d} (TMDB) → ~{after_omdb:3d} (OMDb)")
        
        print("\n🟡 TMDB-ONLY FIELDS (only TMDB can fill):")
        for field in ['backdrop', 'youtube_trailer_id', 'popularity']:
            count = missing_before[field]
            after_tmdb = int(count * 0.1)  # TMDB fills ~90%
            print(f"  {field:20s}: {count:4d} → ~{after_tmdb:3d} (TMDB)")
        
        return
    
    # Phase 1: TMDB enrichment
    if args.phase == '1' or args.phase == 'both':
        print("\n" + "=" * 70)
        print("🚀 PHASE 1: TMDB ENRICHMENT")
        print("=" * 70)
        print("Running: python scripts/enrich_metadata_trailers.py --all")
        print("(This may take 30-60 minutes for 2647 movies)")
        print()
        
        cmd = "python scripts/enrich_metadata_trailers.py --all"
        if args.start_id:
            cmd += f" --start-id {args.start_id}"
            if args.reverse:
                cmd += " --reverse"
        if args.limit:
            cmd = cmd.replace("--all", f"--limit {args.limit}")
        
        print(f"Command: {cmd}")
        print("\nPress Ctrl+C to cancel, or wait for completion...")
        
        import subprocess
        result = subprocess.run(cmd, shell=True)
        
        if result.returncode != 0:
            print("\n❌ Phase 1 failed. Check errors above.")
            return
        
        # Show progress after Phase 1
        print("\n📊 PROGRESS AFTER PHASE 1:")
        missing_after_tmdb = count_missing_fields()
        print_missing_summary(missing_after_tmdb, "After TMDB (Phase 1)")
    
    # Phase 2: OMDb gap filling
    if args.phase == '2' or args.phase == 'both':
        print("\n" + "=" * 70)
        print("🚀 PHASE 2: OMDb GAP FILLING")
        print("=" * 70)
        
        # Check how many movies still need OMDb
        with app.app_context():
            movies_needing_omdb = Movie.query.filter(
                or_(
                    or_(Movie.overview == None, Movie.overview == ''),
                    or_(Movie.poster == None, Movie.poster == ''),
                    or_(Movie.runtime == None, Movie.runtime == 0),
                    or_(Movie.genres == None, Movie.genres == ''),
                    or_(Movie.cast == None, Movie.cast == ''),
                    or_(Movie.rating == None, Movie.rating == 0),
                )
            ).count()
        
        print(f"Movies still missing critical fields: {movies_needing_omdb}")
        print()
        
        limit = args.limit or 500  # Default to 500 for rate limit safety
        print(f"Running: python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit {limit}")
        print(f"(Processing {limit} movies to stay within OMDb rate limit)")
        print()
        
        cmd = f"python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit {limit}"
        if args.start_id:
            cmd += f" --start-id {args.start_id}"
            if args.reverse:
                cmd += " --reverse"
        
        print(f"Command: {cmd}")
        print("\nPress Ctrl+C to cancel, or wait for completion...")
        
        import subprocess
        result = subprocess.run(cmd, shell=True)
        
        if result.returncode != 0:
            print("\n❌ Phase 2 failed. Check errors above.")
            return
    
    # Show final state
    print("\n" + "=" * 70)
    print("🎉 ENRICHMENT COMPLETE!")
    print("=" * 70)
    
    missing_after = count_missing_fields()
    print_missing_summary(missing_after, "Final State")
    
    # Show improvement
    print("\n📈 IMPROVEMENT:")
    print("=" * 70)
    critical_fields = ['overview', 'poster', 'runtime', 'genres', 'cast', 'rating']
    
    for field in critical_fields:
        before = missing_before[field]
        after = missing_after[field]
        filled = before - after
        pct_filled = (filled / before * 100) if before > 0 else 0
        print(f"  {field:20s}: {before:4d} → {after:4d} (filled {filled:4d}, {pct_filled:5.1f}%)")
    
    print("=" * 70)
    
    # Show any remaining gaps
    remaining_critical = sum(missing_after[f] for f in critical_fields)
    
    if remaining_critical > 0:
        print(f"\n⚠️  {remaining_critical} critical fields still missing")
        print("\nTo continue filling:")
        print(f"  python scripts/enrich_metadata_trailers.py --use-omdb --skip-ott --limit 500")
        print("\nNote: Some fields may not be available in any database.")
        print("      You can add them manually via admin portal.")
    else:
        print("\n✅ All critical fields filled!")
        print("   (Except backdrop, trailers, popularity which are TMDB-only)")


if __name__ == '__main__':
    main()
