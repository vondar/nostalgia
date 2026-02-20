import streamlit as st
import sqlite3
import polars as pl
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIG ---
st.set_page_config(page_title="Billboard 2013-2017 Archive", layout="wide")

# --- CUSTOM CSS (THEME) ---
st.markdown("""
    <style>
    /* Global Background */
    .stApp {
        background-color: #0e1117;
    }
    
    /* Card/Container Styling */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: bold;
        color: #e6e6e6;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #161b22;
    }
    
    /* Custom Card for Song Detail */
    .song-card {
        background-color: #1f242d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        margin-bottom: 20px;
    }
    .song-title {
        font-size: 22px;
        font-weight: bold;
        color: #58a6ff;
        margin-bottom: 5px;
    }
    .song-artist {
        font-size: 16px;
        color: #8b949e;
        margin-bottom: 15px;
    }
    .stat-row {
        display: flex;
        justify_content: space-between;
        margin-top: 10px;
        font-size: 14px;
        color: #c9d1d9;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATA LOADING ---
@st.cache_data
def get_dashboard_data():
    conn = sqlite3.connect("billboard.db")
    
    # 1. Main Song Registry
    # Using schema_overrides to ensure robustness against NULLs in variant_info
    songs = pl.read_database(
        "SELECT * FROM songs", 
        conn,
        schema_overrides={"variant_info": pl.String, "confidence_score": pl.Float64}
    )
    
    # Ensure first_chart_date is date type
    songs = songs.with_columns(pl.col("first_chart_date").str.to_date())

    # 2. Market Share Logic
    market_query = """
    WITH normalized_entries AS (
        SELECT c.chart_date, s.norm_artist 
        FROM chart_entries c
        JOIN songs s ON c.song_id = s.song_id
    ),
    top_artists AS (
        SELECT norm_artist FROM normalized_entries
        GROUP BY norm_artist ORDER BY COUNT(*) DESC LIMIT 10
    )
    SELECT 
        n.chart_date,
        CASE WHEN t.norm_artist IS NOT NULL THEN n.norm_artist ELSE 'Other' END as artist_group,
        COUNT(*) as slot_count
    FROM normalized_entries n
    LEFT JOIN top_artists t ON n.norm_artist = t.norm_artist
    GROUP BY 1, 2
    """
    market_share = pl.read_database(market_query, conn)
    
    # 3. KPI Stats
    total_entries = conn.execute("SELECT COUNT(*) FROM chart_entries").fetchone()[0]
    
    conn.close()
    return songs, market_share, total_entries

@st.cache_data
def get_song_history(song_id):
    """Fetch rank history for a specific song for the Sparkline."""
    conn = sqlite3.connect("billboard.db")
    query = """
        SELECT chart_date, rank 
        FROM chart_entries 
        WHERE song_id = ? 
        ORDER BY chart_date ASC
    """
    history = pl.read_database(query, conn, execute_options={"parameters": [song_id]})
    conn.close()
    return history

songs, market_share, total_entries = get_dashboard_data()

# --- SIDEBAR CONTROLS ---
st.sidebar.title("🎛️ Archive Controls")

# Year Slider
min_year = 2013
max_year = 2017
selected_years = st.sidebar.slider(
    "Filter by Year Range",
    min_year, max_year, (min_year, max_year)
)

# Filter Data based on Slider
# Logic: Keep songs that charted AT ALL within the selected range?
# Or just filter the Scatter Plot? Let's filter the songs shown.
# We'll assume a song is "in" the range if its first_chart_date year is within the range.
filtered_songs = songs.filter(
    (pl.col("first_chart_date").dt.year() >= selected_years[0]) &
    (pl.col("first_chart_date").dt.year() <= selected_years[1])
)

# Song Drill-Down Search
st.sidebar.markdown("---")
st.sidebar.subheader("Song Drill-Down")

# Create a display label for the dropdown
songs_list = filtered_songs.select(["song_id", "norm_title", "norm_artist"]).to_dicts()
song_options = {f"{s['norm_title']} - {s['norm_artist']}": s['song_id'] for s in songs_list}

selected_song_label = st.sidebar.selectbox(
    "Select a Song to Inspect",
    options=["None"] + list(song_options.keys()),
    index=0
)

selected_song_id = None
if selected_song_label != "None":
    selected_song_id = song_options[selected_song_label]

# --- MAIN LAYOUT ---
st.title("🏛️ Billboard Cultural Ingestion")
st.markdown("---")

# 1. KPI TICKER (Bento Row 1)
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Songs", f"{len(filtered_songs):,}")
    c2.metric("Total Chart Entries", f"{total_entries:,}") # This is global, maybe filter? keeping simple
    c3.metric("Avg Weeks on Chart", f"{filtered_songs['weeks_top_100'].mean():.1f}")
    c4.metric("#1 Hits in Range", f"{len(filtered_songs.filter(pl.col('peak_rank') == 1)):,}")

# 2. HERO SECTION (Scatter + Detail)
col_hero, col_detail = st.columns([2, 1])

with col_hero:
    with st.container(border=True):
        st.subheader("The Longevity Landscape")
        
        # Color Logic: Highlight #1s or just use longevity?
        # Let's use a custom color scale: Gold for #1s, Blue for others?
        # Or keep the Viridis for consistency but add the shape logic.
        
        fig_persistence = px.scatter(
            filtered_songs.to_pandas(),
            x="peak_rank",
            y="weeks_top_100",
            color="weeks_top_10",
            size="weeks_top_100",
            hover_name="norm_title",
            hover_data=["norm_artist", "peak_rank", "weeks_top_100"],
            color_continuous_scale="Viridis",
            title=f"Song Persistence ({selected_years[0]}-{selected_years[1]})",
        )
        
        # Add "Gold Zone" annotation (Weeks > 40)
        fig_persistence.add_hrect(
            y0=40, y1=90, 
            line_width=0, fillcolor="gold", opacity=0.1,
            annotation_text="The Gold Zone (>40 Weeks)", 
            annotation_position="top right"
        )
        
        fig_persistence.update_xaxes(autorange="reversed", title="Peak Rank (1 is best)")
        fig_persistence.update_yaxes(title="Total Weeks on Chart")
        fig_persistence.update_layout(height=500, template="plotly_dark")
        
        st.plotly_chart(fig_persistence, use_container_width=True)

with col_detail:
    if selected_song_id:
        # Fetch song details
        song_data = songs.filter(pl.col("song_id") == selected_song_id).row(0, named=True)
        
        # Render Custom Card HTML
        st.markdown(f"""
            <div class="song-card">
                <div class="song-title">{song_data['norm_title']}</div>
                <div class="song-artist">{song_data['norm_artist']}</div>
                <div class="stat-row">
                    <span>Peak Rank: <strong>#{song_data['peak_rank']}</strong></span>
                    <span>Weeks on Chart: <strong>{song_data['weeks_top_100']}</strong></span>
                </div>
                <div class="stat-row">
                    <span>First Entry: {song_data['first_chart_date']}</span>
                    <span>Top 10 Weeks: {song_data['weeks_top_10']}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Sparkline (Rank History)
        st.markdown("**Chart Run History**")
        history_df = get_song_history(selected_song_id)
        
        # Invert rank for visual (1 is high)
        fig_spark = px.line(
            history_df.to_pandas(), 
            x="chart_date", 
            y="rank", 
            title=None
        )
        fig_spark.update_yaxes(autorange="reversed", title="Rank")
        fig_spark.update_xaxes(showgrid=False, title=None)
        fig_spark.update_layout(
            height=200, 
            margin=dict(l=20, r=20, t=20, b=20),
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_spark, use_container_width=True)
        
        # YTM Verification Badge
        confidence = song_data.get('confidence_score')
        if confidence:
            badge_color = "green" if confidence > 0.8 else "orange"
            st.markdown(f"**YTM Match Confidence:** :{badge_color}[{confidence:.2f}]")
            
    else:
        # Default State: Top 5 List for the selected era
        with st.container(border=True):
            st.subheader(f"Top 5 Hits ({selected_years[0]}-{selected_years[1]})")
            top_5 = (
                filtered_songs.sort("weeks_top_10", descending=True)
                .head(5)
                .select(["norm_title", "norm_artist", "weeks_top_10"])
            )
            for row in top_5.iter_rows(named=True):
                st.markdown(f"""
                **{row['norm_title']}**  
                <span style='color: #8b949e; font-size: 0.9em;'>{row['norm_artist']} • {row['weeks_top_10']} wks in Top 10</span>
                <hr style='margin: 5px 0; border-color: #30363d;'>
                """, unsafe_allow_html=True)

# 3. MARKET SHARE (Bento Row 2)
with st.container(border=True):
    st.subheader("Market Share Analysis")
    
    # Filter market share by date range?
    # market_share has 'chart_date' string "YYYY-MM-DD"
    # Convert to date for filtering
    ms_filtered = market_share.with_columns(pl.col("chart_date").str.to_date())
    ms_filtered = ms_filtered.filter(
        (pl.col("chart_date").dt.year() >= selected_years[0]) &
        (pl.col("chart_date").dt.year() <= selected_years[1])
    )
    
    fig_market = px.area(
        ms_filtered.sort("chart_date").to_pandas(),
        x="chart_date",
        y="slot_count",
        color="artist_group",
        line_group="artist_group",
        title=None,
        template="plotly_dark"
    )
    fig_market.update_layout(height=400, margin=dict(t=20))
    st.plotly_chart(fig_market, use_container_width=True)
