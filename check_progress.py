
import common
conn = common.get_db_connection()
cursor = conn.cursor()

# Tables
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
print("Tables:", [t[0] for t in tables])

# Songs
try:
    song_count = cursor.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
    print(f"Total Songs: {song_count}")
except Exception as e:
    print(f"Error counting songs: {e}")

# Entries
try:
    entry_count = cursor.execute("SELECT COUNT(*) FROM chart_entries").fetchone()[0]
    print(f"Total Chart Entries: {entry_count}")
except Exception as e:
    print(f"Error counting entries: {e}")

# Weeks
try:
    week_count = cursor.execute("SELECT COUNT(*) FROM scrape_log").fetchone()[0]
    print(f"Weeks Scraped: {week_count}")
except Exception as e:
    print(f"Error counting weeks: {e}")

# Date Range
try:
    min_date = cursor.execute("SELECT MIN(chart_date) FROM scrape_log").fetchone()[0]
    max_date = cursor.execute("SELECT MAX(chart_date) FROM scrape_log").fetchone()[0]
    print(f"Date Range: {min_date} to {max_date}")
except Exception as e:
    print(f"Error getting date range: {e}")

# Breakdown by Year
print("\nEntries per Year:")
for year in range(2013, 2018):
    try:
        count = cursor.execute("SELECT COUNT(*) FROM chart_entries WHERE chart_date LIKE ?", (f"{year}%",)).fetchone()[0]
        log_count = cursor.execute("SELECT COUNT(*) FROM scrape_log WHERE chart_date LIKE ?", (f"{year}%",)).fetchone()[0]
        print(f"{year}: {count} entries, {log_count} weeks logged")
    except Exception as e:
        print(f"{year}: Error {e}")
