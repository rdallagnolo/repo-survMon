import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from utils.data_loader import (
    load_database_cached,
    load_orca_cached,
    build_sequence_windows,
    split_database_by_day,
)

st.set_page_config(page_title="Daily tracks", page_icon=":whale:", layout="wide")
st.header("Daily track analysis")

DB_FILE = Path("24hrVesselPosition/database.csv")
ORCA_FILE = Path("orca-web.csv")

ONLINE_COLOR = "#0B3D91"
OFFLINE_COLOR = "#CC5500"


# -----------------------------
# Cached loaders
# -----------------------------
@st.cache_data
def get_database():
    return load_database_cached(DB_FILE)


@st.cache_data
def get_daily_map():
    df = get_database()
    return split_database_by_day(df)


@st.cache_data
def get_sequence_windows_cached():
    orca_df = load_orca_cached(ORCA_FILE)
    return build_sequence_windows(orca_df)


# -----------------------------
# Session state
# -----------------------------
for key in [
    "daily_source_df",
    "daily_data",
    "daily_plots",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# -----------------------------
# Helpers
# -----------------------------
def format_hms(hours_float: float) -> str:
    total_seconds = int(round(hours_float * 3600))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def classify_online_offline(df: pd.DataFrame, seq_windows: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Status"] = "Offline"

    for _, row in seq_windows.iterrows():
        mask = (df["DateTime"] >= row["Start"]) & (df["DateTime"] <= row["End"])
        df.loc[mask, "Status"] = "Online"

    return df


def build_colored_track(day_df: pd.DataFrame, seq_windows: pd.DataFrame) -> go.Figure:
    df = classify_online_offline(day_df, seq_windows)
    df = df.sort_values("DateTime").reset_index(drop=True)

    start_dt = df["DateTime"].iloc[0]
    end_dt = df["DateTime"].iloc[-1]

    dx = df["Easting"].diff()
    dy = df["Northing"].diff()
    df["Segment_km"] = np.sqrt(dx**2 + dy**2) / 1000.0
    df["Segment_km"] = df["Segment_km"].fillna(0)

    total_distance = df["Segment_km"].sum()
    total_hours = (end_dt - start_dt).total_seconds() / 3600.0

    online_df = df[df["Status"] == "Online"]
    offline_df = df[df["Status"] == "Offline"]

    online_distance = online_df["Segment_km"].sum()
    offline_distance = offline_df["Segment_km"].sum()

    online_speed = online_df["Bottom Speed"].mean() if not online_df.empty else 0.0
    offline_speed = offline_df["Bottom Speed"].mean() if not offline_df.empty else 0.0

    df["segment"] = (df["Status"] != df["Status"].shift()).cumsum()

    fig = go.Figure()

    colors = {
        "Online": ONLINE_COLOR,
        "Offline": OFFLINE_COLOR,
    }

    shown_legend = set()

    for _, seg_df in df.groupby("segment"):
        status = seg_df["Status"].iloc[0]

        fig.add_trace(
            go.Scattergl(
                x=seg_df["Easting"],
                y=seg_df["Northing"],
                mode="lines",
                line=dict(width=2, color=colors[status]),
                name=status,
                showlegend=status not in shown_legend,
                text=seg_df["Date"].astype(str),
                customdata=np.column_stack([
                    seg_df["Time"].astype(str).to_numpy(),
                    seg_df["Status"].astype(str).to_numpy(),
                ]),
                hovertemplate=(
                    "Date: %{text}<br>"
                    "Time: %{customdata[0]}<br>"
                    "Status: %{customdata[1]}<br>"
                    "Easting: %{x}<br>"
                    "Northing: %{y}<extra></extra>"
                ),
            )
        )
        shown_legend.add(status)

    fig.update_layout(
        title="Daily track - online vs offline",
        template="seaborn",
        width=800,
        height=800,
        xaxis_title="Easting",
        yaxis_title="Northing",
        annotations=[
            dict(
                x=0.02, y=0.98, xref="paper", yref="paper",
                text=f"Total Time frame: {format_hms(total_hours)}",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.94, xref="paper", yref="paper",
                text=f"Total distance travelled: {total_distance:.2f} km",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.90, xref="paper", yref="paper",
                text=f"Distance travelled online: {online_distance:.2f} km",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.86, xref="paper", yref="paper",
                text=f"Average speed online: {online_speed:.2f} knots",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.82, xref="paper", yref="paper",
                text=f"Distance travelled offline: {offline_distance:.2f} km",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.78, xref="paper", yref="paper",
                text=f"Average speed offline: {offline_speed:.2f} knots",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.03, xref="paper", yref="paper",
                text=f"Start: {start_dt}",
                showarrow=False, font=dict(size=14)
            ),
            dict(
                x=0.02, y=0.00, xref="paper", yref="paper",
                text=f"End: {end_dt}",
                showarrow=False, font=dict(size=14)
            ),
        ],
    )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)

    return fig


def build_histogram(df: pd.DataFrame, title: str, color: str, x_min: float, x_max: float, bin_size: float) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Histogram(
                x=df["Bottom Speed"],
                xbins=dict(start=x_min, end=x_max, size=bin_size),
                marker=dict(
                    color=color,
                    line=dict(color="black", width=1),
                ),
                opacity=0.6,
            )
        ]
    )

    fig.update_layout(
        title=title,
        template="seaborn",
        width=800,
        height=390,
        showlegend=False,
        bargap=0.00,
    )
    fig.update_xaxes(title_text="Bottom Speed (knots)")
    fig.update_yaxes(title_text="Frequency")

    return fig


