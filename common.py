import sqlite3
import hashlib
from unidecode import unidecode
import re
from datetime import datetime

DB_NAME = "billboard.db"

def get_db_connection():
    """
    Returns a connection to the SQLite database.
    Ensures WAL mode is enabled for better concurrency.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    # conn.execute("PRAGMA foreign_keys = ON;") # Optional: Enable if we want strict enforcement
    return conn

def init_db():
    """
    Initializes the database schema if it doesn't exist.
    """
    conn = get_db_connection()
    with conn:
        # 1. songs (The Identity Registry)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                song_id TEXT PRIMARY KEY,
                title TEXT, -- Display title
                artist TEXT, -- Display artist
                norm_title TEXT NOT NULL,
                norm_artist TEXT NOT NULL,
                variant_info TEXT, -- NEW: Store remix/feat info
                first_chart_date TEXT,
                last_chart_date TEXT,
                peak_rank INTEGER,
                weeks_top_100 INTEGER,
                weeks_top_10 INTEGER,
                yt_video_id TEXT,
                confidence_score REAL DEFAULT 0.0,
                sync_status TEXT DEFAULT 'unsynced', -- unsynced, dry_run_passed, synced, rejected
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(norm_title, norm_artist, variant_info) -- Updated constraint
            );
        """)

        # Migration helper (idempotent-ish check)
        try:
            conn.execute("ALTER TABLE songs ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP;")
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE songs ADD COLUMN variant_info TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE songs ADD COLUMN title TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE songs ADD COLUMN artist TEXT;")
        except sqlite3.OperationalError:
            pass

        # 2. chart_entries (The Temporal Record)
        # Added raw_title and raw_artist to allow reconstruction/normalization in Phase 2
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chart_entries (
                song_id TEXT NOT NULL,
                chart_date TEXT NOT NULL,
                rank INTEGER NOT NULL,
                raw_title TEXT,
                raw_artist TEXT,
                UNIQUE(song_id, chart_date),
                FOREIGN KEY(song_id) REFERENCES songs(song_id)
            );
        """)

        # 3. scrape_log (The Drift Detector)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                chart_date TEXT PRIMARY KEY,
                html_hash TEXT NOT NULL,
                scraped_at TEXT NOT NULL
            );
        """)
    conn.close()
    print(f"Database {DB_NAME} initialized.")

def generate_song_id(title: str, artist: str) -> str:
    """
    Generates a deterministic song_id using SHA256.
    song_id = SHA256(norm_title + "|" + norm_artist)
    """
    norm_title = normalize_text(title)
    norm_artist = normalize_text(artist)
    raw_string = f"{norm_title}|{norm_artist}"
    return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

def normalize_text(text: str) -> str:
    """
    Clean strings: No "feat.", lowercase, unidecode.
    """
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove "feat." and similar patterns for normalization, but we want to capture them before this
    text = re.sub(r'\bfeat\.?.*$', '', text)
    text = re.sub(r'\bft\.?.*$', '', text)
    
    # Remove parenthetical info (often remixes)
    text = re.sub(r'\(.*?\)', '', text)
    
    # Trim whitespace
    text = text.strip()
    
    # Unidecode (accent removal)
    text = unidecode(text)
    
    return text

def extract_variant_info(text: str) -> str:
    """
    Extracts 'feat.', 'ft.', and parenthetical info to store as variant data.
    """
    if not text:
        return ""
        
    variants = []
    
    # Capture feat/ft
    feat_match = re.search(r'\b(feat\.?|ft\.?)\s+(.*)$', text, re.IGNORECASE)
    if feat_match:
        variants.append(feat_match.group(0))
        
    # Capture parentheses
    paren_matches = re.findall(r'\(.*?\)', text)
    if paren_matches:
        variants.extend(paren_matches)
        
    return " ".join(variants) if variants else None

def get_song_metadata(song_id: str):
    """
    Retrieves metadata for a given song_id.
    """
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM songs WHERE song_id = ?", (song_id,)).fetchone()
    conn.close()
    return row

def update_sync_status(song_id: str, status: str):
    """
    Updates the sync_status for a song.
    Valid statuses: 'unsynced', 'dry_run_passed', 'synced', 'rejected'
    """
    valid_statuses = ['unsynced', 'dry_run_passed', 'synced', 'rejected']
    if status not in valid_statuses:
        raise ValueError(f"Invalid sync status: {status}. Must be one of {valid_statuses}")
        
    conn = get_db_connection()
    with conn:
        conn.execute("UPDATE songs SET sync_status = ? WHERE song_id = ?", (status, song_id))
    conn.close()

if __name__ == "__main__":
    init_db()
