import common
import argparse
import csv
from ytmusicapi import YTMusic
import time
import random

# Mock metadata source if no API available
def get_metadata_duration(artist, title):
    # TODO: Connect to Spotify/Last.fm API for real duration
    # For now, return None to signal we can't do duration checks yet
    # Or return a dummy value for testing?
    return None 

import re

def parse_duration(duration_str):
    """
    Converts 'MM:SS', 'H:MM:SS', or ISO 8601 'PT#M#S' to seconds.
    """
    if not duration_str:
        return 0
    
    # Handle ISO 8601 (e.g., PT3M45S)
    if duration_str.startswith('PT'):
        match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            s = int(match.group(3) or 0)
            return h * 3600 + m * 60 + s
        return 0

    try:
        parts = list(map(int, duration_str.split(':')))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0
    except:
        return 0

def calculate_confidence(yt_result, meta_duration=None, variant_info=None):
    score = 0.0
    
    title = yt_result.get('title', '').lower()
    variant_info = variant_info.lower() if variant_info else ""
    
    # 1. Duration Score (if we have metadata)
    if meta_duration:
        # ytmusicapi returns duration like "3:45"
        yt_dur_str = yt_result.get('duration', '')
        yt_dur = parse_duration(yt_dur_str)
        
        if yt_dur > 0:
            delta = abs(yt_dur - meta_duration)
            
            # The Duration Trap: If > 30s off, skip it (severe penalty)
            if delta > 30:
                score -= 0.5 # Immediate fail territory
            else:
                dur_score = max(0, 1 - (delta / meta_duration))
                score += dur_score * 0.5 # Weight 50%
    else:
        # If no metadata, we can't score on duration. 
        # Maybe rely on title match?
        score += 0.5 # Base score?
        
    # 2. Keyword Penalty / Variant Check
    penalty = 0
    keywords = ["live", "remix", "cover", "karaoke", "instrumental"]
    
    for kw in keywords:
        if kw in title:
            # If the keyword is in the variant_info, it's NOT a penalty (it's a match!)
            if kw in variant_info:
                score += 0.1 # Bonus for matching variant type
            else:
                penalty += 0.2
    
    score -= penalty
    
    # 3. Uploader Bonus
    # ytmusicapi results usually have 'resultType': 'song' or 'video'
    result_type = yt_result.get('resultType')
    
    # Check artists/authors for "Topic" or high quality signals
    is_topic = False
    artists = yt_result.get('artists', [])
    for artist in artists:
        if 'name' in artist and 'Topic' in artist['name']:
            is_topic = True
            break
            
    if result_type == 'song':
        score += 0.2
        if is_topic:
            score += 0.2 # Strong signal: Official Song + Topic Channel = High Confidence
    elif result_type == 'video':
        # Penalize videos unless they are clearly official/Topic
        # Check 'author' field for videos
        author = yt_result.get('author', '')
        if 'Topic' in author or 'VEVO' in author.upper():
            score += 0.1
        else:
            score -= 0.1 # Likely a user upload with intro/outro
    
    # Cap at 1.0
    return min(1.0, max(0.0, score))

def verify_songs(dry_run=True, limit=10):
    conn = common.get_db_connection()
    cursor = conn.cursor()
    
    # Init YTMusic (headers_auth usually needed for library operations, but search might work anonymously or requires setup)
    # The user might need to run `ytmusicapi oauth` first. 
    # For now we assume basic search works or user provides headers.
    try:
        yt = YTMusic() 
    except:
        print("Warning: YTMusic not initialized with auth. Search might be limited.")
        yt = YTMusic() # Attempt anonymous

    # Select unsynced songs
    cursor.execute("SELECT song_id, norm_title, norm_artist, variant_info FROM songs WHERE sync_status = 'unsynced' LIMIT ?", (limit,))
    songs = cursor.fetchall()
    
    results = []
    
    print(f"Verifying {len(songs)} songs...")
    
    for song in songs:
        variant = song['variant_info'] if song['variant_info'] else ""
        query = f"{song['norm_title']} {variant} {song['norm_artist']}".strip()
        print(f"Searching: {query}")
        
        try:
            search_results = yt.search(query, filter="songs", limit=3)
            
            best_match = None
            best_score = -1.0
            
            meta_duration = get_metadata_duration(song['norm_artist'], song['norm_title'])
            
            for res in search_results:
                score = calculate_confidence(res, meta_duration, variant_info=variant)
                if score > best_score:
                    best_match = res
                    best_score = score
            
            if best_match:
                video_id = best_match['videoId']
                title = best_match['title']
                print(f"  Found: {title} (Score: {best_score:.2f})")
                
                results.append({
                    'song_id': song['song_id'],
                    'norm_title': song['norm_title'],
                    'norm_artist': song['norm_artist'],
                    'yt_video_id': video_id,
                    'yt_title': title,
                    'score': best_score
                })
                
                if not dry_run:
                    conn.execute("""
                        UPDATE songs 
                        SET yt_video_id = ?, confidence_score = ?, sync_status = 'dry_run_passed'
                        WHERE song_id = ?
                    """, (video_id, best_score, song['song_id']))
                    conn.commit()
            else:
                print("  No results found.")
            
            time.sleep(random.uniform(0.5, 1.5)) # Rate limit niceness
            
        except Exception as e:
            print(f"Error searching {query}: {e}")

    if dry_run:
        csv_file = "verification_dry_run.csv"
        print(f"Dry run complete. Writing to {csv_file}...")
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['song_id', 'norm_title', 'norm_artist', 'yt_video_id', 'yt_title', 'score'])
            writer.writeheader()
            writer.writerows(results)
    else:
        # Also write failures to a CSV for manual review
        failures = [r for r in results if r['score'] < 0.5]
        if failures:
            fail_csv = "verification_failures.csv"
            print(f"Writing {len(failures)} low-confidence results to {fail_csv}...")
            with open(fail_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['song_id', 'norm_title', 'norm_artist', 'yt_video_id', 'yt_title', 'score'])
                writer.writeheader()
                writer.writerows(failures)
        
        print("Verification complete. DB updated.")

    # 4. The Monoculture Stats (Requested by User)
    print("\n--- Phase 2 Stats: The Monoculture ---")
    conn = common.get_db_connection() # Re-connect just in case
    cursor = conn.cursor()
    cursor.execute("""
        SELECT norm_artist, COUNT(*) as song_count, SUM(weeks_top_100) as total_weeks 
        FROM songs 
        GROUP BY norm_artist 
        ORDER BY total_weeks DESC 
        LIMIT 10
    """)
    stats = cursor.fetchall()
    print(f"{'Artist':<30} | {'Songs':<5} | {'Weeks':<5}")
    print("-" * 46)
    for row in stats:
        print(f"{row['norm_artist']:<30} | {row['song_count']:<5} | {row['total_weeks']:<5}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB, write CSV")
    parser.add_argument("--limit", type=int, default=10, help="Number of songs to process")
    args = parser.parse_args()
    
    verify_songs(dry_run=args.dry_run, limit=args.limit)
