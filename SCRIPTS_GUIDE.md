# 📜 OTT Radar Scripts Reference

Complete guide to all automation scripts in the platform.

---

## 🚦 Script Categories

### ✅ Safe for Regular Use
Run these anytime without risk. They're idempotent and won't duplicate data.

### ⚠️ One-Time Only
Run once during setup or migrations. Running again may cause issues.

### 🤖 Admin Portal Ready
Available to trigger directly from `/admin` dashboard.

---

## 📚 Core Scripts

### 1. `enrich_metadata_trailers.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Fetch missing movie metadata from TMDB  
**Rate Limit:** Unlimited (TMDB has no strict API limits)

**Usage:**
```bash
# Enrich 200 movies with missing data
python scripts/enrich_metadata_trailers.py --limit 200

# Enrich all movies (thousands - takes longer)
python scripts/enrich_metadata_trailers.py --all

# Force re-enrich even if data exists
python scripts/enrich_metadata_trailers.py --limit 100 --force

# Skip OTT enrichment (metadata only)
python scripts/enrich_metadata_trailers.py --limit 100 --skip-ott
```

**What it fills:**
- Overview (plot summary)
- Poster & backdrop images
- Runtime, genres, cast
- Rating, popularity, release date
- YouTube trailer ID
- OTT platforms (Netflix, Prime, etc.)
- Certification (PG, R, etc.)

**When to run:** After importing new movies, or monthly for updates

---

### 2. `smart_omdb_enrichment.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Fill gaps that TMDB couldn't provide using OMDb  
**Rate Limit:** 1000 calls/day (strictly enforced)

**Usage:**
```bash
# Check what can be improved (no API calls)
python scripts/smart_omdb_enrichment.py --check-status

# Process 500 movies (safe daily batch)
python scripts/smart_omdb_enrichment.py --limit 500

# Reset tracking (start fresh)
python scripts/smart_omdb_enrichment.py --reset-tracking
```

