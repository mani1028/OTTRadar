# 🐍 Python Files Documentation

Complete guide to all Python files in the OTT RADAR project.

---

## 🎯 Core Application Files (Root Directory)

### **app.py** ⭐ MAIN APPLICATION
**Purpose**: Flask web server - all routes, API endpoints, and web interface  
**Location**: `/app.py`  
**Usage**: `python app.py` (starts web server on port 5000)  
**Key Features**:
- 30+ routes (homepage, movie detail, admin panel, search, filters)
- TMDB API integration for movie metadata
- SEO-friendly URLs with slug generation
- User submission system
- Admin authentication
- Database auto-creation on first run

**When to Edit**: Adding new pages, API endpoints, or features

---

### **models.py** ⭐ DATABASE SCHEMA
**Purpose**: SQLAlchemy database models (tables and relationships)  
**Location**: `/models.py`  
**Tables Defined**:
- `Movie` - Main movie data (5,000+ records)
- `UserSubmission` - User-requested movies
- `Watchlist` - User watchlists with email tracking
- `OTTSnapshot` - Historical OTT availability data

**Key Methods**:
- `to_dict()` - Convert movie to JSON
- `get_ott_platforms()` - Parse OTT data
- `is_available_on()` - Check platform availability

**When to Edit**: Adding new database fields or tables

---

### **config.py** ⚙️ CONFIGURATION
**Purpose**: Environment variables and app settings  
**Location**: `/config.py`  
**Contains**:
- Database connection settings
- TMDB API configuration
- Admin credentials
- Pagination limits
- Security settings

**When to Edit**: Changing environment variables or deployment settings

---

### **logger.py** 📝 LOGGING SYSTEM
**Purpose**: Centralized logging to files and console  
**Location**: `/logger.py`  
**Features**:
- Rotating file handler (10MB max, 5 backups)
- Console and file logging
- Automatic log directory creation
- Structured log format with timestamps

**When to Edit**: Rarely (works out of the box)

---

### **discovery.py** 🔍 SEARCH & FILTERING
**Purpose**: Smart search and movie discovery logic  
**Location**: `/discovery.py`  
**Key Classes**:
- `UnifiedSearch` - Centralized search with word splitting
- `MovieFilters` - Platform/language/genre filtering
- `TrendingDetector` - Identifies trending movies
- `CategoryManager` - Organizes movies into sections

**When to Edit**: Adding new filter types or search algorithms

---

### **ott_links.py** 🔗 OTT PLATFORM INTEGRATION
**Purpose**: Fetch streaming links from JustWatch API  
**Location**: `/ott_links.py`  
**Features**:
- JustWatch API integration (real deep links)
- Platform-specific URL generation
- India region support
- Fallback to generic platform URLs

**When to Edit**: Adding new OTT platforms or changing region

---

### **scheduler.py** ⏰ AUTOMATION (OPTIONAL)
**Purpose**: Background tasks for daily movie updates  
**Location**: `/scheduler.py`  
**Tasks**:
- Daily new movie fetch (3 AM)
- Weekly OTT link refresh (Sunday 2 AM)
- Automatic database backups

**Usage**: `python scheduler.py` (runs as daemon)  
**Note**: NOT required for basic operation - only for automated updates

**When to Edit**: Changing schedule times or tasks

---

### **test_app_start.py** ❌ DELETE
**Purpose**: Simple test script  
**Status**: ⚠️ NOT NEEDED - Can be deleted  
**Reason**: Basic functionality test, not used in production

---

## 📦 Scripts Directory (`/scripts`)

### **production_bulk_import.py** ⭐ INITIAL DATA LOAD
**Purpose**: Import movies from TMDB (Telugu/Tamil/Hindi/etc.)  
**Usage**: `python -m scripts.production_bulk_import --language te`  
**What It Does**:
- Fetches 3,000-5,000 movies per language
- Filters by popularity and rating
- Saves to database automatically
- Shows progress bar

**Run Once**: During initial setup to populate database

---

### **enrich_existing.py** ⭐ FILL MISSING DATA
**Purpose**: Enrich existing movies with cast, OTT links, metadata  
**Usage**: `python -m scripts.enrich_existing`  
**What It Does**:
- Finds movies missing runtime/cast/OTT links
- Fetches data from TMDB and JustWatch
- Updates up to 500 movies per run
- Shows progress

**Run Periodically**: Weekly or after bulk import

---

### **scraper_service.py** ⭐ TMDB DATA FETCHER
**Purpose**: Core TMDB API functions (used by other scripts)  
**Location**: `/scripts/scraper_service.py`  
**Functions**:
- `fetch_movie_details()` - Get runtime, genres, overview
- `fetch_movie_credits()` - Get cast with profile images (JSON format)
- `fetch_movie_certification()` - Get age rating
- `search_tmdb()` - Search for movies

**When to Edit**: Rarely (stable utility functions)

---

### **daily_fetch.py** 🔄 DAILY UPDATES
**Purpose**: Fetch new Telugu movies added to TMDB  
**Usage**: `python -m scripts.daily_fetch`  
**What It Does**:
- Checks TMDB for movies released in last 30 days
- Adds new movies to database
- Fetches full metadata

**Run**: Daily via scheduler or manually

---

