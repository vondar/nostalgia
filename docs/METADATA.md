# Project Metadata & Data Dictionary

## 1. Overview
This dataset is a temporal reconstruction of the Billboard Hot 100 from **January 5, 2013, to December 30, 2017**. It tracks 26,000 individual chart entries and distills them into a registry of 2,136 unique cultural artifacts.

## 2. The Identity Model (The "Hash")
To avoid the entropy of string matching, every song is assigned a deterministic `song_id`.
*   **Logic:** `SHA256(norm_title + "|" + norm_artist)`
*   **Normalization:** All titles/artists are lowercased, stripped of punctuation, and flattened via `unidecode`.
*   **Purpose:** This ID is immutable. Even if the DOM changes or the artist changes their name, as long as the normalized strings match, the identity remains stable.

---

## 3. Data Dictionary

### Table: `songs` (The Registry)
The "Source of Truth" for unique tracks.

| Field | Type | Description |
| :--- | :--- | :--- |
| `song_id` | TEXT (PK) | 16-character SHA256 truncated hash. |
| `title` | TEXT | The primary song title as it first appeared. |
| `artist` | TEXT | The primary artist credited. |
| `norm_title` | TEXT | Sanitized title for search and hashing. |
| `norm_artist` | TEXT | Sanitized artist name. |
| `variant_info` | TEXT | Preserved metadata (e.g., "feat. Drake", "Remix"). |
| `peak_rank` | INTEGER | Highest rank achieved (1-100). |
| `weeks_top_100` | INTEGER | Total weeks on Hot 100. |
| `weeks_top_10` | INTEGER | Total appearances ranked 1–10. |
| `first_chart_date` | DATE | Date of the song's debut on the chart. |
| `last_chart_date` | DATE | Date of the song's final appearance in this era. |
| `yt_video_id` | TEXT | Verified YouTube Music video identifier. |
| `confidence_score` | REAL | Match confidence (0.0-1.0). |
| `sync_status` | TEXT | Sync state: 'unsynced', 'synced', 'rejected'. |
| `created_at` | TEXT | UTC timestamp of record creation. |

### Table: `chart_entries` (The Time-Series)
Raw weekly snapshots.

| Field | Type | Description |
| :--- | :--- | :--- |
| `song_id` | TEXT (FK) | Reference to the `songs` table. |
| `chart_date` | DATE | The Saturday-aligned date of the Billboard chart. |
| `rank` | INTEGER | The position for that specific week (1-100). |
| `raw_title` | TEXT | The exact HTML string captured (for debugging). |
| `raw_artist` | TEXT | The exact HTML string captured. |

---

## 4. Business Rules & Constraints

### The Saturday Alignment (The "Wednesday Bug" Fix)
Billboard charts are anchored to Saturdays. All `chart_date` values are automatically "snapped" to the nearest Saturday during ingestion to prevent temporal drift.

### The Recurrent Rule (The 20-Week Spike)
Billboard forcibly removes songs from the Hot 100 if they fall below #50 after 20 weeks. This creates a statistical "cliff" in the `weeks_top_100` distribution visible in the dashboard.

### Verification Logic
A YouTube Music match is considered "High Confidence" (>0.8) if:
1.  The uploader is a "Topic" or "VEVO" channel.
2.  The duration matches the official metadata within a ±15s threshold.
3.  The `norm_title` exists within the `yt_title`.

---

## 5. Known Limitations
*   **Era Bounds:** Data outside 2013-01-05 and 2017-12-30 is not present. If a song debuted in 2012, its `first_chart_date` here will incorrectly be Jan 2013. 
*   **Artist Grouping:** Collaborations are hashed as a single string. "Rihanna" and "Rihanna feat. Drake" are treated as two distinct artists unless the `variant_info` logic successfully separates them.
*   **YouTube Availability:** Deleted videos or geoblocked content will result in a `null` `yt_video_id`.

---

## 6. Maintenance
To refresh the metrics without re-scraping:
1.  Run `03_aggregate.py`. 
2.  Polars will re-scan `chart_entries` and overwrite `peak_rank` and `weeks_top_100` in the `songs` table.
3.  Restart the Streamlit dashboard to clear the `@st.cache_data`.