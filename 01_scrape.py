import requests
from bs4 import BeautifulSoup
import hashlib
import time
import random
import re
from datetime import datetime, timedelta
import common

# Billboard Hot 100 URL pattern
BASE_URL = "https://www.billboard.com/charts/hot-100/{date}/"

# Date range: 2013-01-05 to 2017-12-30 (Saturdays usually)
START_DATE = datetime(2013, 1, 5)
END_DATE = datetime(2017, 12, 30)

def generate_html_hash(html_content):
    return hashlib.sha256(html_content.encode('utf-8')).hexdigest()

def fetch_with_retry(url, retries=3):
    """
    Fetches URL with exponential backoff and jitter.
    """
    for i in range(retries):
        try:
            # Random jitter between 1 and 3 seconds (plus exponential backoff)
            sleep_time = random.uniform(1, 3) + (2 ** i)
            if i > 0:
                print(f"  Retry {i}/{retries} after {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            if i == retries - 1:
                raise
    return None

def scrape_chart(date_str):
    url = BASE_URL.format(date=date_str)
    print(f"Fetching {url}...")
    
    try:
        html_content = fetch_with_retry(url)
        
        current_hash = generate_html_hash(html_content)
        
        conn = common.get_db_connection()
        cursor = conn.cursor()
        
        # Check for existing hash
        cursor.execute("SELECT html_hash FROM scrape_log WHERE chart_date = ?", (date_str,))
        row = cursor.fetchone()
        
        if row and row['html_hash'] == current_hash:
            print(f"Skipping {date_str}: Hash matches (No changes).")
            conn.close()
            return

        print(f"Parsing {date_str}...")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Billboard HTML Structure (as of 2024/2025/Historical)
        # Rows are in div.o-chart-results-list-row-container
        rows = soup.select('div.o-chart-results-list-row-container')
        
        # Canary Check: If primary selector fails, try fallback
        if not rows:
             print(f"  Warning: Primary selector failed for {date_str}. Trying fallback...")
             rows = soup.select("li.chart-list__element")
             
        if len(rows) < 100:
             # If still less than 100, raise critical error to stop pollution
             raise ValueError(f"CRITICAL: Found only {len(rows)} entries for {date_str}. DOM likely changed.")

        entries = []
        for i, row in enumerate(rows):
            try:
                # Title is in h3#title-of-a-story
                title_tag = row.select_one('h3#title-of-a-story')
                if not title_tag:
                    continue
                title = title_tag.text.strip()
                
                # Artist Selector Refinement (Hierarchical)
                # Instead of relying on 'a-no-trucate', look for the span that is a sibling of the h3's parent/container
                # Structure: li > ... > h3 > ... > span.c-label
                # The artist is usually the first span.c-label following the title's container context
                
                # Option 1: h3 + span (immediate sibling) - often there's whitespace or newlines
                # Option 2: select('span.c-label') and filter out badges
                
                # Let's try the hierarchical approach recommended:
                # Find the parent of h3, then look for span.c-label in that context?
                # Actually, in 2013-2017 structure, title and artist are often in a wrapper.
                
                # Using the specific "NEW" bug fix logic but making it more robust:
                # Find all c-labels in the row
                labels = row.select('span.c-label')
                artist_text = ""
                
                for label in labels:
                    text = label.text.strip()
                    # Filter out known badge text
                    # "RE-\nENTRY" is a common issue where text is split
                    clean_text = text.replace('\n', '').strip()
                    
                    if clean_text in ['NEW', 'RE-ENTRY', 'RE-\nENTRY'] or re.match(r'^\d+$', clean_text): # numeric rank
                        continue
                    # If we found a valid-looking string, assume it's the artist
                    if clean_text:
                        artist_text = clean_text
                        break
                
                if not artist_text:
                     # Fallback to the 'a-no-trucate' class if the loop failed
                     fallback_tag = row.select_one('span.c-label.a-no-trucate')
                     if fallback_tag:
                         artist_text = fallback_tag.text.strip()
                
                if not artist_text:
                    print(f"  Warning: Could not find artist tag for {title}")
                    continue
                
                artist = artist_text
                
                # Rank: we can use the loop index + 1
                rank = i + 1
                
                entries.append((title, artist, rank))
            except Exception as e:
                print(f"  Error parsing row {i}: {e}")
        
        if not entries:
            print(f"Warning: No entries found for {date_str}. HTML structure might have changed.")
            # Don't delete existing data if scrape failed completely
            return

        # Deduplicate entries based on generated song_id to avoid UNIQUE constraint errors
        # Keep the highest rank (lowest number) if duplicates exist
        unique_entries = {}
        for title, artist, rank in entries:
            s_id = common.generate_song_id(title, artist)
            if s_id not in unique_entries:
                unique_entries[s_id] = (title, artist, rank)
            else:
                # If we found a duplicate, maybe keep the one with better rank?
                # Usually duplicates are remixes lower down.
                # If existing rank > new rank (meaning new one is better), update.
                if unique_entries[s_id][2] > rank:
                    unique_entries[s_id] = (title, artist, rank)
        
        # Convert back to list
        final_entries = list(unique_entries.values())
        if len(final_entries) < len(entries):
            print(f"  Deduplicated {len(entries) - len(final_entries)} entries for {date_str}.")

        # Atomic Transaction
        with conn:
            # Clear old entries for this date if re-scraping
            conn.execute("DELETE FROM chart_entries WHERE chart_date = ?", (date_str,))
            
            # Insert new entries
            for title, artist, rank in final_entries:
                song_id = common.generate_song_id(title, artist)
                norm_title = common.normalize_text(title)
                norm_artist = common.normalize_text(artist)
                
                # Extract variant info (remix, feat)
                variant_title = common.extract_variant_info(title)
                variant_artist = common.extract_variant_info(artist)
                variants = []
                if variant_title: variants.append(variant_title)
                if variant_artist: variants.append(variant_artist)
                variant_info = " ".join(variants) if variants else None
                
                # Ensure song exists in registry (minimal insert to satisfy FK)
                # Full population happens in Phase 2
                conn.execute("""
                    INSERT OR IGNORE INTO songs (song_id, norm_title, norm_artist, variant_info)
                    VALUES (?, ?, ?, ?)
                """, (song_id, norm_title, norm_artist, variant_info))
                
                conn.execute("""
                    INSERT INTO chart_entries (song_id, chart_date, rank, raw_title, raw_artist)
                    VALUES (?, ?, ?, ?, ?)
                """, (song_id, date_str, rank, title, artist))
            
            # Update scrape_log
            conn.execute("""
                INSERT OR REPLACE INTO scrape_log (chart_date, html_hash, scraped_at)
                VALUES (?, ?, ?)
            """, (date_str, current_hash, datetime.now().isoformat()))
            
        print(f"Successfully scraped {date_str}.")
        
    except Exception as e:
        print(f"Error scraping {date_str}: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

import argparse

def scrape_billboard(start_str, end_str):
    common.init_db()
    
    current_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")
    
    # Force start_date to the next Saturday if it isn't one already (Saturday = 5)
    days_until_saturday = (5 - current_date.weekday() + 7) % 7
    if days_until_saturday != 0:
        current_date += timedelta(days=days_until_saturday)
        print(f"Snapped start_date to next Saturday: {current_date.date()}")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        scrape_chart(date_str)
        current_date += timedelta(days=7)
        # Random sleep between requests to avoid rate limiting
        sleep_time = random.uniform(2, 5)
        time.sleep(sleep_time)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Billboard Hot 100")
    parser.add_argument("--start", type=str, default="2013-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default="2017-12-31", help="End date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    scrape_billboard(args.start, args.end)