# -----------------------------
# Load data
# -----------------------------
try:
    if st.session_state.daily_source_df is None:
        st.session_state.daily_source_df = get_database()

except Exception as e:
    st.error(f"Error loading database: {e}")
    st.stop()


# -----------------------------
# Build daily tracks
# -----------------------------
if st.sidebar.button("Refresh plots") or st.session_state.daily_data is None:
    try:
        daily_map = get_daily_map()

        daily_data = {
            pd.Timestamp(day).strftime("%Y-%m-%d"): df.reset_index(drop=True)
            for day, df in daily_map.items()
            if len(df) > 1
        }

        st.session_state.daily_data = daily_data
        st.session_state.daily_plots = None

    except Exception as e:
        st.error(f"Error building daily tracks: {e}")
        st.stop()

if not st.session_state.daily_data:
    st.warning("No daily data available.")
    st.stop()


# -----------------------------
# Select day
# -----------------------------
day_keys = sorted(st.session_state.daily_data.keys(), reverse=True)

selected_day = st.sidebar.selectbox(
    "Select day",
    options=day_keys,
    key="selected_day",
)


# -----------------------------
# Plot
# -----------------------------
needs_plot_refresh = (
    st.session_state.daily_plots is None
    or st.session_state.daily_plots.get("selected_day") != selected_day
)

if needs_plot_refresh:
    day_df = st.session_state.daily_data[selected_day]
    seq_windows = get_sequence_windows_cached()

    df_classified = classify_online_offline(day_df, seq_windows)
    fig_track = build_colored_track(day_df, seq_windows)

    online_df = df_classified[df_classified["Status"] == "Online"]
    offline_df = df_classified[df_classified["Status"] == "Offline"]

    combined_speed = df_classified["Bottom Speed"].dropna()
    x_min = combined_speed.min()
    x_max = combined_speed.max()
    n_bins = 30
    bin_size = (x_max - x_min) / n_bins if x_max > x_min else 0.1

    fig_speed_online = build_histogram(
        online_df,
        "Vessel Speed Distribution - Online",
        ONLINE_COLOR,
        x_min,
        x_max,
        bin_size,
    )

    fig_speed_offline = build_histogram(
        offline_df,
        "Vessel Speed Distribution - Offline",
        OFFLINE_COLOR,
        x_min,
        x_max,
        bin_size,
    )

    st.session_state.daily_plots = {
        "selected_day": selected_day,
        "fig_track": fig_track,
        "fig_speed_online": fig_speed_online,
        "fig_speed_offline": fig_speed_offline,
    }


# -----------------------------
# Display
# -----------------------------
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(
        st.session_state.daily_plots["fig_track"],
        theme=None,
        use_container_width=True,
    )

with col2:
    st.plotly_chart(
        st.session_state.daily_plots["fig_speed_online"],
        theme=None,
        use_container_width=True,
    )
    st.plotly_chart(
        st.session_state.daily_plots["fig_speed_offline"],
        theme=None,
        use_container_width=True,
    )