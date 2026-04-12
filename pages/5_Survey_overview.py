import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.data_loader import (
    load_database_clean,
    load_orca_web_clean,
    build_sequence_windows,
)

st.set_page_config(page_title="Survey overview", page_icon=":bar_chart:", layout="wide")
st.header("Survey overview")

DB_FILE = "24hrVesselPosition/database.csv"
ORCA_FILE = "orca-web.csv"

# -----------------------------
# Session state
# -----------------------------
for key in [
    "overview_source_df",
    "overview_orca_df",
    "overview_sequence_windows",
    "overview_daily_distance_split_df",
    "overview_speed_split_df",
    "overview_weekly_speed_split_df",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# -----------------------------
# Cached loaders
# -----------------------------
@st.cache_data
def get_database():
    return load_database_clean(DB_FILE)


@st.cache_data
def get_orca():
    return load_orca_web_clean(ORCA_FILE)


@st.cache_data
def get_sequence_windows():
    orca_df = get_orca()
    return build_sequence_windows(orca_df)


# -----------------------------
# Daily distance split
# -----------------------------
@st.cache_data
def build_daily_distance_split():
    df = get_database().copy()
    seq_windows = get_sequence_windows().copy()

    if df.empty:
        return pd.DataFrame(columns=["Date", "Online_km", "Offline_km", "Total_km"])

    df = df.sort_values("DateTime").reset_index(drop=True)

    seg = pd.DataFrame({
        "DateTime_start": df["DateTime"].iloc[:-1].values,
        "DateTime_end": df["DateTime"].iloc[1:].values,
        "Easting_start": df["Easting"].iloc[:-1].values,
        "Easting_end": df["Easting"].iloc[1:].values,
        "Northing_start": df["Northing"].iloc[:-1].values,
        "Northing_end": df["Northing"].iloc[1:].values,
    })

    seg["MidTime"] = seg["DateTime_start"] + (seg["DateTime_end"] - seg["DateTime_start"]) / 2
    seg["Date"] = pd.to_datetime(seg["MidTime"]).dt.normalize()

    dx = seg["Easting_end"] - seg["Easting_start"]
    dy = seg["Northing_end"] - seg["Northing_start"]
    seg["Distance_km"] = np.sqrt(dx * dx + dy * dy) / 1000.0

    seg["Status"] = "Offline"

    for _, row in seq_windows.iterrows():
        mask = (seg["MidTime"] >= row["Start"]) & (seg["MidTime"] <= row["End"])
        seg.loc[mask, "Status"] = "Online"

    summary = (
        seg.groupby(["Date", "Status"], as_index=False)["Distance_km"]
        .sum()
        .pivot(index="Date", columns="Status", values="Distance_km")
        .fillna(0)
        .reset_index()
    )

    summary = summary.rename(columns={"Online": "Online_km", "Offline": "Offline_km"})
    summary["Total_km"] = summary["Online_km"] + summary["Offline_km"]

    return summary.sort_values("Date").reset_index(drop=True)


# -----------------------------
# Daily speed split
# -----------------------------
@st.cache_data
def build_daily_speed_split():
    df = get_database().copy()
    seq_windows = get_sequence_windows().copy()

    if df.empty:
        return pd.DataFrame(columns=["Date", "Online_speed", "Offline_speed"])

    df = df.sort_values("DateTime").reset_index(drop=True)
    df["Status"] = "Offline"

    for _, row in seq_windows.iterrows():
        mask = (df["DateTime"] >= row["Start"]) & (df["DateTime"] <= row["End"])
        df.loc[mask, "Status"] = "Online"

    df["Date"] = pd.to_datetime(df["DateTime"]).dt.normalize()

    summary = (
        df.groupby(["Date", "Status"])["Bottom Speed"]
        .mean()
        .unstack()
        .fillna(0)
        .reset_index()
    )

    summary = summary.rename(columns={"Online": "Online_speed", "Offline": "Offline_speed"})

    return summary.sort_values("Date").reset_index(drop=True)


# -----------------------------
# Weekly speed split (NEW)
# -----------------------------
@st.cache_data
def build_weekly_speed_split():
    df = get_database().copy()
    seq_windows = get_sequence_windows().copy()

    if df.empty:
        return pd.DataFrame(columns=["WeekStart", "WeekLabel", "Online_speed", "Offline_speed"])

    df = df.sort_values("DateTime").reset_index(drop=True)
    df["Status"] = "Offline"

    for _, row in seq_windows.iterrows():
        mask = (df["DateTime"] >= row["Start"]) & (df["DateTime"] <= row["End"])
        df.loc[mask, "Status"] = "Online"

    df["WeekStart"] = (
        pd.to_datetime(df["DateTime"]) - pd.to_timedelta(df["DateTime"].dt.weekday, unit="d")
    ).dt.normalize()

    df["WeekLabel"] = df["WeekStart"].dt.strftime("%Y-W%U")

    summary = (
        df.groupby(["WeekStart", "WeekLabel", "Status"])["Bottom Speed"]
        .mean()
        .unstack()
        .fillna(0)
        .reset_index()
    )

    summary = summary.rename(columns={"Online": "Online_speed", "Offline": "Offline_speed"})

    return summary.sort_values("WeekStart").reset_index(drop=True)


# -----------------------------
# Load data
# -----------------------------
if st.session_state.overview_source_df is None:
    st.session_state.overview_source_df = get_database()

if st.session_state.overview_orca_df is None:
    st.session_state.overview_orca_df = get_orca()

if st.session_state.overview_sequence_windows is None:
    st.session_state.overview_sequence_windows = get_sequence_windows()

if st.session_state.overview_daily_distance_split_df is None:
    st.session_state.overview_daily_distance_split_df = build_daily_distance_split()

if st.session_state.overview_speed_split_df is None:
    st.session_state.overview_speed_split_df = build_daily_speed_split()

if st.session_state.overview_weekly_speed_split_df is None:
    st.session_state.overview_weekly_speed_split_df = build_weekly_speed_split()

distance_df = st.session_state.overview_daily_distance_split_df
speed_df = st.session_state.overview_speed_split_df
weekly_speed_df = st.session_state.overview_weekly_speed_split_df

# -----------------------------
# Plots
# -----------------------------
fig_dist_split = px.bar(
    distance_df,
    x="Date",
    y=["Online_km", "Offline_km"],
    title="Daily distance travelled - online vs offline",
    template="seaborn",
    barmode="stack",
)

fig_speed_line = px.line(
    speed_df,
    x="Date",
    y=["Online_speed", "Offline_speed"],
    title="Daily average speed - online vs offline",
    template="seaborn",
    markers=True,
)

fig_weekly_speed = px.line(
    weekly_speed_df,
    x="WeekLabel",
    y=["Online_speed", "Offline_speed"],
    title="Weekly average speed - online vs offline",
    template="seaborn",
    markers=True,
)

# -----------------------------
# Metrics
# -----------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Survey days", len(distance_df))

with col2:
    st.metric("Total online distance", f"{distance_df['Online_km'].sum():.1f} km")

with col3:
    st.metric("Total offline distance", f"{distance_df['Offline_km'].sum():.1f} km")

# -----------------------------
# Display
# -----------------------------
st.plotly_chart(fig_dist_split, use_container_width=True)
st.plotly_chart(fig_speed_line, use_container_width=True)

st.markdown("---")

st.subheader("Weekly speed overview")
st.plotly_chart(fig_weekly_speed, use_container_width=True)