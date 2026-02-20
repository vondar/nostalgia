import common
import sys

def normalize_and_populate():
    conn = common.get_db_connection()
    cursor = conn.cursor()
    
    print("Fetching all chart entries...")
    # Fetch all raw entries to verify/re-populate songs registry
    cursor.execute("SELECT rowid, song_id, raw_title, raw_artist FROM chart_entries")
    entries = cursor.fetchall()
    
    print(f"Processing {len(entries)} entries...")
    
    songs_cache = {} # song_id -> (norm_title, norm_artist)
    
    # Pre-load existing songs to minimize DB hits and check for collisions
    cursor.execute("SELECT song_id, norm_title, norm_artist FROM songs")
    for row in cursor.fetchall():
        songs_cache[row['song_id']] = (row['norm_title'], row['norm_artist'])
        
    updates = 0
    errors = 0
    
    with conn:
        for entry in entries:
            raw_title = entry['raw_title']
            raw_artist = entry['raw_artist']
            stored_song_id = entry['song_id']
            
            # Re-generate ID to verify consistency
            generated_id = common.generate_song_id(raw_title, raw_artist)
            norm_title = common.normalize_text(raw_title)
            norm_artist = common.normalize_text(raw_artist)
            
            # Check for Identity Drift (stored ID != generated ID)
            # This happens if normalization logic changes or if data was corrupted
            if stored_song_id != generated_id:
                print(f"CRITICAL: Identity Drift for '{raw_title}' by '{raw_artist}'. Stored: {stored_song_id}, Generated: {generated_id}")
                # Optional: Update chart_entry to point to new ID?
                # conn.execute("UPDATE chart_entries SET song_id = ? WHERE rowid = ?", (generated_id, entry['rowid']))
                errors += 1
                continue

            # Check for Hash Collision (Different norm text -> Same ID) - Impossible with SHA256 unless collision
            # But we check if the ID exists in cache but maps to different norm text
            if generated_id in songs_cache:
                existing_title, existing_artist = songs_cache[generated_id]
                if existing_title != norm_title or existing_artist != norm_artist:
                    # This might be a false positive if variants are different but normalized text is same?
                    # No, normalize_text strips variants. So if norm text is different, it's a real collision.
                    print(f"CRITICAL ERROR: Hash Collision! ID {generated_id}")
                    print(f"  Existing: {existing_title} | {existing_artist}")
                    print(f"  New:      {norm_title} | {norm_artist}")
                    errors += 1
                    continue
            else:
                # New song (or not in cache yet), insert it
                try:
                    # Extract variant info
                    variant_title = common.extract_variant_info(raw_title)
                    variant_artist = common.extract_variant_info(raw_artist)
                    variants = []
                    if variant_title: variants.append(variant_title)
                    if variant_artist: variants.append(variant_artist)
                    variant_info = " ".join(variants) if variants else None

                    conn.execute("""
                        INSERT INTO songs (song_id, norm_title, norm_artist, variant_info)
                        VALUES (?, ?, ?, ?)
                    """, (generated_id, norm_title, norm_artist, variant_info))
                    songs_cache[generated_id] = (norm_title, norm_artist)
                    updates += 1
                except Exception as e:
                    print(f"Error inserting song {generated_id}: {e}")
                    errors += 1

    print(f"Normalization complete. New songs: {updates}, Errors: {errors}")

if __name__ == "__main__":
    normalize_and_populate()
