import io
import math
import os
import tempfile
import zipfile

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import shapefile
import streamlit as st

from utils.data_loader import (
    load_database_clean,
    load_orca_web_clean,
    build_sequence_windows,
    slice_track_by_time,
    add_cardinal_direction,
)

st.set_page_config(page_title="Directional analysis", page_icon=":compass:", layout="wide")

DB_FILE = "24hrVesselPosition/database.csv"
ORCA_FILE = "orca-web.csv"
MAX_PLOT_POINTS = 4000


# -----------------------------
# Session state
# -----------------------------
for key in [
    "dir_source_df",
    "dir_orca_df",
    "dir_seq_windows",
    "dir_turn_windows",
    "dir_sequence_data",
    "dir_turn_data",
    "dir_combined_plot",
    "dir_sequence_plots",
    "dir_turn_plots",
    "dir_sequence_summary",
    "dir_turn_summary",
    "dir_combined_shapefile_zip",
    "dir_ready",
]:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.dir_ready is None:
    st.session_state.dir_ready = False


# -----------------------------
# Cached loaders
# -----------------------------
@st.cache_data
def get_database():
    return load_database_clean(DB_FILE)


@st.cache_data
def get_orca():
    df = load_orca_web_clean(ORCA_FILE)
    return add_cardinal_direction(df)


def normalize_heading_direction_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "Heading" not in df.columns:
        if "Heading_x" in df.columns:
            df["Heading"] = df["Heading_x"]
        elif "Heading_y" in df.columns:
            df["Heading"] = df["Heading_y"]
        else:
            df["Heading"] = np.nan

    if "Cardinal_Direction" not in df.columns:
        if "Cardinal_Direction_x" in df.columns:
            df["Cardinal_Direction"] = df["Cardinal_Direction_x"]
        elif "Cardinal_Direction_y" in df.columns:
            df["Cardinal_Direction"] = df["Cardinal_Direction_y"]
        else:
            df["Cardinal_Direction"] = np.nan

    return df


@st.cache_data
def get_sequence_windows():
    orca_df = get_orca()
    seq_windows = build_sequence_windows(orca_df).copy()

    direction_map = (
        orca_df[["Seq No", "Heading", "Cardinal_Direction"]]
        .drop_duplicates()
        .rename(columns={"Seq No": "Sequence No"})
    )

    seq_windows = seq_windows.merge(direction_map, on="Sequence No", how="left")
    seq_windows = normalize_heading_direction_columns(seq_windows)
    seq_windows = seq_windows.sort_values("Sequence No").reset_index(drop=True)
    return seq_windows


@st.cache_data
def get_turn_windows_corrected():
    seq_windows = get_sequence_windows().copy()
    seq_windows = normalize_heading_direction_columns(seq_windows)
    seq_windows = seq_windows.sort_values("Sequence No").reset_index(drop=True)

    turns = []
    for i in range(len(seq_windows) - 1):
        current_seq = seq_windows.iloc[i]
        next_seq = seq_windows.iloc[i + 1]

        turns.append(
            {
                "Turn No": int(current_seq["Sequence No"]),
                "Sequence No": int(current_seq["Sequence No"]),
                "Start": current_seq["End"],
                "End": next_seq["Start"],
                "Heading": current_seq.get("Heading", np.nan),
                "Cardinal_Direction": current_seq.get("Cardinal_Direction", np.nan),
            }
        )

    return pd.DataFrame(turns)


