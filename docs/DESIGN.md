# DESIGN.md: UX/UI Refinement Strategy

## 1. Visual Identity & Brand
**Objective:** Move away from "Default Dark Mode" to a "Premium Archival" aesthetic.

*   **Color Palette:** Stop using default `Viridis`. Implement a custom color scale that mirrors 2010s aesthetics—neon accents (Electric Blue, Synthwave Pink) against a Deep Charcoal (`#0E1117`) background.
*   **Typography:** Use a high-contrast sans-serif for headers (e.g., `Inter` or `Roboto`) to provide a clean, "Newspaper" feel.
*   **Card-Based UI:** Wrap every chart and KPI in a visual container with a subtle border (`1px solid #30363d`) and a slight drop shadow. This creates a "Bento Box" layout that defines boundaries between different data types.

## 2. The "Bento Box" Layout (Grid System)
**Objective:** Reduce vertical scrolling by grouping related metrics.

*   **The Top Bar:** Use `st.columns` to create a thin "Ticker" at the top for KPIs (Total Songs, Total #1s, Total Years).
*   **The Hero Section (Left 2/3):** The Scatter Plot remains the hero, but with a **"Gold Zone"** overlay—a semi-transparent rectangle highlighting songs that stayed >40 weeks.
*   **The Context Sidebar (Right 1/3):** Instead of a full-width table, show a "Top 5 This Era" list with mini-icons.

## 3. Interactive Discovery (The "Search & Drill-Down")
**Objective:** Move from static viewing to active exploration.

*   **The Global Era Filter:** Add a "Year Slider" to the sidebar. As the user slides from 2013 to 2017, the Area Chart should zoom and the Scatter Plot should highlight songs from that specific year.
*   **Song Drill-Down (The "Deep Dive"):** Implement a "Select a Song" dropdown with autocomplete (filtering by `norm_title` or `norm_artist`). When a song is selected:
    *   Show a custom "Song Card" with the title, artist, and a **Sparkline** of its rank over time (requires joining `chart_entries`).
    *   Display a "YTM Verification Badge" showing the match confidence score from `04_yt_verify.py`.
*   **The "One-Hit Wonder" Toggle:** A checkbox to filter the scatter plot for songs that hit the Top 10 but had < 10 total weeks on the chart.

## 4. Enhancing Data Visualization (Plotly Refinement)
**Objective:** Make the charts more "intuitive" at a glance.

*   **The Area Chart (Annotated):** Add vertical dashed lines with annotations for "Cultural Milestones" (e.g., "The Despacito Summer," "Drake's Scorpion Drop"). This explains *why* the market share shifts.
*   **The Scatter Plot (Legendary Markers):** Change marker shapes based on peak rank. 
    *   `Star` = #1 Hits
    *   `Circle` = Top 10
    *   `Cross` = The Rest
*   **Tooltips:** Custom HTML tooltips that show the `variant_info` and the `first_chart_date`.

## 5. Implementation Tactics (Streamlit Terms)

| Feature | Streamlit Component | Frontend Impact |
| :--- | :--- | :--- |
| **KPI Ticker** | `st.columns` + `st.metric` | Immediate high-level context. |
| **The Bento Layout** | `st.container(border=True)` | Modern, professional structure. |
| **Search/Filter** | `st.selectbox` with `index=None` | Encourages user exploration. |
| **Rank History** | `st.line_chart` (Miniature) | Visualizes "climb" vs "decay" velocity. |
| **Status Feedback** | `st.status` | Shows the current state of the YTM Sync. |

---

## 6. The "Intuitive" Checklist
- [ ] **Can I see who dominated 2015 specifically in 2 seconds?** (Requires Year Filter).
- [ ] **Can I tell if a song is a 'Creeper' or a 'Rocket'?** (Requires Rank Sparkline).
- [ ] **Is the 'Recurrent Rule' visible?** (Requires a vertical line on the Histogram at week 20).
- [ ] **Does it look good on a 4K monitor?** (Requires `layout="wide"` and responsive containers).

---

### Why this works:
You are moving from **reporting** (what happened) to **analysis** (why it happened). By adding era-specific annotations and song-level sparklines, you turn a database into a storytelling engine. 

**Next Step:** Don't try to do all of this at once. Start with the **Bento Box containers** and the **Year Slider**. Those two changes alone will make the dashboard feel like a finished product.