### **refresh_ott_links.py** 🔄 UPDATE OTT DATA
**Purpose**: Refresh JustWatch links for existing movies  
**Usage**: `python -m scripts.refresh_ott_links`  
**What It Does**:
- Updates OTT availability for all movies
- Gets latest streaming links
- Marks outdated links

**Run**: Weekly (OTT platforms change frequently)

---

### **auto_backup.py** 💾 DATABASE BACKUP
**Purpose**: Create JSON backup of entire database  
**Usage**: `python -m scripts.auto_backup`  
**What It Does**:
- Exports all movies to JSON (saved in `/exports/`)
- Timestamped filename
- Can be restored later

**Run**: Before major changes or weekly

---

### **export_db.py** 📤 EXPORT DATA
**Purpose**: Export movies to JSON file  
**Usage**: `python -m scripts.export_db --output movies.json`  
**Similar to**: auto_backup.py (can merge or delete one)

---

### **import_db.py** 📥 IMPORT DATA
**Purpose**: Import movies from JSON backup  
**Usage**: `python -m scripts.import_db --input movies.json`  
**Use Case**: Restore from backup or migrate database

---

### **db_stats.py** 📊 STATISTICS
**Purpose**: Show database statistics  
**Usage**: `python -m scripts.db_stats`  
**Output**:
- Total movies count
- Movies by platform
- Movies by language
- Missing data statistics

**Run**: Anytime to check database health

---

### **record_snapshot.py** 📸 OTT HISTORY
**Purpose**: Record OTT availability snapshots  
**Usage**: `python -m scripts.record_snapshot`  
**What It Does**:
- Saves current OTT availability to OTTSnapshot table
- Useful for tracking "New on Netflix" etc.

**Run**: Daily (via scheduler)

---

### **migrate_watchlist_email.py** ❌ MIGRATION SCRIPT
**Purpose**: One-time database migration (adds email field)  
**Status**: ⚠️ NOT NEEDED - Can be deleted  
**Reason**: Migration already done, not needed for new setups

---

### **run_full_pipeline.py** 🔄 FULL WORKFLOW
**Purpose**: Run import → enrich → export workflow  
**Usage**: `python -m scripts.run_full_pipeline`  
**What It Does**:
- Runs production_bulk_import
- Runs enrich_existing (multiple passes until complete)
- Creates backup

**Run**: Initial setup or major refresh

---

### **__init__.py** ⚙️ PACKAGE MARKER
**Purpose**: Makes `/scripts` a Python package  
**Status**: ✅ REQUIRED - Keep this file

---

## 🔧 Maintenance Directory (`/maintenance`)

⚠️ **All files in this folder can be DELETED**  
These were one-time migration/cleanup scripts already executed:

- `migrate_db.py` - Old database migration (done)
- `migrate_add_youtube_trailer_id.py` - Added trailer field (done)
- `migrate_add_user_submission_category.py` - Added category field (done)
- `cleanup_css.py` - CSS cleanup (done)
- `separate_css.py` - CSS separation (done)
- `find_movies.py` - Utility script (not needed)
- `check_checkpoint.py` - Check refresh status (not needed)
- `set_checkpoint.py` - Set refresh checkpoint (not needed)
- `README.md` - Maintenance docs (redundant)

**Action**: Delete entire `/maintenance` directory ✂️

---

## 🗑️ Files to DELETE

**Markdown Files** (keeping only main README.md):
```
❌ CAST_*.md (9 files - old documentation)
❌ DELIVERY_*.md (2 files - old reports)
❌ EXECUTIVE_SUMMARY_FINAL.md
❌ FINAL_*.md (4 files - old audit reports)
❌ PRODUCTION_READY_APPROVAL.md
❌ SECOND_AUDIT_RESULTS.md
❌ WATCHLIST_*.md (2 files - old plans)
❌ CO_FOUNDER_AUDIT_RESPONSE.md
❌ DOCUMENTATION_GUIDE.md
❌ REFRESH_GUIDE.md
```

**Python Files**:
```
❌ test_app_start.py (test file, not needed)
❌ scripts/migrate_watchlist_email.py (one-time migration, done)
❌ /maintenance/ (entire directory)
```

---

## ✅ Essential Files Summary

**FOR RUNNING THE APP:**
1. `app.py` - Main application
2. `models.py` - Database schema
3. `config.py` - Configuration
4. `logger.py` - Logging
5. `discovery.py` - Search logic
6. `ott_links.py` - OTT integration

**FOR SETUP & DATA:**
7. `scripts/production_bulk_import.py` - Import movies
8. `scripts/enrich_existing.py` - Fill missing data
9. `scripts/scraper_service.py` - TMDB functions

**FOR MAINTENANCE (OPTIONAL):**
10. `scripts/daily_fetch.py` - Daily updates
11. `scripts/auto_backup.py` - Backups
12. `scripts/db_stats.py` - Statistics
13. `scheduler.py` - Automation

**TOTAL: 13 essential Python files** (down from 30+)

---

## 🚀 Quick Setup Workflow

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up environment
echo SECRET_KEY=your-secret-key-here > .env
echo TMDB_API_KEY=your-tmdb-api-key >> .env

# 3. Create database and import movies
python init_db.py

# 4. Run enrichment to fill missing data
python -m scripts.enrich_existing

# 5. Start the app
python app.py
```

Visit: http://127.0.0.1:5000

---

**Last Updated**: February 6, 2026  
**Project**: OTT RADAR - Indian Regional Cinema Tracker
