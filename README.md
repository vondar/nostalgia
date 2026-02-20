# Billboard Reconstruction & Ingestion Engine (2013–2017)

## Overview
A deterministic, resumable, and state-aware ETL pipeline. This system extracts 5 years of Billboard Hot 100 history (260 weeks, 26,000 entries), anchors identity via SHA256 hashing, and performs policy-driven injection into YouTube Music via a confidence-weighted matching algorithm.

**Status**: Completed (2013-2017 Dataset Fully Acquired & Verified)
**Total Unique Songs**: 2,136
**Dominant Artist**: Drake (73 unique songs)

---

## Tech Stack (The "Final Form")

| Layer | Tech | Purpose |
| :--- | :--- | :--- |
| **Storage** | SQLite + WAL Mode | ACID-compliant persistence with atomic transaction boundaries. |
| **Identity** | SHA256 | Deterministic `song_id` generation to prevent entropy leak. |
| **Logic** | Python 3.11 / Polars | Vectorized data aggregation and history modeling. |
| **Parsing** | BeautifulSoup 4 (Hierarchical) | DOM-drift resistant scraping with canary checks. |
| **Matching** | Weighted Heuristics | Confidence-scored sync logic (Duration + Keyword + Title + Variant Info). |
| **API** | `ytmusicapi` | Unofficial YouTube Music API with session management. |

---

## Data Architecture (Hardened Schema)

### 1. `songs` (The Identity Registry)
- `song_id` (PK): `SHA256(norm_title + "|" + norm_artist)`
- `norm_title`, `norm_artist`: Cleaned strings (No "feat.", lowercase, unidecode).
- `variant_info`: Extracted remix/feature data (e.g., "Remix", "feat. X") used for search boosting.
- `first_chart_date`, `last_chart_date`: Era context.
- `peak_rank`, `weeks_top_100`, `weeks_top_10`: Computed metrics.
- `yt_video_id`: Found via dry-run.
- `confidence_score`: 0.0 to 1.0 based on match quality.
- `sync_status`: `unsynced`, `dry_run_passed`, `synced`, `rejected`.
- **Constraint:** `UNIQUE(norm_title, norm_artist)`

### 2. `chart_entries` (The Temporal Record)
- `song_id` (FK), `chart_date`, `rank`.
- `raw_title`, `raw_artist`: Original text for auditing/re-normalization.
- **Constraint:** `UNIQUE(song_id, chart_date)`

### 3. `scrape_log` (The Drift Detector)
- `chart_date` (PK), `html_hash`, `scraped_at`.
- Used to detect if the source site has changed its structure between runs.

---

## The Pipeline Execution

### Phase 1: Extraction & Fingerprinting (`01_scrape.py`)
- **Hierarchical Selectors**: Uses context-aware DOM parsing to survive layout shifts (e.g., 2014 vs 2015 layouts).
- **Canary Checks**: Fails fast if entry count < 100 to prevent data pollution.
- **Atomic Transactions**: Inserts `chart_entries` and updates `scrape_log` in one block.
- **Exponential Backoff**: Handles rate limits with random jitter.

### Phase 2: Normalization & Variant Extraction (`02_normalize.py`)
- **Registry Authority**: Can re-process the entire raw dataset to fix normalization bugs without re-scraping.
- **Variant Logic**: Extracts metadata like "Remix" or "Radio Edit" into `variant_info` to improve YouTube search accuracy.
- **Identity Drift Detection**: Alerts if a code change would alter existing `song_id` hashes.

### Phase 3: Analytical Aggregation (`03_aggregate.py`)
- **Polars Engine**: High-performance aggregation of 26,000+ rows.
- **Metrics**: Computes `peak_rank`, `weeks_on_chart`, and `weeks_top_10`.
- **Date Snapping**: Ensures all chart dates align to Saturdays for consistency.

### Phase 4: Metadata & Dry-Run (`04_yt_verify.py`)
- **Search Strategy**: Uses `norm_title`, `norm_artist`, and `variant_info` for targeted queries.
- **Confidence Scoring**:
    - **Duration Delta**: `(1 - abs(yt_dur - meta_dur) / meta_dur)` (ISO 8601 parsing).
    - **Keyword Penalty**: Deduct points for "live", "video", "remix" (if not in metadata).
    - **Variant Boost**: Bonus points if `variant_info` matches the video title.
    - **Uploader Bonus**: Extra points for "Official Artist Channel" or "Topic" channels.

### Phase 5: Policy-Driven Deployment (`05_yt_sync.py`)
- **Session Blocks**: Limits sync to **500 songs per session** with a **1-hour cooldown** to avoid Google account flags.
- **Batching**: Commits to YouTube in chunks of 50.
- **Command**:
  ```bash
  python 05_yt_sync.py --live --min-confidence 0.90 --session-limit 500
  ```

---

## Engineering Standards

1.  **Idempotency**: Every script is safe to run $N$ times.
2.  **Atomicity**: SQLite transactions ensure partial failures don't corrupt the DB.
3.  **No Entropy**: String matching is a fallback. Hashing is the primary key.
4.  **Observability**: `PROGRESS.md` tracks the state of the system.

---

## Usage Workflow

1.  **Ingest**: `python 01_scrape.py` (Updates `chart_entries` & `scrape_log`)
2.  **Refine**: `python 02_normalize.py` (Updates `songs` registry & `variant_info`)
3.  **Analyze**: `python 03_aggregate.py` (Computes metrics)
4.  **Verify**: `python 04_yt_verify.py` (Populates `confidence_score`)
5.  **Deploy**: `python 05_yt_sync.py --live --min-confidence 0.90`

---

## Why This Matters
You aren't just making a playlist. You are creating a queryable database of a five-year pop-era. By anchoring everything to a `song_id`, you can eventually join this data against anything—Spotify play counts, lyrics sentiment, or BPM data—without ever having to fix a "feat." typo again.

**Build it for the 2028 version of yourself who will want to re-run this and expect it to still work.**
