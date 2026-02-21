# 📜 OTT Radar Script Operations Guide

This guide explains the **8 essential scripts** powering the OTT Radar platform. It tells you exactly **what** they do, **where** to run them, and **how** to use them.

---

## 🚦 Execution Environments

You can run your scripts in two places:

1. **💻 The Terminal:** Running scripts directly on your server or local computer's command line.
2. **🌐 The Admin Panel:** Clicking buttons in your web dashboard (`/admin`).

---

## 🤖 1. The Automation Engine (Terminal Only)

These scripts keep your platform running on autopilot.

### `scheduler_background.py`

* **What it does:** The "Brain" of your platform. It stays awake in the background and automatically triggers all other scripts on a schedule (e.g., finding new movies at 2 AM, updating OTT links at midnight).
* **Where to run it:** **💻 Terminal ONLY.**
* **How to run it:** You should start this script once and leave it running in the background using a tool like `tmux` or `screen` on your server.
```bash
python scripts/scheduler_background.py
```

---

## 🎬 2. Content Fetchers (Admin Panel or Terminal)

If you don't want to wait for the Scheduler, you can use these scripts to manually force updates right now.

### `discover_new_movies.py`

* **What it does:** Safely talks to the TMDB API to find brand new movies and adds a basic, empty shell for them in your database.
* **Where to run it:** 💻 Terminal or 🌐 Admin Panel.
* **How to run it (Terminal):**
```bash
# Find 100 popular movies from 2024
python scripts/discover_new_movies.py --year 2024 --limit 100
```

### `enrich_metadata_trailers.py`

* **What it does:** The Heavy Lifter. It looks at the empty movie shells in your database and fills them with Posters, Overviews, YouTube Trailers, and OTT Platform links (Netflix, Prime, etc.).
* **Where to run it:** 💻 Terminal or 🌐 Admin Panel (Click "Enrich Metadata").
* **How to run it (Terminal):**
```bash
# Enrich 200 movies that are missing data
python scripts/enrich_metadata_trailers.py --limit 200
```

### `daily_ott_checker.py`

* **What it does:** Scans your database for "Upcoming" movies. If today is their release date, it flips their status to "Available" so they appear on the homepage.
* **Where to run it:** 💻 Terminal or 🌐 Admin Panel.
* **How to run it (Terminal):**
```bash
python scripts/daily_ott_checker.py
```

---

## 💾 3. Database Savers (Terminal Recommended)

Use these scripts for backups and disaster recovery.

### `export_db.py`

* **What it does:** Creates a full JSON backup file of your entire database inside the `exports/` folder.
* **Where to run it:** 💻 Terminal or 🌐 Admin Panel (Click "Export Database").
* **How to run it (Terminal):**
```bash
python scripts/export_db.py
```

### `import_db.py`

* **What it does:** Restores your database from a JSON backup file if something goes wrong.
* **Where to run it:** **💻 Terminal ONLY.** *(For security, you should never allow the web dashboard to overwrite your whole database).*
* **How to run it (Terminal):**
```bash
# Replace the filename with your actual backup file
python scripts/import_db.py exports/movies_backup_20260215.json
```

---

## ⚙️ 4. Helper Libraries (DO NOT RUN)

These files sit in your `scripts/` folder, but you **never run them manually**. Your Flask web app (`app.py`) automatically reads them to make the website work.

1. **`ott_link_builder.py`**: Contains the logic to generate exact search URLs for Netflix, Amazon Prime, Hotstar, etc., when a user clicks "Watch".
2. **`ott_release_features.py`**: Does the math to calculate countdowns (e.g., "Releasing in 5 Days") for the frontend UI.

---

## 🎯 Common Workflows

### Scenario 1: "I want the site to run itself forever."

1. Open your terminal.
2. Run `python scripts/scheduler_background.py`.
3. Close the terminal (if using `tmux`). You're done.


### Scenario 2: "I want to manually add movies right now."

<!--
1. Run `python scripts/discover_new_movies.py --limit 100` to pull 100 new titles.
2. Run `python scripts/enrich_metadata_trailers.py --limit 100` to download their posters and trailers.
-->
*Scripts for manual discovery and enrichment are currently missing. Restore from backup if needed.*
3. Refresh your website!
---

## ⚠️ Notice: Missing Scripts

The following scripts are currently missing from the repository:
- `discover_new_movies.py`
- `enrich_metadata_trailers.py`

Some automation and enrichment features may be unavailable until these are restored.

### Scenario 3: "I'm about to make a risky change to the code."

1. Run `python scripts/export_db.py` to create a safe backup.
2. If your change breaks the site, run `python scripts/import_db.py exports/YOUR_BACKUP_FILE.json` to undo the damage.
