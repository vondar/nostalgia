# Billboard Reconstruction Dashboard: Streamlit Edition

## Overview
This dashboard transforms the `billboard.db` SQLite archive into a visual analysis of cultural saturation. By using Streamlit, we maintain a unified Python environment and leverage Polars for high-performance data manipulation.

## Tech Stack
- **Framework:** [Streamlit](https://streamlit.io/)
- **Data Engine:** [Polars](https://pola.rs/) (for the heavy lifting)
- **Visualization:** [Plotly Express](https://plotly.com/python/plotly-express/) (interactive charts)
- **Backend:** SQLite

---

## Structure
Unlike Evidence, Streamlit is script-based. We will use a single main file with cached data functions.

```text
project/
├── data/billboard.db
├── dashboard.py         # Main entry point
└── pages/               # Optional: Streamlit auto-detects multi-page apps here
    ├── 01_Artist_Deep_Dive.py
    └── 02_Data_Quality.py
```

---

## Core Analytical Logic (Inside `dashboard.py`)

### 1. Persistence vs. Peak (The Scatter Plot)
We use the `songs` table to find the relationship between how high a song peaked and how long it stayed on the chart. 

### 2. Market Share Monopoly (The Stacked Area Chart)
This identifies the "Colonization" effect. We identify the Top 10 artists of the entire era and group everyone else into "Other" to see who owned the chart real estate month-over-month.

---

## The Dashboard Code

```python
import streamlit as st
import sqlite3
import polars as pl
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="Billboard 2013-2017 Archive", layout="wide")

# Dark mode styling for that "Internal Tool" aesthetic
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADING (CACHED) ---
@st.cache_data
def get_dashboard_data():
    conn = sqlite3.connect("data/billboard.db")
    
    # 1. Main Song Registry
    songs = pl.read_database("SELECT * FROM songs", conn)
    
    # 2. Market Share Logic (Top 10 Artists vs Other)
    market_query = """
    WITH top_artists AS (
        SELECT artist FROM chart_entries 
        GROUP BY artist ORDER BY COUNT(*) DESC LIMIT 10
    )
    SELECT 
        c.chart_date,
        CASE WHEN t.artist IS NOT NULL THEN c.artist ELSE 'Other' END as artist_group,
        COUNT(*) as slot_count
    FROM chart_entries c
    LEFT JOIN top_artists t ON c.artist = t.artist
    GROUP BY 1, 2
    """
    market_share = pl.read_database(market_query, conn)
    
    # 3. Stats for KPIs
    total_entries = conn.execute("SELECT COUNT(*) FROM chart_entries").fetchone()[0]
    
    conn.close()
    return songs, market_share, total_entries

songs, market_share, total_entries = get_dashboard_data()

# --- HEADER ---
st.title("🏛️ Billboard Cultural Ingestion (2013-2017)")
st.markdown("---")

# --- KPIs ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Unique Songs Indexed", f"{len(songs):,}")
col2.metric("Chart Appearances", f"{total_entries:,}")
col3.metric("Avg Weeks on Chart", f"{songs['weeks_top_100'].mean():.1f}")
col4.metric("Total #1 Hits", f"{len(songs.filter(pl.col('peak_rank') == 1)):,}")

st.markdown("---")

# --- ROW 1: THE PERSISTENCE PLOT ---
st.header("The Longevity Outliers")
st.write("Does peak rank correlate with survival? Not always. Look for the 'Staples' in the top-left.")

fig_persistence = px.scatter(
    songs.to_pandas(),
    x="peak_rank",
    y="weeks_top_100",
    color="weeks_top_10",
    size="weeks_top_100",
    hover_name="title",
    hover_data=["artist", "peak_rank", "weeks_top_100"],
    color_continuous_scale="Viridis",
    labels={"peak_rank": "Peak Rank (1 is best)", "weeks_top_100": "Total Weeks in Top 100"}
)
fig_persistence.update_xaxes(autorange="reversed") # Reverse so #1 is on the right
fig_persistence.update_layout(height=600, template="plotly_dark")
st.plotly_chart(fig_persistence, use_container_width=True)

# --- ROW 2: MARKET SHARE ---
st.header("Artist Dominance Over Time")
st.write("Visualizing the colonization of the Hot 100 by the Top 10 Artists.")

fig_market = px.area(
    market_share.sort("chart_date").to_pandas(),
    x="chart_date",
    y="slot_count",
    color="artist_group",
    line_group="artist_group",
    title="Market Share: Top 10 Artists vs. The Field",
    template="plotly_dark"
)
fig_market.update_layout(height=500)
st.plotly_chart(fig_market, use_container_width=True)

# --- ROW 3: SURVIVAL & LEADERBOARD ---
c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("The Survival Rate (The Dead Zone)")
    fig_hist = px.histogram(
        songs.to_pandas(), 
        x="weeks_top_100", 
        nbins=40,
        title="Distribution of Song Longevity",
        template="plotly_dark"
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with c2:
    st.subheader("The Top 10 Elite")
    top_10_table = (
        songs.sort("weeks_top_10", descending=True)
        .select(["title", "artist", "weeks_top_10", "peak_rank"])
        .head(15)
    )
    st.table(top_10_table.to_pandas())
```

---

## Implementation Instructions

1.  **Install Dependencies:**
    ```bash
    pip install streamlit polars plotly
    ```
2.  **Run the App:**
    ```bash
    streamlit run dashboard.py
    ```
3.  **The "Flex" - Adding a Search Bar:**
    Since you have the `songs` DataFrame, you can add a simple sidebar search:
    ```python
    search_query = st.sidebar.text_input("Search for a Song or Artist")
    if search_query:
        search_results = songs.filter(
            pl.col("title").str.contains(search_query.lower()) | 
            pl.col("artist").str.contains(search_query.lower())
        )
        st.sidebar.dataframe(search_results.select(["title", "artist", "peak_rank"]))
    ```