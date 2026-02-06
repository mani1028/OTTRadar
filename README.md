# 🎬 OTT RADAR - Indian Cinema Streaming Tracker

> **Complete OTT aggregator for Indian regional cinema**  
> Track 5,000+ movies across Netflix, Prime Video, Hotstar, Aha, Zee5, SonyLIV and more!

---

## 📖 Table of Contents

1. [Quick Start](#-one-command-setup)
2. [What This Does](#-features)
3. [Project Structure](#-project-structure)
4. [Python Files Guide](#-python-files-explained)
5. [Database](#-database)
6. [Workflows](#-common-workflows)
7. [Troubleshooting](#-troubleshooting)

---

## ⚡ One-Command Setup

### **New Project Setup (Simplest Way)**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create environment file
python -c "import secrets; print(f'SECRET_KEY={secrets.token_hex(32)}')" > .env
echo TMDB_API_KEY=your-api-key-here >> .env
echo ADMIN_USERNAME=admin >> .env
echo ADMIN_PASSWORD=your-password >> .env

# 3. Initialize database + import Telugu movies (one command!)
python init_db.py --import

# 4. Start the app
python app.py
```

**🎉 Done!** Visit [http://127.0.0.1:5000](http://127.0.0.1:5000)

### **Manual Setup (Step by Step)**

```bash
# Create database only
python init_db.py

# Import movies separately
python -m scripts.production_bulk_import --language te

# Enrich with cast/OTT data
python -m scripts.enrich_existing

# Start app
python app.py
```

---

## 🎯 Features

### **User Features**
- 🎥 Cinematic hero banner with trending movie
- 📱 6 curated sections (New on OTT, Trending, Top Rated, etc.)
- 🔍 Smart search with instant TMDB scraping
- 🎞️ Filter by platform (Netflix, Prime, Hotstar, Aha, Zee5, etc.)
- 🌐 Original vs Dubbed content toggle
- 👥 Cast profiles with TMDB images and biographies
- 📺 Direct OTT deep links (JustWatch integration)
- 🎬 YouTube trailer embeds
- 📤 Share to social media (WhatsApp, Telegram, clipboard)
- 💾 Watchlist with localStorage persistence
- 📳 Haptic feedback on mobile devices

### **Technical Features**
- ✅ Zero-download architecture (TMDB CDN for images)
- ✅ SEO-friendly URLs (`/movie/the-dark-knight`)
- ✅ Mobile-first responsive design
- ✅ SQL injection protection
- ✅ Automatic database creation
- ✅ Background scheduler for daily updates
- ✅ JSON backup/restore system
- ✅ Admin panel for manual curation

---

## 📁 Project Structure

```
ott/
├── app.py                    # ⭐ Main Flask application
├── models.py                 # ⭐ Database schema (Movie, Watchlist, etc.)
├── config.py                 # ⚙️ Configuration & environment variables
├── init_db.py                # 🚀 One-command database setup
├── logger.py                 # 📝 Centralized logging
├── discovery.py              # 🔍 Search & filtering logic
├── ott_links.py              # 🔗 JustWatch OTT integration
├── scheduler.py              # ⏰ Background automation (optional)
├── requirements.txt          # 📦 Python dependencies
├── .env                      # 🔐 Secret keys (create this!)
│
├── templates/                # 🎨 HTML pages
│   ├── base.html             # Layout with navbar/footer
│   ├── index.html            # Homepage (6 sections)
│   ├── movie.html            # Movie detail page
│   ├── person.html           # Actor profile page
│   ├── admin.html            # Admin dashboard
│   └── ...
│
├── static/                   # 🎨 CSS/JS assets
│   ├── css/
│   │   ├── style.css         # Desktop styles
│   │   └── mobile.css        # Mobile-first responsive
│   └── js/
│       ├── optimizations.js  # Lazy loading, infinite scroll
│       ├── mobile.js         # Haptic feedback, touch events
│       └── features.js       # Wishlist, share, filters
│
├── scripts/                  # 🔧 Data import & maintenance
│   ├── production_bulk_import.py  # ⭐ Import movies from TMDB
│   ├── enrich_existing.py         # ⭐ Fill missing cast/OTT data
│   ├── scraper_service.py         # ⭐ TMDB API utilities
│   ├── daily_fetch.py             # 🔄 Daily new releases
│   ├── auto_backup.py             # 💾 Automated backups
│   └── db_stats.py                # 📊 Database statistics
│
├── instance/                 # 💾 SQLite database
│   └── ott_tracker.db        # ⚠️ NEVER delete without backup!
│
└── exports/                  # 💾 JSON backups
    └── movies_backup_*.json  # Timestamped database exports
```

**📄 Documentation Files:**
- `README.md` - This file (main documentation)
- `PYTHON_FILES.md` - Detailed Python file guide with usage
- `requirements.txt` - Python package dependencies

---

## 🐍 Python Files Explained

### **Core Application (Required)**

| File | Purpose | Run When |
|------|---------|----------|
| **app.py** | Flask web server with all routes | `python app.py` to start server |
| **models.py** | Database tables (Movie, Watchlist, etc.) | Never run directly - imported by app.py |
| **config.py** | Settings from .env file | Never run directly - imported by app.py |
| **logger.py** | Structured logging to files/console | Never run directly - imported by app.py |
| **discovery.py** | Search and filter logic | Never run directly - imported by app.py |
| **ott_links.py** | JustWatch API for OTT deep links | Never run directly - imported by app.py |

### **Setup & Data Import**

| File | Purpose | Run When |
|------|---------|----------|
| **init_db.py** | Create database + import movies | `python init_db.py --import` (first setup) |
| **production_bulk_import.py** | Import movies from TMDB by language | `python -m scripts.production_bulk_import --language te` |
| **enrich_existing.py** | Fill missing cast/OTT/metadata | `python -m scripts.enrich_existing` (after import) |
| **scraper_service.py** | TMDB API utility functions | Never run directly - used by other scripts |

### **Maintenance (Optional)**

| File | Purpose | Run When |
|------|---------|----------|
| **daily_fetch.py** | Get new releases from last 30 days | `python -m scripts.daily_fetch` (daily) |
| **auto_backup.py** | Export database to JSON | `python -m scripts.auto_backup` (before changes) |
| **db_stats.py** | Show database statistics | `python -m scripts.db_stats` (anytime) |
| **scheduler.py** | Run background tasks automatically | `python scheduler.py` (optional daemon) |

### **Files You Can DELETE**

**Unnecessary Markdown Files** (consolidated into README.md):
```
✂️ CAST_*.md (9 files)
✂️ DELIVERY_*.md (2 files)
✂️ FINAL_*.md (4 files)
✂️ WATCHLIST_*.md (2 files)
✂️ All other .md files except README.md and PYTHON_FILES.md
```

**Unnecessary Python Files** (migrations already done):
```
✂️ test_app_start.py
✂️ maintenance/ (entire directory)
   - migrate_*.py files
   - cleanup_css.py
   - separate_css.py
   - find_movies.py
```

📖 **See [PYTHON_FILES.md](PYTHON_FILES.md) for detailed documentation**

---

## 💾 Database

### **Schema Overview**

```python
Movie:
  - tmdb_id (UNIQUE) - Prevents duplicates
  - title, poster, backdrop
  - release_date, rating, runtime
  - language (te/ta/hi/ml/kn)
  - genres, cast (JSON with TMDB images)
  - certification (U/U/A/A)
  - ott_platforms (JSON with deep links)
  - is_dubbed, is_active
  - popularity, status

Watchlist:
  - email, movie_id, status
  - notify_on_ott

UserSubmission:
  - movie_title, user_email
  - status (pending/approved/rejected)

OTTSnapshot:
  - Historical OTT availability tracking
```

### **Database Creation**

Database is created automatically on first run, but you can use `init_db.py` for better control:

```bash
# Create empty database
python init_db.py

# Create + import Telugu movies
python init_db.py --import

# Create + import all languages
python init_db.py --import --all
```

### **Backup & Restore**

```bash
# Backup database
python -m scripts.auto_backup

# Restore from backup
python -m scripts.import_db exports/movies_backup_latest.json
```

**⚠️ Always backup before:**
- Importing new data
- Modifying database schema
- Running enrichment scripts
- Updating Python dependencies

---

## 🔄 Common Workflows

### **Workflow 1: Fresh Install**

```bash
pip install -r requirements.txt
python init_db.py --import
python app.py
```

### **Workflow 2: Add More Languages**

```bash
python -m scripts.auto_backup  # Backup first!
python -m scripts.production_bulk_import --language ta
python -m scripts.enrich_existing
```

### **Workflow 3: Weekly Update**

```bash
python -m scripts.auto_backup
python -m scripts.production_bulk_import --language te  # Gets new releases
python -m scripts.enrich_existing  # Fill missing data
```

### **Workflow 4: Production Deployment**

```bash
# 1. Set environment to production
echo FLASK_ENV=production >> .env
echo DEBUG=False >> .env

# 2. Use production server (not Flask dev server)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app

# 3. Setup scheduler for daily updates
python scheduler.py &  # Runs in background
```

---

## 🐛 Troubleshooting

### **Database Issues**

**Problem**: `no such table: movies`  
**Solution**: `python init_db.py`

**Problem**: Database deleted!  
**Solution**: `python -m scripts.import_db exports/movies_backup_latest.json`

### **Import Issues**

**Problem**: TMDB rate limit (HTTP 429)  
**Solution**: Wait 10 seconds and run again (script has auto-retry)

**Problem**: Import stopped halfway  
**Solution**: Just run again - script is idempotent (checks tmdb_id to avoid duplicates)

### **App Issues**

**Problem**: Port 5000 already in use  
**Solution**: `python app.py --port 8000` or kill existing process

**Problem**: Missing cast/OTT data  
**Solution**: `python -m scripts.enrich_existing`

### **Environment Issues**

**Problem**: TMDB_API_KEY not set  
**Solution**: Get key from [TMDB Settings](https://www.themoviedb.org/settings/api) and add to .env

**Problem**: SECRET_KEY error  
**Solution**: `python -c "import secrets; print(secrets.token_hex(32))"` and add to .env

---

## 📊 Expected Results

### After Initial Import (Telugu)
- **Runtime**: 30-60 minutes
- **Movies**: 3,000-4,000
- **Database**: 60-80 MB
- **With OTT Data**: ~40% (1,200-1,600 movies)

### After Multi-Language Import
- **Runtime**: 2-3 hours
- **Movies**: 10,000-15,000
- **Database**: 150-200 MB
- **Languages**: Telugu, Tamil, Hindi, Malayalam, Kannada

---

## 🔐 Environment Variables (.env)

```bash
# Required
SECRET_KEY=generate-with-secrets-module
TMDB_API_KEY=get-from-tmdb-website

# Admin Access
ADMIN_USERNAME=admin
ADMIN_PASSWORD=create-strong-password

# Optional
FLASK_ENV=development
DEBUG=True
```

---

## 📞 Quick Reference

```bash
# SETUP
python init_db.py --import              # One-command setup

# RUN APP
python app.py                           # Start server (port 5000)

# IMPORT DATA  
python -m scripts.production_bulk_import --language te  # Telugu
python -m scripts.production_bulk_import --language ta  # Tamil
python -m scripts.enrich_existing                       # Fill missing data

# BACKUP
python -m scripts.auto_backup           # Save database to JSON

# STATS
python -m scripts.db_stats              # Show database info

# MAINTENANCE (Optional)
python scheduler.py                     # Background automation
python -m scripts.daily_fetch           # Get new releases
```

---

## 📚 Additional Documentation

- **[PYTHON_FILES.md](PYTHON_FILES.md)** - Detailed guide to all Python files with use cases and deletion recommendations
- **requirements.txt** - Python package dependencies

---

## 🎯 Technology Stack

- **Backend**: Flask 3.0, SQLAlchemy, Python 3.8+
- **Database**: SQLite (production: PostgreSQL/MySQL supported)
- **Frontend**: HTML5, CSS3 (Grid/Flexbox), Vanilla JavaScript
- **APIs**: TMDB (metadata), JustWatch (OTT links)
- **Deployment**: Gunicorn, Nginx (production)

---

## 🎉 You're Ready!

**Start building:**
```bash
python init_db.py --import && python app.py
```

**🌟 Star Features:**
- Zero-download TMDB CDN architecture
- SEO-friendly movie URLs
- Mobile-first responsive design
- One-command setup
- Idempotent imports (safe to run multiple times)

---

**Last Updated**: February 6, 2026  
**Version**: 2.0 Production  
**Status**: ✅ Production Ready  
**License**: MIT

**Questions?** Check [PYTHON_FILES.md](PYTHON_FILES.md) for detailed Python file documentation.
| **base.html** | Navbar, footer - Shared across all pages |
| **index.html** | Homepage with 6 curated sections |
| **admin.html** | Admin dashboard - Stats, manual scrape |
| **404.html** | Error page |

### **Static/CSS/** - Styling

| File | Lines | Contains |
|------|-------|----------|
| **style.css** | ~1200 | All styles - Colors, layouts, animations, responsive design |

### **Static/JS/** - JavaScript

| File | Purpose |
|------|---------|
| **app.js** | Details modal, filters, search |
| **admin.js** | Admin panel interactions |

### **Scripts/** - Import & Maintenance

#### ✅ **PRODUCTION SCRIPTS** (Use These!)

| Script | Purpose | When to Run | Runtime |
|--------|---------|-------------|---------|
| **production_bulk_import.py** ⭐ | Main importer - Safe, idempotent | Initial setup, weekly updates | 30-60 min |
| **export_db.py** | Backup database to JSON | Before major changes | 10 sec |
| **import_db.py** | Restore from JSON backup | After database loss | 1-2 min |
| **auto_backup.py** | Daily automated backup | Schedule for midnight | 10 sec |

**production_bulk_import.py - The Star Script:**
```bash
# How it works:
1. Fetches movies from TMDB by popularity
2. Checks if movie exists (by tmdb_id)
3. If NEW → Adds to database
4. If EXISTS → Updates OTT platforms
5. NO DUPLICATES, NO DATA LOSS

# Safe to run multiple times!
python -m scripts.production_bulk_import --language te
python -m scripts.production_bulk_import --language ta
python -m scripts.production_bulk_import --language hi
```

#### ⚠️ **Legacy Scripts** (Optional/Deprecated)

| Script | Purpose | Note |
|--------|---------|------|
| bulk_import.py | Year-by-year import | Slower - use production_bulk_import instead |
| bulk_import_fast.py | Popularity import | Replaced by production_bulk_import |
| daily_fetch.py | Fetch last 7 days | Manually run if needed |
| enrich_existing.py | Backfill metadata | Use if missing cast/genres |
| scraper_service.py | Scheduled service | Not actively used |
| backup_fetcher.py | Alternative fetcher | Experimental |

### **Instance/** - Database

```
instance/
└── ott_tracker.db  # SQLite database - ALL YOUR MOVIES
                    # ⚠️ NEVER delete without backup!
                    # Size: 50-200 MB
```

### **Exports/** - Backups

```
exports/
├── movies_backup_20260203_120000.json   # Timestamped backups
├── movies_backup_20260203_140000.json
├── movies_backup_20260203_160000.json
└── movies_backup_latest.json            # Latest (for easy access)
```

---

## 💾 Database Design

### ✅ Single Database Recommended

**Why one database for all languages?**
- ✅ Easier to manage (one file to backup)
- ✅ Cross-language search works
- ✅ No database switching needed
- ✅ Better for "dubbed content" feature
- ✅ Simpler deployment

**How multi-language works:**
```python
# Each movie has:
language = 'te'        # Telugu
language = 'ta'        # Tamil
language = 'hi'        # Hindi

# Query by language:
Movie.query.filter_by(language='te').all()  # Only Telugu

# All languages:
Movie.query.all()  # Everything
```

### Movie Schema

```python
class Movie(db.Model):
    # PRIMARY KEY
    id = Integer (Auto-increment)
    tmdb_id = Integer (UNIQUE ← Prevents duplicates!)
    
    # BASIC INFO
    title = String(200)
    poster = String(500)      # Image URL
    backdrop = String(500)     # Large image URL
    overview = Text            # Plot summary
    release_date = String(20)  # YYYY-MM-DD
    rating = Float             # 0.0 to 10.0
    
    # CATEGORIZATION
    language = String(10)      # 'te', 'ta', 'hi', 'ml', 'kn'
    is_dubbed = Boolean        # False for originals
    genres = String(200)       # "Action, Drama, Thriller"
    certification = String(10) # "U", "U/A", "A"
    
    # METADATA
    runtime = Integer          # Minutes
    cast = Text                # "Actor1, Actor2, Actor3..."
    trailer = String(500)      # YouTube URL
    popularity = Float         # TMDB score
    
    # OTT PLATFORMS (JSON)
    ott_platforms = Text
    # Example:
    # {
    #   "Netflix": {"flatrate": true, "url": "...", "region": "IN"},
    #   "Prime Video": {"flatrate": true, "url": "..."}
    # }
    
    # TIMESTAMPS
    created_at = DateTime
    last_updated = DateTime
    last_checked = DateTime
    
    # FLAGS
    is_active = Boolean  # For soft delete
```

### Why tmdb_id is UNIQUE (Critical!)

```python
# Prevents duplicates when running import multiple times:

# First run:
Movie(tmdb_id=123, title="RRR")  → INSERTED

# Second run:
existing = Movie.query.filter_by(tmdb_id=123).first()
if existing:
    # UPDATE OTT platforms
else:
    # INSERT new movie

# Result: NO DUPLICATES! Safe to run anytime!
```

---

## 🔄 Import Strategies

### Strategy 1: Single Language (Fastest)

```bash
# Import only Telugu movies
python -m scripts.production_bulk_import --language te --pages 200
```

**Result:**
- ⏱️ Runtime: 30-60 minutes
- 📊 Movies: 3,000-4,000
- 💾 Database: 50-80 MB
- ✅ Perfect for Telugu-only app

### Strategy 2: Multi-Language (Comprehensive)

```bash
# Import multiple languages (run separately)
python -m scripts.production_bulk_import --language te  # Telugu
python -m scripts.production_bulk_import --language ta  # Tamil
python -m scripts.production_bulk_import --language hi  # Hindi
python -m scripts.production_bulk_import --language ml  # Malayalam
python -m scripts.production_bulk_import --language kn  # Kannada
```

**Result:**
- ⏱️ Runtime: 2-3 hours total
- 📊 Movies: 12,000-15,000
- 💾 Database: 150-200 MB
- ✅ Complete Indian cinema coverage

### Strategy 3: Update Existing (Safe!)

```bash
# Run import again to add NEW movies
python -m scripts.production_bulk_import --language te
```

**What happens:**
1. ✅ Checks each movie's tmdb_id
2. ✅ If EXISTS → Updates OTT platforms
3. ✅ If NEW → Adds to database
4. ✅ NO DUPLICATES
5. ✅ NO DATA LOSS

**Safe to run:**
- Daily for new releases
- Weekly for updates
- After fixing bugs
- Multiple times without worry

### Strategy 4: Custom Configuration

```bash
# Fetch more pages (more movies)
python -m scripts.production_bulk_import --language te --pages 300

# Different region
python -m scripts.production_bulk_import --language en --region US

# Minimal import (testing)
python -m scripts.production_bulk_import --language te --pages 10
```

---

## 🛡️ Backup & Safety

### Why You Need Backups

**Your database WILL be lost if:**
- ❌ Code crashes during import
- ❌ Accidental `rm -rf instance/`
- ❌ Disk corruption
- ❌ Windows update restarts mid-import
- ❌ Power outage

**Solution: Automatic Backups!**

### Setup Daily Backup (One-Time Setup)

**Windows Task Scheduler:**

1. Open Task Scheduler (Win + R → `taskschd.msc`)
2. Create Basic Task
3. Name: **OTT Tracker Daily Backup**
4. Trigger: **Daily at 12:00 AM**
5. Action: **Start a program**
   - Program: `python`
   - Arguments: `-m scripts.auto_backup`
   - Start in: `C:\Users\HP\OneDrive\Desktop\ott`
6. Finish

**Done!** Backup runs every night, keeps last 7 backups.

### Manual Backup (Before Big Changes)

```bash
# Before ANY major change:
python -m scripts.export_db
```

**Output:**
```
✅ DATABASE EXPORTED SUCCESSFULLY
   File: exports/movies_backup_20260203_220946.json
   Movies: 3,247
   Size: 12.3 MB
```

### Restore from Backup

```bash
# If database deleted/corrupted:
python -m scripts.import_db exports/movies_backup_latest.json
```

**What it does:**
```
1. Reads JSON file
2. For each movie:
   - If tmdb_id exists in DB → UPDATE
   - If tmdb_id is new → INSERT
3. Commits in batches (safe)
4. Shows progress

Result: Database restored! ✅
```

### Backup Checklist

Daily:
- [x] Auto-backup runs at midnight (Task Scheduler)

Before major changes:
- [ ] Manual export: `python -m scripts.export_db`

Monthly:
- [ ] Test restore: `python -m scripts.import_db exports/movies_backup_latest.json`
- [ ] Verify count matches

---

## 📅 Daily Usage

### Run the App

```bash
python app.py
```

**You'll see:**
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
 * Debugger is active!
```

**Visit:** http://127.0.0.1:5000

**Stop:** Press Ctrl+C

### Weekly Update (Add New Movies)

```bash
# Backup first
python -m scripts.export_db

# Update database with new releases
python -m scripts.production_bulk_import --language te
```

**Output:**
```
✅ IMPORT COMPLETED!
   ➕ New movies added: 47
   🔄 Existing updated: 3,186
   📊 Total in database: 3,233
```

**Safe to run anytime!** No duplicates created.

### Check Database Stats

```bash
# Total movies
python -c "from app import app; from models import Movie; app.app_context().push(); print(f'Total: {Movie.query.count()}')"

# By language
python -c "from app import app; from models import Movie; app.app_context().push(); print(f'Telugu: {Movie.query.filter_by(language=\"te\").count()}'); print(f'Tamil: {Movie.query.filter_by(language=\"ta\").count()}')"
```

### Manual Search Feature

**How it works:**
1. User searches for "RRR"
2. If not in database → Auto-fetch from TMDB
3. Add to database
4. Show results immediately

**No manual scraping needed!**

---

## 🐛 Troubleshooting

### ❌ Database Deleted!

**Symptoms:** `no such table: movies`, file missing

**Solution:**
```bash
# 1. Check if backups exist
dir exports\movies_backup_*.json

# 2. Restore from latest backup
python -m scripts.import_db exports/movies_backup_latest.json

# 3. Verify restoration
python -c "from app import app; from models import Movie; app.app_context().push(); print(Movie.query.count())"

# Expected: Shows previous movie count
```

### ❌ No Backups Found!

**Symptoms:** `exports/` folder empty

**Solution:**
```bash
# Re-import from TMDB (takes 30-60 min)
python -m scripts.production_bulk_import --language te

# Future prevention: Setup daily backup
# (See "Setup Daily Backup" section above)
```

### ⚠️ Import Stopped Halfway

**Symptoms:** Import script crashed, incomplete data

**Solution:**
```bash
# Just run it again! It's idempotent:
python -m scripts.production_bulk_import --language te
```

**Why it works:**
- Checks tmdb_id before adding
- Skips existing movies
- Only adds NEW movies
- Commits in batches (50 movies)

**Result:** Picks up where it left off!

### ⏱️ TMDB Rate Limit (HTTP 429)

**Symptoms:** `Too Many Requests`, import pauses

**Why:** TMDB allows 40 requests per 10 seconds

**Solution:**
```bash
# Wait 10 seconds, run again
python -m scripts.production_bulk_import --language te
```

**Script handles this automatically:**
- Built-in 0.3s delays
- Automatic retry with backoff
- Session pooling

**If still hitting limits:**
```python
# Edit scripts/production_bulk_import.py
time.sleep(0.5)  # Increase from 0.3 to 0.5
```

### 🔧 App Won't Start

**Check list:**
```bash
# 1. Database exists?
dir instance\ott_tracker.db

# 2. .env file present?
type .env

# 3. Dependencies installed?
pip install -r requirements.txt

# 4. Port already in use?
# Stop other Python processes
Stop-Process -Name python -Force
python app.py
```

### 📝 Missing Metadata (No cast, genres)

**Symptoms:** Movies have no cast, certification, runtime

**Cause:** Basic import only gets poster, title, rating

**Solution:**
```bash
# Enrich existing movies with full metadata
python -m scripts.enrich_existing
```

**What it does:**
1. Finds movies with empty cast/genres
2. Fetches from TMDB:
   - Cast (top 8 actors)
   - Certification (U, U/A, A)
   - Runtime, genres
   - Backdrop, trailer
3. Updates database
4. Limit: 200 movies per run

**Run multiple times until all enriched.**

---

## 🎯 Common Workflows

### Workflow 1: Brand New Setup

```bash
# Day 1: Setup
pip install -r requirements.txt
echo TMDB_API_KEY=your_key > .env

# Day 1: Test app (sample data)
python app.py
# Visit http://127.0.0.1:5000
# Stop with Ctrl+C

# Day 1: Import real movies
python -m scripts.production_bulk_import --language te
# Wait 30-60 minutes

# Day 1: Backup
python -m scripts.export_db

# Day 1: Run app with real data
python app.py
```

### Workflow 2: Add Another Language

```bash
# Step 1: Backup current database
python -m scripts.export_db

# Step 2: Import new language
python -m scripts.production_bulk_import --language ta

# Step 3: Verify counts
python -c "from app import app; from models import Movie; app.app_context().push(); print(f'Telugu: {Movie.query.filter_by(language=\"te\").count()}'); print(f'Tamil: {Movie.query.filter_by(language=\"ta\").count()}')"

# Step 4: Backup again
python -m scripts.export_db
```

### Workflow 3: Weekly Maintenance

```bash
# Every Sunday:

# 1. Backup
python -m scripts.export_db

# 2. Update with new releases
python -m scripts.production_bulk_import --language te

# 3. Clean old backups (auto_backup does this)
python -m scripts.auto_backup

# Done! New movies added, old backups cleaned
```

### Workflow 4: Disaster Recovery

```bash
# Oh no! Database deleted!

# Step 1: Don't panic - check backups
dir exports\

# Step 2: Restore latest
python -m scripts.import_db exports/movies_backup_latest.json

# Step 3: Verify
python -c "from app import app; from models import Movie; app.app_context().push(); print(Movie.query.count())"

# Step 4: If count looks good, restart app
python app.py

# Crisis averted! ✅
```

---

## 📊 Expected Results

### After First Import (Telugu)

```
Command: python -m scripts.production_bulk_import --language te
Runtime: 30-60 minutes

Results:
├── Movies Fetched: ~3,500
├── Added to DB: ~3,500
├── With OTT Data: ~1,400 (40%)
├── Database Size: 60 MB
├── Backup Size: 10 MB
└── Status: ✅ Ready for production
```

### After Multi-Language Import

```
Languages: Telugu + Tamil + Hindi
Runtime: 90-180 minutes

Results:
├── Total Movies: ~10,000
│   ├── Telugu (te): ~3,500
│   ├── Tamil (ta): ~3,200
│   └── Hindi (hi): ~3,300
├── With OTT Data: ~4,000 (40%)
├── Database Size: 150 MB
└── Backup Size: 28 MB
```

### After Running Import Again (Safe!)

```
First Run:  3,500 movies added
Second Run: 47 new movies added (weekly releases)
Third Run:  12 new movies added (daily releases)

✅ No duplicates created
✅ Existing movies updated
✅ OTT data refreshed
✅ Safe to run daily/weekly
```

---

## 🔧 Configuration

### .env File

```bash
# Required
TMDB_API_KEY=your_api_key_here_from_tmdb

# Optional
FLASK_ENV=development
SECRET_KEY=change_in_production
```

### Customize Import

**Change pages to fetch:**
```bash
# More pages = more movies
python -m scripts.production_bulk_import --language te --pages 300
```

**Change region:**
```bash
# Different OTT availability
python -m scripts.production_bulk_import --language hi --region US
```

**Edit script defaults:**
```python
# In scripts/production_bulk_import.py

# Line ~60: Change rate limit delay
time.sleep(0.5)  # From 0.3 to 0.5

# Line ~180: Change commit frequency
if count % 100 == 0:  # From 50 to 100
```

---

## 🚀 Next Steps

### Today
1. ✅ Backup: `python -m scripts.export_db`
2. ✅ Import: `python -m scripts.production_bulk_import --language te`
3. ✅ Run app: `python app.py`

### This Week
1. ✅ Setup daily backup (Task Scheduler)
2. ✅ Test restore from backup
3. ✅ Add more languages (if needed)

### Future
- [ ] User authentication
- [ ] Watchlist feature
- [ ] Email notifications
- [ ] Mobile app
- [ ] Telugu UI language

---

## 📞 Quick Reference

```bash
# IMPORT MOVIES
python -m scripts.production_bulk_import --language te    # Telugu
python -m scripts.production_bulk_import --language ta    # Tamil
python -m scripts.production_bulk_import --language hi    # Hindi

# BACKUP & RESTORE
python -m scripts.export_db                               # Export to JSON
python -m scripts.import_db exports/movies_backup_latest.json  # Restore
python -m scripts.auto_backup                             # Daily backup

# RUN APP
python app.py                                             # Start server

# CHECK DATABASE
python -c "from app import app; from models import Movie; app.app_context().push(); print(Movie.query.count())"
```

---

**🎉 Your OTT tracker is ready!**

**Golden Rule: Always backup before major changes!**

```bash
python -m scripts.export_db
```

**Last Updated:** February 3, 2026  
**Version:** 2.0 Production  
**Status:** ✅ Production Ready
