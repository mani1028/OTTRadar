
# 🎬 OTT Movie Discovery & Enrichment Platform

A complete movie discovery, enrichment, and OTT availability tracking system powered by TMDB API.

---

## ⚠️ Important Notice: Missing Scripts

As of February 2026, the following scripts are missing from the repository and some automation features may not work:

- `scripts/discover_new_movies.py` (movie discovery/import)
- `scripts/enrich_metadata_trailers.py` (metadata enrichment)

If you need these features, please restore these scripts from backup or contact the maintainer.

---

## 🚨 STATUS: Ready for Database Enrichment

**Target: 95%+ metadata completeness with a two-phase flow.**

📈 **Two-Phase Enrichment:**
- ✅ Phase 1 (TMDB): Unlimited - full metadata pass
- ✅ Phase 2 (OMDb): Rate-limited (1000/day) - fill remaining gaps

**Recommended commands:**
```bash

# Phase 1 (TMDB)
# (Script missing: enrich_metadata_trailers.py)

# Phase 2 (OMDb) - smart, rate-limit safe
python scripts/smart_omdb_enrichment.py --limit 500

# Check remaining gaps
python scripts/complete_enrichment.py --dry-run
```

---

## 🎯 What This Does

- **📽️ Discover Movies** - Find new movies from TMDB, track what's missing in your DB
- **😊 Enrich with Details** - Fetch metadata, trailers, cast, ratings automatically
- **📺 Add OTT Platforms** - Show which streaming services have each movie (Netflix, Prime, Hotstar, etc.)
- **🔍 Search Fallbacks** - Auto-generate search links when direct links unavailable
- **📊 Track Changes** - Monitor daily OTT availability changes and price drops
- **💾 Bulk Operations** - Import/export entire database, batch enrichment

---

## ⚡ Quick Start (5 Minutes)

### **1. Setup**

```bash
# Install dependencies
pip install -r requirements.txt

# Create database
python db_init.py

# Set TMDB API key in .env
echo "TMDB_API_KEY=your_api_key_here" > .env
```


### **2. Find & Import Movies**

```bash
# Find 100 missing movies from TMDB
python scripts/track_missing_movies.py --find 100 --save
# (Script missing: discover_new_movies.py)
```

### **3. Enrich with Metadata**

```bash
# (Script missing: enrich_metadata_trailers.py)
```

### **4. Check Results**

```bash
# See OTT coverage
python scripts/manage_ott_links.py --report
```

**Result:** Movies found and tracked. For enrichment and import, restore missing scripts.

---

## 🧭 Script Usage (One-Time vs Regular)

**One-time setup / migrations:**
- `db_init.py` - Initialize the SQLite database
- `scripts/import_db.py` - Restore from a backup (use carefully)
- `scripts/migrate_add_ott_release_date.py` - Adds `ott_release_date` column


**Regular operations (safe to run often):**
- `scripts/smart_omdb_enrichment.py` - OMDb gap filling (1000/day)
- `scripts/track_missing_movies.py` - Find missing TMDB titles
- `scripts/manage_ott_links.py --report` - OTT coverage report
- `scripts/daily_ott_checker.py` - Daily OTT link checks
- `scripts/export_db.py` - Create JSON backup
- `scripts/complete_enrichment.py --dry-run` - Missing-field summary

*Note: Some enrichment and discovery scripts are missing. See notice above.*

**Admin portal runnable scripts:**
- TMDB Enrichment (limited batch)
- OMDb Gap Fill (rate-limited)
- Track Missing Movies
- Import New Movies
- Daily OTT Checker
- Export Database
- OTT Coverage Report

---

## 📁 Project Structure


```bash
# 2. Can import scripts
# (Script missing: enrich_metadata_trailers.py)

# 3. Can find missing movies
python scripts/track_missing_movies.py --find 5 --save

# 4. Can enrich a movie
# (Script missing: enrich_metadata_trailers.py)

# 5. Can check OTT
python scripts/manage_ott_links.py --report
```
│   └── ott_link_api.py          # Flask helpers for OTT
│
├── 🛠️ Utilities
│   ├── admin_utils.py           # Admin helpers
│   ├── affiliate_utils.py       # Affiliate link management
│   └── gunicorn_config.py       # Production server config
│
├── 📜 Scripts (in `scripts/` folder)
│   ├── enrich_metadata_trailers.py     # Main TMDB enrichment
│   ├── smart_omdb_enrichment.py        # OMDb gap-filling with tracking
│   ├── complete_enrichment.py          # Missing-field summary
│   ├── track_missing_movies.py         # Find new movies
│   ├── discover_new_movies.py          # Import movies to DB
│   ├── manage_ott_links.py             # OTT coverage reports
│   ├── export_db.py                    # Backup database
│   ├── import_db.py                    # Restore database
│   ├── daily_ott_checker.py            # Daily OTT checks
│   ├── scheduler_background.py         # Automated tasks
│   └── migrate_add_ott_release_date.py # One-time migration
│
├── 🌐 Web Interface
│   ├── templates/                # HTML pages
│   ├── static/                   # CSS, JS
│   └── ... (other assets)
│
└── 📦 Data
    ├── instance/ott.db          # SQLite database (auto-created)
    ├── exports/                 # Database backups
    └── logs/                    # Application logs
