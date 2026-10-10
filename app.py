
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st


# ----------------------------
# Page configuration
# ----------------------------
st.set_page_config(
    page_title="Industrial Project Lead Intelligence",
    page_icon="🏭",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "leads.db"

LEAD_STATUSES = [
    "New",
    "Reviewing",
    "Contacted",
    "Qualified",
    "Won",
    "Ignored",
]


def ensure_database():
    """Create and populate the database on a fresh Streamlit deployment."""
    from database import initialize_database

    if DB_PATH.exists():
        initialize_database()
        return

    from lead_classifier import classify_articles
    from news_collector import collect_news

    with st.spinner("Collecting the latest industrial project news for the first load..."):
        initialize_database()
        collect_news()
        classify_articles()


# ----------------------------
# Load data
# ----------------------------
@st.cache_data(ttl=60)
def load_articles():
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query(
            """
            SELECT
                a.id,
                a.title,
                a.published,
                a.source,
                a.url,
                a.industry,
                a.geography,
                COALESCE(l.lead_score, 0) AS lead_score,
                COALESCE(l.lead_priority, 'Unclassified')
                    AS lead_priority,
                COALESCE(l.reason, 'Not classified') AS reason,
                COALESCE(a2.status, 'New') AS status,
                COALESCE(a2.notes, '') AS notes,
                a2.follow_up_date
            FROM articles AS a
            LEFT JOIN lead_classification AS l
                ON a.id = l.article_id
            LEFT JOIN lead_actions AS a2
                ON a.id = a2.article_id
            ORDER BY lead_score DESC, a.published DESC
            """,
            connection,
        )


# ----------------------------
# Dashboard header
# ----------------------------
st.title("🏭 Industrial Project Lead Intelligence")
st.caption(
    "Discover and review industrial project announcements "
    "for conveyor and material-handling sales opportunities."
)

ensure_database()

df = load_articles()

if df.empty:
    st.info("No articles found. Run the news collector first.")
    st.stop()


# ----------------------------
# Sidebar filters
# ----------------------------
st.sidebar.header("Filters")

from datetime import date, timedelta

# Recent publication window
date_filter = st.sidebar.selectbox(
    "Publication period",
    [
        "All dates",
        "Last 7 days",
        "Last 30 days",
        "Last 90 days",
    ],
    index=1,
)


industries = sorted(
    df["industry"].dropna().astype(str).unique().tolist()
)
priorities = [
    "High Potential",
    "Potential",
    "Monitor",
    "Review / Exclude",
    "Unclassified",
]
available_priorities = [
    p for p in priorities if p in df["lead_priority"].values
]

selected_industries = st.sidebar.multiselect(
    "Industry",
    options=industries,
    default=industries,
)

selected_priorities = st.sidebar.multiselect(
    "Lead priority",
    options=available_priorities,
    default=available_priorities,
)

geographies = sorted(
    df["geography"].dropna().astype(str).unique().tolist()
)
selected_geographies = st.sidebar.multiselect(
    "Geography",
    options=geographies,
    default=geographies,
)

search_text = st.sidebar.text_input(
    "Search titles or reasons"
)


# Publication date filter
df["published_date"] = pd.to_datetime(
    df["published"], errors="coerce", utc=True
).dt.date

valid_dates = df["published_date"].dropna()

if not valid_dates.empty:
    earliest_date = valid_dates.min()
    latest_date = valid_dates.max()

    date_range = st.sidebar.date_input(
        "Publication date range",
        value=(max(earliest_date, latest_date.replace(
            year=latest_date.year - 1
        )), latest_date),
        min_value=earliest_date,
        max_value=latest_date,
    )
else:
    date_range = None


minimum_score = st.sidebar.slider(
    "Minimum lead score",
    min_value=0,
    max_value=100,
    value=0,
)

st.sidebar.divider()
st.sidebar.header("Lead follow-up")

lead_options = {
    f"{row.title[:80]} — {row.status}": int(row.id)
    for row in df.itertuples()
}

if lead_options:
    selected_label = st.sidebar.selectbox(
        "Select a lead",
        options=list(lead_options),
    )
    selected_id = lead_options[selected_label]
    selected_row = df.loc[df["id"] == selected_id].iloc[0]

    selected_status = st.sidebar.selectbox(
        "Status",
        LEAD_STATUSES,
        index=(
            LEAD_STATUSES.index(selected_row["status"])
            if selected_row["status"] in LEAD_STATUSES
            else 0
        ),
    )
    selected_notes = st.sidebar.text_area(
        "Notes",
        value=selected_row["notes"],
        height=100,
    )
    selected_follow_up = st.sidebar.date_input(
        "Follow-up date",
        value=(
            pd.to_datetime(selected_row["follow_up_date"]).date()
            if pd.notna(selected_row["follow_up_date"])
            else None
        ),
    )

    if st.sidebar.button("Save lead update", type="primary"):
        with sqlite3.connect(DB_PATH) as connection:
            connection.execute(
                """
                INSERT INTO lead_actions
                    (article_id, status, notes, follow_up_date, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(article_id) DO UPDATE SET
                    status = excluded.status,
                    notes = excluded.notes,
                    follow_up_date = excluded.follow_up_date,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    selected_id,
                    selected_status,
                    selected_notes,
                    selected_follow_up.isoformat()
                    if selected_follow_up
                    else None,
                ),
            )
        st.cache_data.clear()
        st.sidebar.success("Lead update saved.")


# ----------------------------
# Apply filters
# ----------------------------
filtered = df[
    df["industry"].isin(selected_industries)
    & df["lead_priority"].isin(selected_priorities)
    & df["geography"].isin(selected_geographies)
    & (df["lead_score"] >= minimum_score)
    & df["published_date"].between(
    date_range[0], date_range[1]
)
].copy()


# Filter by actual publication date, not collection date
filtered["published_date"] = pd.to_datetime(
    filtered["published"],
    errors="coerce",
    utc=True,
).dt.date

today = date.today()

if date_filter == "Last 7 days":
    cutoff = today - timedelta(days=7)
    filtered = filtered[
        filtered["published_date"].between(cutoff, today)
    ]
elif date_filter == "Last 30 days":
    cutoff = today - timedelta(days=30)
    filtered = filtered[
        filtered["published_date"].between(cutoff, today)
    ]
elif date_filter == "Last 90 days":
    cutoff = today - timedelta(days=90)
    filtered = filtered[
        filtered["published_date"].between(cutoff, today)
    ]

if search_text.strip():
    search_mask = (
        filtered["title"].fillna("").str.contains(
            search_text, case=False, regex=False
        )
        | filtered["reason"].fillna("").str.contains(
            search_text, case=False, regex=False
        )
    )
    filtered = filtered[search_mask]


# ----------------------------
# KPI metrics
# ----------------------------
total_articles = len(filtered)
high_potential = (
    filtered["lead_priority"] == "High Potential"
).sum()
potential = (
    filtered["lead_priority"] == "Potential"
).sum()
average_score = (
    round(filtered["lead_score"].mean(), 1)
    if total_articles
    else 0
)
active_follow_ups = (filtered["status"].isin(["Contacted", "Qualified"])).sum()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Articles", total_articles)
col2.metric("High Potential", int(high_potential))
col3.metric("Potential", int(potential))
col4.metric("Average Score", average_score)
col5.metric("Active Follow-ups", int(active_follow_ups))


# ----------------------------
# Charts
# ----------------------------
st.subheader("Lead Overview")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("**Articles by priority**")
    if total_articles:
        priority_counts = (
            filtered["lead_priority"]
            .value_counts()
            .rename_axis("Priority")
            .reset_index(name="Articles")
        )
        st.bar_chart(
            priority_counts,
            x="Priority",
            y="Articles",
        )
    else:
        st.info("No articles match these filters.")

with chart_col2:
    st.markdown("**Articles by industry**")
    if total_articles:
        industry_counts = (
            filtered["industry"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("Industry")
            .reset_index(name="Articles")
        )
        st.bar_chart(
            industry_counts,
            x="Industry",
            y="Articles",
        )
    else:
        st.info("No articles match these filters.")


# ----------------------------
# Article table
# ----------------------------
st.subheader("Industrial News & Potential Leads")
st.caption(
    "Scores are preliminary keyword-based indicators. "
    "Verify each announcement before treating it as a sales lead."
)

if filtered.empty:
    st.warning("No articles match your current filters.")
else:
    display_df = filtered[
        [
            "title",
            "industry",
            "geography",
            "source",
            "published",
            "lead_score",
            "lead_priority",
            "status",
            "follow_up_date",
            "reason",
            "url",
        ]
    ].copy()

    display_df = display_df.rename(
        columns={
            "title": "Article",
            "industry": "Industry",
            "geography": "Geography",
            "source": "Source",
            "published": "Published",
            "lead_score": "Score",
            "lead_priority": "Priority",
            "status": "Status",
            "follow_up_date": "Follow-up",
            "reason": "Scoring explanation",
            "url": "Article Link",
        }
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Article Link": st.column_config.LinkColumn(
                "Open Source",
                display_text="Read article",
            ),
            "Score": st.column_config.NumberColumn(
                "Score",
                format="%d",
            ),
        },
    )

st.caption(f"Database: {DB_PATH}")