**Smart Features:**
- Tracks already-checked movies (won't retry)
- Remembers "not found" movies (saves API calls)
- Shows accurate remaining count
- Saves progress every 50 movies
- API call counter

**What it fills:**
- Missing overviews
- Missing posters
- Missing runtimes
- Missing genres
- Missing cast
- Missing ratings
- Missing certifications

**When to run:** After TMDB enrichment, maximum once per day (rate limit)

---

### 3. `complete_enrichment.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Show missing-field summary and recommendations  
**Rate Limit:** None (just reads database)

**Usage:**
```bash
# Show what's missing (dry run)
python scripts/complete_enrichment.py --dry-run

# See field-by-field breakdown
python scripts/complete_enrichment.py --verbose
```

**Output Example:**
```
Missing Fields Report:
  overview: 70
  poster: 235
  runtime: 47
  genres: 380
  cast: 204
  rating: 1054

Recommendation:
  Run Phase 2 (OMDb): python scripts/smart_omdb_enrichment.py --limit 500
```

**When to run:** Before/after enrichment to track progress

---

### 4. `track_missing_movies.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Find popular TMDB movies not yet in your database  
**Rate Limit:** TMDB (unlimited)

**Usage:**
```bash
# Find 100 missing movies
python scripts/track_missing_movies.py --find 100

# Find and save to JSON for import
python scripts/track_missing_movies.py --find 200 --save

# Specific year range
python scripts/track_missing_movies.py --find 50 --year 2024
```

**Output:**
- Saves to `missing_movies.json`
- Shows popularity distribution
- Shows year breakdown
- Filters out existing DB movies

**When to run:** Weekly or monthly to discover new content

---

### 5. `discover_new_movies.py`
**Category:** ✅ Regular  
**Purpose:** Import movies from `missing_movies.json` to database  
**Rate Limit:** TMDB (unlimited)

**Usage:**
```bash
# Import from JSON (created by track_missing_movies.py)
python scripts/discover_new_movies.py --import-from-json

# Search and add single movie by TMDB ID
python scripts/discover_new_movies.py --tmdb-id 12345
```

**Workflow:**
1. Run `track_missing_movies.py --find 100 --save`
2. Review `missing_movies.json`
3. Run `discover_new_movies.py --import-from-json`
4. Movies are added to DB (basic info only)
5. Run `enrich_metadata_trailers.py` to fill details

**When to run:** After finding missing movies

---

### 6. `export_db.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Create JSON backup of entire database  
**Rate Limit:** None

**Usage:**
```bash
# Full export (all movies)
python scripts/export_db.py

# Export only active movies
python scripts/export_db.py --active-only
```

**Output:**
- Creates timestamped backup in `exports/`
- Format: `movies_backup_YYYYMMDD_HHMMSS.json`
- Includes all movie fields, OTT platforms, metadata

**When to run:** Daily or before major operations

---

### 7. `import_db.py`
**Category:** ⚠️ One-Time (Dangerous)  
**Purpose:** Restore database from JSON backup  
**Rate Limit:** None

**Usage:**
```bash
# Import from specific backup
python scripts/import_db.py exports/movies_backup_20260209_120000.json

# Clear DB first then import (DESTRUCTIVE)
python scripts/import_db.py --clear-first backup.json
```

**⚠️ WARNING:**
- Can overwrite existing data
- Use `--clear-first` carefully
- Always backup before importing
- Meant for disaster recovery

**When to run:** Only when restoring from backup

---

### 8. `daily_ott_checker.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Refresh OTT availability for all movies  
**Rate Limit:** TMDB (unlimited)

**Usage:**
```bash
# Check all movies
python scripts/daily_ott_checker.py

# Check specific limit
python scripts/daily_ott_checker.py --limit 500

# Check and log changes
python scripts/daily_ott_checker.py --track-changes
```

**What it does:**
- Updates `ott_platforms` field
- Tracks new additions/removals
- Updates `last_checked` timestamp
- Logs changes to file

**When to run:** Daily (via scheduler or cron)

---

### 9. `manage_ott_links.py`
**Category:** ✅ Regular | 🤖 Portal Available  
**Purpose:** Generate OTT coverage reports and stats  
**Rate Limit:** None

**Usage:**
```bash
# Full coverage report
python scripts/manage_ott_links.py --report

# Show movies without OTT
python scripts/manage_ott_links.py --dead-links

# Platform-specific stats
python scripts/manage_ott_links.py --platform-stats
```

**Output Example:**
```
OTT Platform Coverage Report:
  Total Movies: 2,647
  With OTT Links: 1,344 (50.8%)
  No OTT: 1,303 (49.2%)

Platform Distribution:
  Netflix: 456
  Prime Video: 389
  Hotstar: 312
  ...
```

**When to run:** Weekly for monitoring

---

### 10. `scheduler_background.py`
**Category:** ✅ Regular (Background Service)  
**Purpose:** Run automated tasks on schedule  
**Rate Limit:** Depends on tasks

**Usage:**
```bash
# Start scheduler service
python scripts/scheduler_background.py
```

**Scheduled Tasks:**
- Daily OTT refresh (3 AM)
- Weekly metadata update (Sunday)
- Database backup (daily)
- Missing movie discovery (weekly)

**When to run:** Once as a background service (Linux/tmux)

---

### 11. `migrate_add_ott_release_date.py`
**Category:** ⚠️ One-Time (Migration)  
**Purpose:** Add `ott_release_date` column to existing database  
**Rate Limit:** None

**Usage:**
```bash
# Add column (safe - checks if exists)
python scripts/migrate_add_ott_release_date.py
```

**What it does:**
- Adds `ott_release_date` VARCHAR(10) column
- Safe to run multiple times (checks existence)
- Required for countdown features

**When to run:** Once (already done if column exists)

---

### 12. `ott_release_features.py`
**Category:** ✅ Regular (Library - not standalone)  
**Purpose:** Helper functions for OTT release date features  
**Rate Limit:** None

**Functions:**
```python
from scripts.ott_release_features import *

# Get upcoming releases
upcoming = get_upcoming_ott_releases(days_ahead=30)

# Calculate countdown
countdown = calculate_countdown('2026-03-15')  # {days, hours, formatted}

# Get today's releases
today = get_movies_releasing_today()

# Get reminder candidates
reminders = get_reminder_candidates(days_before=3)
```

**When to use:** Import in your Flask routes for UI features

---

## 🤖 Admin Portal Integration

Available in `/admin` → Automation tab:

| Script Name | Button Label | Limit | Purpose |
|------------|--------------|-------|---------|
| `enrich_metadata_trailers` | Enrich Metadata (TMDB) | 200 | Fill missing movie details |
| `smart_omdb_enrichment` | Fill Gaps (OMDb) | 200 | Fill remaining gaps carefully |
| `track_missing_movies` | Find Missing Movies | 100 | Discover new content |
| `discover_new_movies` | Import New Movies | - | Add from JSON |
| `daily_ott_checker` | Refresh OTT Links | All | Update platform availability |
| `export_db` | Export Database | - | Create backup |
| `manage_ott_links_report` | OTT Coverage Report | - | View statistics |
| `complete_enrichment` | Missing Fields Report | - | Check completeness |

---

## 📊 Recommended Workflow

### Initial Setup (First Time)
```bash
# 1. Initialize database
python db_init.py

# 2. Find and import movies
python scripts/track_missing_movies.py --find 500 --save
python scripts/discover_new_movies.py --import-from-json

# 3. Enrich with TMDB (Phase 1)
python scripts/enrich_metadata_trailers.py --all

# 4. Fill gaps with OMDb (Phase 2)
python scripts/smart_omdb_enrichment.py --check-status
python scripts/smart_omdb_enrichment.py --limit 500

# 5. Check results
python scripts/complete_enrichment.py --dry-run
python scripts/manage_ott_links.py --report
```

### Regular Maintenance (Weekly)
```bash
# Monday: Find new movies
python scripts/track_missing_movies.py --find 100 --save
python scripts/discover_new_movies.py --import-from-json

# Tuesday: Enrich new additions
python scripts/enrich_metadata_trailers.py --limit 200

# Daily: OTT refresh
python scripts/daily_ott_checker.py

# Sunday: Backup
python scripts/export_db.py
```

---

## ⚡ Quick Reference

**Fill missing metadata:**
```bash
python scripts/enrich_metadata_trailers.py --limit 200
```

**Fill remaining gaps (rate-limited):**
```bash
python scripts/smart_omdb_enrichment.py --limit 500
```

**Check what's missing:**
```bash
python scripts/complete_enrichment.py --dry-run
```

**Find new movies:**
```bash
python scripts/track_missing_movies.py --find 100 --save
python scripts/discover_new_movies.py --import-from-json
```

**Backup database:**
```bash
python scripts/export_db.py
```

**OTT coverage report:**
```bash
python scripts/manage_ott_links.py --report
```

---

## 🚨 Safety Notes

**Safe to run multiple times:**
- `enrich_metadata_trailers.py` (idempotent - won't duplicate)
- `smart_omdb_enrichment.py` (tracks already-checked)
- `complete_enrichment.py` (read-only)
- `track_missing_movies.py` (filters existing)
- `export_db.py` (creates new file)
- `daily_ott_checker.py` (updates timestamps)
- `manage_ott_links.py` (read-only)

**Use carefully (can modify data):**
- `discover_new_movies.py` (adds movies)
- `import_db.py` (overwrites data)
- `migrate_add_ott_release_date.py` (schema change - run once)

**Rate limits:**
- TMDB API: Unlimited (generous soft limit)
- OMDb API: **1000 calls/day** (strict - use `smart_omdb_enrichment.py` to track)

---

**Last Updated:** February 9, 2026