```

---

## 🚀 Core Features

### **1. Movie Discovery**

Find movies not yet in your database:

```bash
python scripts/track_missing_movies.py --find 100 --save
```

**Features:**
- Searches TMDB for popular movies (2020-2024)
- Automatically filters out existing DB movies
- Saves to `missing_movies.json` for bulk import
- Shows report by year and popularity

---

### **2. Metadata Enrichment**

Fetch complete movie details from TMDB:

```bash
python scripts/enrich_metadata_trailers.py --limit 50
```

**Fetches:**
- Overview, rating, popularity
- Poster & backdrop images
- YouTube trailer ID
- Cast & crew
- OTT platforms
- Fallback search URLs

---

### **3. OTT Platform Integration**

Automatically adds watch links:

```bash
python scripts/manage_ott_links.py --report
```

**Platforms Supported (13+):**
Netflix, Prime Video, Disney+ Hotstar, JioCinema, ZEE5, SonyLIV, Apple TV, Airtel Xstream, MX Player, Voot, aha, YouTube Movies, and custom platforms.

---

### **4. Two-Tier Link Strategy**

Each platform has fallback:
- Direct Link (if available) → Search Link (auto-generated)

Example:
- Netflix: `netflix.com/search?q=movie-name`
- Prime: `primevideo.com/search?phrase=movie-name`
- Hotstar: `hotstar.com/in/search?q=movie-name`

---

### **5. Bulk Operations**

Import/export entire database:

```bash
# Backup database
python scripts/export_db.py

# Restore from backup
python scripts/import_db.py --file backup.json --merge
```

---

## 📊 Main Workflows

### **Workflow: Add 100 New Movies (20 mins)**

```bash
# 1. Find missing movies
python scripts/track_missing_movies.py --find 100 --save

# 2. Review them
python scripts/track_missing_movies.py --report

# 3. Import to database
python scripts/discover_new_movies.py --import-from-json

# 4. Enrich with details + OTT
python scripts/enrich_metadata_trailers.py --limit 100

# 5. Verify
python scripts/manage_ott_links.py --report
```

---

## 🔧 Configuration

### **Set TMDB API Key**

Create `.env` file:
```
TMDB_API_KEY=your_key_from_https://www.themoviedb.org/settings/api
```

Get free key at: https://www.themoviedb.org/settings/api

### **Change Database**

Edit `config.py`:
```python
SQLALCHEMY_DATABASE_URI = 'sqlite:///ott.db'  # SQLite
```

---

## 📋 All Available Scripts

**Complete documentation: See [SCRIPTS.md](SCRIPTS.md)**

Quick reference:

| Script | Command | Purpose |
|--------|---------|---------|
| enrich_metadata_trailers.py | `python scripts/enrich_metadata_trailers.py --limit 50` | Fetch TMDB + OTT |
| track_missing_movies.py | `python scripts/track_missing_movies.py --find 100 --save` | Find new movies |
| discover_new_movies.py | `python scripts/discover_new_movies.py --import-from-json` | Import to DB |
| manage_ott_links.py | `python scripts/manage_ott_links.py --report` | Check OTT coverage |
| export_db.py | `python scripts/export_db.py` | Backup DB |
| import_db.py | `python scripts/import_db.py --file backup.json` | Restore DB |
| daily_ott_checker.py | `python scripts/daily_ott_checker.py` | Daily OTT checks |

---

## 🌐 Using in Flask

### **Show Watch Links in Template**

```html
<!-- templates/movie.html -->
<div class="watch-links">
  {% for link in movie.get_ott_links() %}
    <a href="{{ link.url }}" target="_blank">
      📺 Watch on {{ link.provider_name }}
    </a>
  {% endfor %}
</div>
```

### **Get Links in Python**

```python
from models import Movie

movie = Movie.query.get(123)
links = movie.get_ott_links()  # Returns list of clickable links
```

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for more examples.

---

## ✅ Quick Setup Verification

After setup, verify everything works:

```bash
# 1. Database created
ls -la instance/ott.db

# 2. Can import scripts
python -c "from scripts.enrich_metadata_trailers import enrich_movie"

# 3. Can find missing movies
python scripts/track_missing_movies.py --find 5 --save

# 4. Can enrich a movie
python scripts/enrich_metadata_trailers.py --limit 1

# 5. Can check OTT
python scripts/manage_ott_links.py --report
```

All ✅? You're ready!

---

## 🚨 Common Issues

| Issue | Solution |
|-------|----------|
| TMDB_API_KEY not found | Create `.env` with your API key |
| Database locked | Delete `instance/ott.db` and re-create |

| No movies enriched | Run `track_missing_movies.py --find 10 --save` first (enrichment unavailable until script is restored) |
| OTT links not showing | (enrichment unavailable until script is restored) |

See [SCRIPTS.md](SCRIPTS.md) for more troubleshooting.

---

## 📈 Next Steps

1. **Create `.env`** with TMDB API key
2. **Run `python db_init.py`** to initialize database
3. **Start with:** `python scripts/track_missing_movies.py --find 100 --save`
4. **Then follow:** [SCRIPTS.md](SCRIPTS.md) for detailed usage

---

## 📚 Documentation Files


- **[SCRIPTS.md](SCRIPTS.md)** - Detailed reference for all available scripts with examples
- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** - Code examples for Flask integration
- **README.md** - This file (project overview)

---

## 🛡️ Robust Error Handling

External API calls (TMDB, OMDb, etc.) are now protected with robust error handling. The app will not crash if a connection fails or a remote API is down. See `app.py` for details.

---

---

**Built with ❤️ using TMDB API, Flask, and SQLAlchemy**
