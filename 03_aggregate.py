import polars as pl
import common
import sqlite3

def aggregate_metrics():
    conn = common.get_db_connection()
    print("Loading chart entries into Polars...")
    
    # Read chart_entries manually to avoid extra dependencies for read_database
    cursor = conn.cursor()
    cursor.execute("SELECT song_id, chart_date, rank FROM chart_entries")
    rows = cursor.fetchall()
    
    if not rows:
        print("No chart entries found.")
        return

    # Convert to Polars DataFrame
    # rows are sqlite3.Row objects, convert to list of dicts or just tuples with schema
    data = [dict(row) for row in rows]
    df = pl.DataFrame(data)

    print(f"Aggregating metrics for {df.height} entries...")

    # Convert chart_date to Date type if needed, but string comparison works for min/max ISO dates
    # But for weeks calculation, we just count rows per song_id (assuming one entry per week)
    
    # Aggregation
    metrics = df.group_by("song_id").agg([
        pl.col("chart_date").min().alias("first_chart_date"),
        pl.col("chart_date").max().alias("last_chart_date"),
        pl.col("rank").min().alias("peak_rank"),
        pl.col("rank").count().alias("weeks_top_100"),
        (pl.col("rank") <= 10).sum().alias("weeks_top_10")
    ])
    
    print(f"Updating {metrics.height} songs...")
    
    # Convert back to list of dicts or tuples for SQLite update
    # Polars to_dicts() is easy
    updates = metrics.to_dicts()
    
    # Batch update
    with conn:
        conn.executemany("""
            UPDATE songs 
            SET first_chart_date = :first_chart_date,
                last_chart_date = :last_chart_date,
                peak_rank = :peak_rank,
                weeks_top_100 = :weeks_top_100,
                weeks_top_10 = :weeks_top_10
            WHERE song_id = :song_id
        """, updates)
        
    print("Aggregation complete.")

if __name__ == "__main__":
    aggregate_metrics()
