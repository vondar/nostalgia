# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Dashboard**: Created `dashboard.py` (Streamlit/Plotly) for interactive data exploration. Features include:
    - Bento Box layout for high-level KPIs.
    - Longevity vs. Peak Rank scatter plot with "Gold Zone" highlighting.
    - Sparkline visualizations for individual song chart histories.
    - Artist market share visualization.
- **Metadata**: Added `title` and `artist` columns to `songs` table to store human-readable display names (separate from normalized search keys).
- **Metadata**: Added `sync_status`, `first_chart_date`, `last_chart_date`, and `weeks_top_10` to `songs` schema.

### Changed
- **Schema**: Updated `songs` table schema in `common.py` and `METADATA.md` to strictly define types and constraints.
- **Scraper**: Updated `01_scrape.py` to capture and insert raw `title` and `artist` strings directly into the registry.
- **Migration**: Ran `migrate_metadata.py` to backfill display titles/artists for all 2,136 existing songs using historical chart data.

### Fixed
- **Dashboard**: Resolved `ComputeError` in Polars by handling `None None` strings in `variant_info` and adding `schema_overrides`.
- **Docs**: Aligned `METADATA.md` with the actual codebase state, fixing missing column definitions.

## [Initial Release] - 2013-2017 Dataset

### Added
- Initial project scaffolding based on `README.md` specifications.
- `requirements.txt`: Added dependencies (`polars`, `requests`, `beautifulsoup4`, `unidecode`, `ytmusicapi`).
- `common.py`:
    - Implemented SQLite database initialization with WAL mode.
    - Defined schema for `songs`, `chart_entries`, and `scrape_log`.
    - Added `generate_song_id` (SHA256) and `normalize_text` utilities.
- `01_scrape.py`:
    - Implemented logic to fetch and hash Billboard HTML.
    - Added atomic transaction support for inserting chart entries.
    - Added logic to populate `songs` table with minimal info during scrape.
- `02_normalize.py`:
    - Created script to verify identity drift and populate the song registry.
    - Implemented checks for hash collisions.
- `03_aggregate.py`:
    - Implemented metrics calculation (`peak_rank`, `weeks_top_10`, etc.) using Polars.
    - Added logic to update `songs` table with aggregated data.
- `04_yt_verify.py`:
    - Implemented YouTube Music search and verification logic.
    - Added confidence scoring based on duration, title match, and uploader.
    - Added `parse_duration` utility to handle timestamp strings.
- `05_yt_sync.py`:
    - Implemented playlist creation and synchronization logic.
    - Added support for `--live` and `--dry-run` modes.

### Fixed
- **HTML Parsing**: Fixed "The Wednesday Bug" by implementing date-snapping logic (forcing all scrape dates to Saturday).
- **Selector Logic**: Fixed "RE-ENTRY" and "NEW" badge bugs by implementing hierarchical DOM traversal instead of relying on fragile CSS classes.
- **Data Integrity**: Fixed 2014 data leakage (58-week year) by purging corrupted data and re-scraping with strict date boundaries.
- `01_scrape.py`: Fixed critical bug where "NEW" and "RE-ENTRY" badges were incorrectly scraped as artist names. Updated CSS selectors to use `span.c-label.a-no-trucate`.
- `03_aggregate.py`: Removed `connectorx` dependency to fix import errors, switched to manual cursor fetching.

### Changed
- **Schema Update**: Added `variant_info` column to `songs` table to preserve remix/feat details without breaking normalization.
- **Data Cleanup**: Purged and re-scraped 2013 data to eliminate corrupted artist entries caused by the badge selector bug.
- **Validation**: Added `audit_2013.py` and `audit_deep.py` for rigorous data quality checks (confirmed 0% badge artifacts).
- `common.py`: 
    - Updated `chart_entries` schema to include `raw_title` and `raw_artist` for better normalization support.
    - Added `created_at` timestamp to `songs` table (with migration check).
    - Added `extract_variant_info` utility for smart remix detection.
- `03_aggregate.py`: Switched from `pl.read_database` to manual cursor fetching to reduce dependencies/complexity with SQLite.
- `01_scrape.py`: 
    - Added exponential back-off and random jitter (1-3s) to request logic to prevent rate limiting.
    - Implemented "Canary Check" to fail fast if DOM layout changes (prevents empty scrapes).
- `04_yt_verify.py`: 
    - Improved `parse_duration` to handle ISO 8601 (`PT#M#S`) format alongside `MM:SS`.
    - Updated confidence scoring to boost "Topic" channels and official VEVO content.
- `01_scrape.py`: 
    - Implemented robust HTML parsing using BeautifulSoup with updated selectors.
    - Added CLI arguments (`--start`, `--end`) for custom date range scraping.
    - Added in-memory deduplication to handle duplicate song entries on the same chart.
- `05_yt_sync.py`: Implemented batched playlist addition (chunks of 50) with jitter to avoid YouTube Music rate limits.