# -----------------------------
# Helpers
# -----------------------------
def format_hms(total_seconds: float) -> str:
    total_seconds = int(round(total_seconds))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def compute_track_metrics(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 2:
        return {
            "start": None,
            "end": None,
            "duration_s": 0,
            "distance_km": 0.0,
            "avg_speed_knots": 0.0,
        }

    df = df.sort_values("DateTime").reset_index(drop=True)

    dx = df["Easting"].diff()
    dy = df["Northing"].diff()
    distance_km = np.sqrt(dx**2 + dy**2).fillna(0).sum() / 1000.0

    start = df["DateTime"].iloc[0]
    end = df["DateTime"].iloc[-1]
    duration_s = (end - start).total_seconds()

    return {
        "start": start,
        "end": end,
        "duration_s": duration_s,
        "distance_km": float(distance_km),
        "avg_speed_knots": float(df["Bottom Speed"].mean()) if not df.empty else 0.0,
    }


def thin_for_plot(df: pd.DataFrame, max_points: int = MAX_PLOT_POINTS) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = math.ceil(len(df) / max_points)
    return df.iloc[::step].copy()


def get_color_map(mode: str, directions: list[str]) -> dict:
    if mode == "Sequence lines":
        palette = ["#0B3D91", "#4F86F7", "#7FB3FF", "#B7D4FF"]
    elif mode == "Line changes":
        palette = ["#CC5500", "#F28C28", "#FFB366", "#FFD1A3"]
    else:
        palette = ["#0B3D91", "#4F86F7", "#CC5500", "#F28C28", "#7FB3FF", "#FFB366"]

    return {direction: palette[i % len(palette)] for i, direction in enumerate(directions)}


def build_grouped_tracks(
    source_df: pd.DataFrame,
    windows_df: pd.DataFrame,
    id_col: str,
) -> dict:
    grouped = {}

    for _, row in windows_df.iterrows():
        direction = row.get("Cardinal_Direction", np.nan)
        if pd.isna(direction):
            continue

        item_id = int(row[id_col])
        item_df = slice_track_by_time(source_df, row["Start"], row["End"])

        if len(item_df) < 2:
            continue

        if direction not in grouped:
            grouped[direction] = []

        grouped[direction].append(
            {
                "id": item_id,
                "heading": row.get("Heading", np.nan),
                "direction": direction,
                "df": item_df.reset_index(drop=True),
            }
        )

    return grouped


def build_track_figure(items: list[dict], title: str, item_label: str, color_map: dict):
    fig = go.Figure()
    shown_legend = set()

    for item in items:
        df = thin_for_plot(item["df"].sort_values("DateTime").reset_index(drop=True))
        direction = item["direction"]

        fig.add_trace(
            go.Scattergl(
                x=df["Easting"],
                y=df["Northing"],
                mode="lines",
                line=dict(width=2, color=color_map[direction]),
                name=direction,
                showlegend=direction not in shown_legend,
                text=df["Date"].astype(str),
                customdata=np.column_stack([
                    df["Time"].astype(str).to_numpy(),
                    np.full(len(df), item["id"]),
                    np.full(len(df), item.get("heading", np.nan)),
                    np.full(len(df), direction),
                ]),
                hovertemplate=(
                    "Date: %{text}<br>"
                    "Time: %{customdata[0]}<br>"
                    + item_label + ": %{customdata[1]}<br>"
                    + "Heading: %{customdata[2]}<br>"
                    + "Direction: %{customdata[3]}<br>"
                    + "Easting: %{x}<br>"
                    + "Northing: %{y}<extra></extra>"
                ),
            )
        )
        shown_legend.add(direction)

    fig.update_layout(
        title=title,
        template="seaborn",
        width=800,
        height=800,
        xaxis_title="Easting",
        yaxis_title="Northing",
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def build_speed_histogram(df: pd.DataFrame, title: str, color: str):
    fig = px.histogram(
        df,
        x="Bottom Speed",
        nbins=30,
        title=title,
        opacity=0.6,
        template="seaborn",
    )
    fig.update_traces(marker_color=color, marker_line_color="black", marker_line_width=1)
    fig.update_xaxes(title_text="Bottom Speed (knots)")
    fig.update_yaxes(title_text="Frequency")
    fig.update_layout(showlegend=False, height=350)
    return fig


def build_speed_boxplot(data_map: dict, title: str, color_map: dict):
    rows = []

    for direction in sorted([d for d in data_map.keys() if pd.notna(d)]):
        for item in data_map.get(direction, []):
            df = item["df"]
            if df.empty:
                continue

            rows.append(
                df[["Bottom Speed"]].assign(Direction=direction)
            )

    if not rows:
        return None

    speed_df = pd.concat(rows, ignore_index=True)

    fig = px.box(
        speed_df,
        x="Direction",
        y="Bottom Speed",
        color="Direction",
        title=title,
        template="seaborn",
        color_discrete_map=color_map,
        points="outliers",
    )
    fig.update_xaxes(title_text="Direction")
    fig.update_yaxes(title_text="Bottom Speed (knots)")
    fig.update_layout(height=420, legend_title_text="Direction")
    return fig


def build_avg_speed_lineplot(data_map: dict, title: str, id_label: str, color_map: dict, x_col_name: str):
    rows = []

    for direction in sorted([d for d in data_map.keys() if pd.notna(d)]):
        for item in data_map.get(direction, []):
            df = item["df"]
            if df.empty:
                continue

            rows.append(
                {
                    x_col_name: item["id"],
                    "Direction": direction,
                    "Average Speed": float(df["Bottom Speed"].mean()),
                }
            )

    if not rows:
        return None

    plot_df = pd.DataFrame(rows).sort_values(x_col_name).reset_index(drop=True)

    fig = px.line(
        plot_df,
        x=x_col_name,
        y="Average Speed",
        color="Direction",
        markers=True,
        title=title,
        template="seaborn",
        color_discrete_map=color_map,
        hover_data={x_col_name: True, "Average Speed": ":.2f"},
    )
    fig.update_xaxes(title_text=id_label)
    fig.update_yaxes(title_text="Average Speed (knots)")
    fig.update_layout(height=420, legend_title_text="Direction")
    return fig


def build_summary_table(data_map: dict) -> pd.DataFrame:
    rows = []

    for direction in sorted([d for d in data_map.keys() if pd.notna(d)]):
        items = data_map.get(direction, [])
        if not items:
            continue

        distances = []
        durations = []
        speeds = []

        for item in items:
            metrics = compute_track_metrics(item["df"])
            distances.append(metrics["distance_km"])
            durations.append(metrics["duration_s"])
            speeds.append(metrics["avg_speed_knots"])

        avg_duration_s = float(np.mean(durations)) if durations else 0.0

        rows.append(
            {
                "Direction": direction,
                "Count": len(items),
                "Average distance (km)": round(float(np.mean(distances)), 2) if distances else 0.0,
                "Average time": format_hms(avg_duration_s),
                "Average speed (knots)": round(float(np.mean(speeds)), 2) if speeds else 0.0,
            }
        )

    return pd.DataFrame(rows)


def build_mode_plots(data_map: dict, mode_name: str, item_label: str, x_col_name: str):
    available_dirs = sorted([d for d in data_map.keys() if pd.notna(d)])

    if not available_dirs:
        return None

    color_map = get_color_map(mode_name, available_dirs)

    items = []
    for direction in available_dirs:
        items.extend(data_map.get(direction, []))

    if not items:
        return None

    fig_track = build_track_figure(
        items=items,
        title=f"{mode_name} - comparison by direction",
        item_label=item_label,
        color_map=color_map,
    )

    speed_figs = {}
    for direction in available_dirs:
        df_dir_list = data_map.get(direction, [])
        if not df_dir_list:
            continue

        df_dir = pd.concat(
            [
                item["df"].assign(
                    _direction=direction,
                    _id=item["id"],
                    _heading=item.get("heading", np.nan),
                )
                for item in df_dir_list
            ],
            ignore_index=True,
        ).sort_values("DateTime").reset_index(drop=True)

        speed_figs[direction] = build_speed_histogram(
            df=df_dir,
            title=f"Speed distribution - {direction}",
            color=color_map[direction],
        )

    boxplot = build_speed_boxplot(
        data_map=data_map,
        title=f"Speed boxplot - {mode_name}",
        color_map=color_map,
    )

    avg_speed_lineplot = build_avg_speed_lineplot(
        data_map=data_map,
        title=f"Average speed by {item_label.lower()}",
        id_label=item_label,
        color_map=color_map,
        x_col_name=x_col_name,
    )

    return {
        "fig_track": fig_track,
        "speed_figs": speed_figs,
        "boxplot": boxplot,
        "avg_speed_lineplot": avg_speed_lineplot,
        "directions": available_dirs,
    }


def build_combined_plot(sequence_data: dict, turn_data: dict):
    seq_dirs = sorted([d for d in sequence_data.keys() if pd.notna(d)])
    turn_dirs = sorted([d for d in turn_data.keys() if pd.notna(d)])

    seq_color_map = get_color_map("Sequence lines", seq_dirs)
    turn_color_map = get_color_map("Line changes", turn_dirs)

    fig = go.Figure()
    shown_legend = set()

    for direction in seq_dirs:
        for item in sequence_data.get(direction, []):
            df = thin_for_plot(item["df"].sort_values("DateTime").reset_index(drop=True))
            legend_name = f"Sequence - {direction}"

            fig.add_trace(
                go.Scattergl(
                    x=df["Easting"],
                    y=df["Northing"],
                    mode="lines",
                    line=dict(width=2, color=seq_color_map[direction]),
                    name=legend_name,
                    showlegend=legend_name not in shown_legend,
                    text=df["Date"].astype(str),
                    customdata=np.column_stack([
                        df["Time"].astype(str).to_numpy(),
                        np.full(len(df), item["id"]),
                        np.full(len(df), item.get("heading", np.nan)),
                        np.full(len(df), direction),
                        np.full(len(df), "Sequence"),
                    ]),
                    hovertemplate=(
                        "Type: %{customdata[4]}<br>"
                        "Date: %{text}<br>"
                        "Time: %{customdata[0]}<br>"
                        "ID: %{customdata[1]}<br>"
                        "Heading: %{customdata[2]}<br>"
                        "Direction: %{customdata[3]}<br>"
                        "Easting: %{x}<br>"
                        "Northing: %{y}<extra></extra>"
                    ),
                )
            )
            shown_legend.add(legend_name)

    for direction in turn_dirs:
        for item in turn_data.get(direction, []):
            df = thin_for_plot(item["df"].sort_values("DateTime").reset_index(drop=True))
            legend_name = f"Line change - {direction}"

            fig.add_trace(
                go.Scattergl(
                    x=df["Easting"],
                    y=df["Northing"],
                    mode="lines",
                    line=dict(width=2, color=turn_color_map[direction]),
                    name=legend_name,
                    showlegend=legend_name not in shown_legend,
                    text=df["Date"].astype(str),
                    customdata=np.column_stack([
                        df["Time"].astype(str).to_numpy(),
                        np.full(len(df), item["id"]),
                        np.full(len(df), item.get("heading", np.nan)),
                        np.full(len(df), direction),
                        np.full(len(df), "Line change"),
                    ]),
                    hovertemplate=(
                        "Type: %{customdata[4]}<br>"
                        "Date: %{text}<br>"
                        "Time: %{customdata[0]}<br>"
                        "ID: %{customdata[1]}<br>"
                        "Heading: %{customdata[2]}<br>"
                        "Direction: %{customdata[3]}<br>"
                        "Easting: %{x}<br>"
                        "Northing: %{y}<extra></extra>"
                    ),
                )
            )
            shown_legend.add(legend_name)

    fig.update_layout(
        title="Combined survey lines and line changes",
        template="seaborn",
        width=1000,
        height=900,
        xaxis_title="Easting",
        yaxis_title="Northing",
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def build_combined_shapefile_zip(sequence_data: dict, turn_data: dict) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_base = os.path.join(tmpdir, "combined_directional_analysis")
        writer = shapefile.Writer(shp_base, shapeType=shapefile.POLYLINE)
        writer.autoBalance = 1

        writer.field("TYPE", "C", size=20)
        writer.field("ID", "N", size=10, decimal=0)
        writer.field("DIRECTION", "C", size=20)
        writer.field("HEADING", "C", size=20)

        def add_records(data_map: dict, record_type: str):
            for direction in sorted([d for d in data_map.keys() if pd.notna(d)]):
                for item in data_map.get(direction, []):
                    df = item["df"].sort_values("DateTime").reset_index(drop=True)
                    if len(df) < 2:
                        continue

                    points = [[float(row.Easting), float(row.Northing)] for row in df.itertuples(index=False)]
                    writer.line([points])
                    heading_value = item.get("heading", "")
                    heading_text = "" if pd.isna(heading_value) else str(heading_value)

                    writer.record(
                        TYPE=record_type,
                        ID=int(item["id"]),
                        DIRECTION=str(direction),
                        HEADING=heading_text,
                    )

        add_records(sequence_data, "Sequence")
        add_records(turn_data, "LineChange")
        writer.close()

        cpg_path = shp_base + ".cpg"
        with open(cpg_path, "w", encoding="utf-8") as f:
            f.write("UTF-8")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext in [".shp", ".shx", ".dbf", ".cpg"]:
                file_path = shp_base + ext
                if os.path.exists(file_path):
                    zf.write(file_path, arcname=os.path.basename(file_path))

        zip_buffer.seek(0)
        return zip_buffer.getvalue()


# -----------------------------
# Load base data once
# -----------------------------
try:
    if st.session_state.dir_source_df is None:
        st.session_state.dir_source_df = get_database()

    if st.session_state.dir_orca_df is None:
        st.session_state.dir_orca_df = get_orca()

    if st.session_state.dir_seq_windows is None:
        st.session_state.dir_seq_windows = get_sequence_windows()

    if st.session_state.dir_turn_windows is None:
        st.session_state.dir_turn_windows = get_turn_windows_corrected()

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

if st.session_state.dir_source_df.empty:
    st.warning("The database is empty.")
    st.stop()


# -----------------------------
# Refresh button
# -----------------------------
refresh_clicked = st.sidebar.button("Refresh data")

if refresh_clicked:
    get_sequence_windows.clear()
    get_turn_windows_corrected.clear()

    st.session_state.dir_seq_windows = None
    st.session_state.dir_turn_windows = None
    st.session_state.dir_sequence_data = None
    st.session_state.dir_turn_data = None
    st.session_state.dir_combined_plot = None
    st.session_state.dir_sequence_plots = None
    st.session_state.dir_turn_plots = None
    st.session_state.dir_sequence_summary = None
    st.session_state.dir_turn_summary = None
    st.session_state.dir_combined_shapefile_zip = None
    st.session_state.dir_ready = False


# -----------------------------
# Build only on refresh or first load
# -----------------------------
if not st.session_state.dir_ready:
    try:
        with st.spinner("Refreshing directional analysis..."):
            st.session_state.dir_seq_windows = get_sequence_windows()
            st.session_state.dir_turn_windows = get_turn_windows_corrected()

            st.session_state.dir_sequence_data = build_grouped_tracks(
                st.session_state.dir_source_df,
                st.session_state.dir_seq_windows,
                id_col="Sequence No",
            )

            st.session_state.dir_turn_data = build_grouped_tracks(
                st.session_state.dir_source_df,
                st.session_state.dir_turn_windows,
                id_col="Turn No",
            )

            st.session_state.dir_combined_plot = build_combined_plot(
                st.session_state.dir_sequence_data,
                st.session_state.dir_turn_data,
            )

            st.session_state.dir_combined_shapefile_zip = build_combined_shapefile_zip(
                st.session_state.dir_sequence_data,
                st.session_state.dir_turn_data,
            )

            st.session_state.dir_sequence_plots = build_mode_plots(
                data_map=st.session_state.dir_sequence_data,
                mode_name="Sequence lines",
                item_label="Sequence No",
                x_col_name="Sequence No",
            )

            st.session_state.dir_turn_plots = build_mode_plots(
                data_map=st.session_state.dir_turn_data,
                mode_name="Line changes",
                item_label="Line change No",
                x_col_name="Line change No",
            )

            st.session_state.dir_sequence_summary = build_summary_table(
                st.session_state.dir_sequence_data
            )

            st.session_state.dir_turn_summary = build_summary_table(
                st.session_state.dir_turn_data
            )

            st.session_state.dir_ready = True

    except Exception as e:
        st.error(f"Error building directional data: {e}")
        st.stop()


if not st.session_state.dir_ready:
    st.info("Click 'Refresh data' to build the analysis.")
    st.stop()


# -----------------------------
# Display - Combined section
# -----------------------------

st.plotly_chart(
    st.session_state.dir_combined_plot,
    theme=None,
    use_container_width=True,
)

st.download_button(
    label="Export shapefile",
    data=st.session_state.dir_combined_shapefile_zip,
    file_name="combined_directional_analysis.zip",
    mime="application/zip",
)

st.markdown("---")


# -----------------------------
# Display - Sequences
# -----------------------------
st.subheader("Sequences")

if st.session_state.dir_sequence_summary is not None and not st.session_state.dir_sequence_summary.empty:
    st.dataframe(st.session_state.dir_sequence_summary, use_container_width=True)

if st.session_state.dir_sequence_plots is None:
    st.warning("No sequence line data available.")
else:
    left_col, right_col = st.columns([1.2, 1.0])

    with left_col:
        st.plotly_chart(
            st.session_state.dir_sequence_plots["fig_track"],
            theme=None,
            use_container_width=True,
        )

    with right_col:
        hist_cols = st.columns(len(st.session_state.dir_sequence_plots["directions"]))
        for col, direction in zip(hist_cols, st.session_state.dir_sequence_plots["directions"]):
            with col:
                st.plotly_chart(
                    st.session_state.dir_sequence_plots["speed_figs"][direction],
                    theme=None,
                    use_container_width=True,
                )

        if st.session_state.dir_sequence_plots["boxplot"] is not None:
            st.plotly_chart(
                st.session_state.dir_sequence_plots["boxplot"],
                theme=None,
                use_container_width=True,
            )

    if st.session_state.dir_sequence_plots["avg_speed_lineplot"] is not None:
        st.plotly_chart(
            st.session_state.dir_sequence_plots["avg_speed_lineplot"],
            theme=None,
            use_container_width=True,
        )

st.markdown("---")


# -----------------------------
# Display - Line changes
# -----------------------------
st.subheader("Line changes")

if st.session_state.dir_turn_summary is not None and not st.session_state.dir_turn_summary.empty:
    st.dataframe(st.session_state.dir_turn_summary, use_container_width=True)

if st.session_state.dir_turn_plots is None:
    st.warning("No line change data available.")
else:
    left_col, right_col = st.columns([1.2, 1.0])

    with left_col:
        st.plotly_chart(
            st.session_state.dir_turn_plots["fig_track"],
            theme=None,
            use_container_width=True,
        )

    with right_col:
        hist_cols = st.columns(len(st.session_state.dir_turn_plots["directions"]))
        for col, direction in zip(hist_cols, st.session_state.dir_turn_plots["directions"]):
            with col:
                st.plotly_chart(
                    st.session_state.dir_turn_plots["speed_figs"][direction],
                    theme=None,
                    use_container_width=True,
                )

        if st.session_state.dir_turn_plots["boxplot"] is not None:
            st.plotly_chart(
                st.session_state.dir_turn_plots["boxplot"],
                theme=None,
                use_container_width=True,
            )

    if st.session_state.dir_turn_plots["avg_speed_lineplot"] is not None:
        st.plotly_chart(
            st.session_state.dir_turn_plots["avg_speed_lineplot"],
            theme=None,
            use_container_width=True,
        )