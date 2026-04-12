import io
import math
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from utils.data_loader import (
    load_database_cached,
    load_orca_cached,
    build_sequence_windows,
    slice_track_by_time,
    build_summary_metrics,
)

st.set_page_config(page_title="Segment analysis", page_icon=":compass:", layout="wide")
st.header("Segment analysis")

DB_FILE = Path("24hrVesselPosition/database.csv")
ORCA_FILE = Path("orca-web.csv")

ONLINE_COLOR = "#0B3D91"
OFFLINE_COLOR = "#CC5500"
MAX_PLOT_POINTS = 8000


# -----------------------------
# Cached loaders
# -----------------------------
@st.cache_data
def get_database():
    return load_database_cached(DB_FILE)


@st.cache_data
def get_orca():
    return load_orca_cached(ORCA_FILE)


@st.cache_data
def get_sequence_windows_cached():
    orca_df = get_orca()
    return build_sequence_windows(orca_df)


@st.cache_data
def get_segment_windows():
    seq_windows = get_sequence_windows_cached().copy()
    seq_windows = seq_windows.sort_values("Sequence No").reset_index(drop=True)

    rows = []

    for i in range(len(seq_windows) - 1):
        current_seq = seq_windows.iloc[i]
        next_seq = seq_windows.iloc[i + 1]

        seq_no = int(current_seq["Sequence No"])

        rows.append(
            {
                "Segment No": seq_no,
                "Sequence No": seq_no,
                "Sequence Start": current_seq["Start"],
                "Sequence End": current_seq["End"],
                "Turn Start": current_seq["End"],
                "Turn End": next_seq["Start"],
                "Segment Start": current_seq["Start"],
                "Segment End": next_seq["Start"],
                "Heading": current_seq.get("Heading", ""),
            }
        )

    return pd.DataFrame(rows)


# -----------------------------
# Session state
# -----------------------------
for key in [
    "segment_source_df",
    "segment_windows",
    "segment_plot_cache",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# -----------------------------
# Helpers
# -----------------------------
def thin_for_plot(df: pd.DataFrame, max_points: int = MAX_PLOT_POINTS) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = math.ceil(len(df) / max_points)
    return df.iloc[::step].copy()


def format_duration_hours(duration_hr: float) -> str:
    total_seconds = int(round(duration_hr * 3600))
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def add_metrics_table_annotation(fig: go.Figure, segment_metrics: dict, seq_metrics: dict, turn_metrics: dict) -> None:
    header_fill = "#D9E2F3"
    segment_fill = "#F2F2F2"
    seq_fill = "#DCE6F1"
    turn_fill = "#FCE4D6"

    table = go.Table(
        domain=dict(x=[0.35, 1.00], y=[0.70, 1.00]),
        columnwidth=[150, 150, 150, 150],
        header=dict(
            values=["Part", "Duration", "Distance (km)", "Av. speed (kt)"],
            fill_color=header_fill,
            align="left",
            font=dict(size=12),
            height=30,
        ),
        cells=dict(
            values=[
                ["Complete", "Online", "Offline"],
                [
                    format_duration_hours(segment_metrics["duration_hr"]),
                    format_duration_hours(seq_metrics["duration_hr"]),
                    format_duration_hours(turn_metrics["duration_hr"]),
                ],
                [
                    f"{segment_metrics['distance_km']:.2f}",
                    f"{seq_metrics['distance_km']:.2f}",
                    f"{turn_metrics['distance_km']:.2f}",
                ],
                [
                    f"{segment_metrics['avg_speed_knots']:.2f}",
                    f"{seq_metrics['avg_speed_knots']:.2f}",
                    f"{turn_metrics['avg_speed_knots']:.2f}",
                ],
            ],
            fill_color=[
                ["white", "white", "white"],
                [segment_fill, seq_fill, turn_fill],
                [segment_fill, seq_fill, turn_fill],
                [segment_fill, seq_fill, turn_fill],
            ],
            align="left",
            font=dict(size=11),
            height=28,
        ),
    )

    fig.add_trace(table)


def add_aggregate_metrics_table_annotation(
    fig: go.Figure,
    total_metrics: dict,
    avg_distance_km: float,
    avg_duration_hr: float,
    mode_label: str,
) -> None:
    header_fill = "#D9E2F3"
    row_fill = "#DCE6F1" if mode_label == "Sequence" else "#FCE4D6"

    table = go.Table(
        domain=dict(x=[0.58, 1.00], y=[0.74, 1.00]),
        columnwidth=[165, 120],
        header=dict(
            values=["Metric", "Value"],
            fill_color=header_fill,
            align="left",
            font=dict(size=12),
            height=30,
        ),
        cells=dict(
            values=[
                [
                    "Total duration",
                    "Total distance",
                    "Average speed",
                    "Average distance",
                    "Average duration",
                ],
                [
                    format_duration_hours(total_metrics["duration_hr"]),
                    f"{total_metrics['distance_km']:.2f} km",
                    f"{total_metrics['avg_speed_knots']:.2f} kt",
                    f"{avg_distance_km:.2f} km",
                    format_duration_hours(avg_duration_hr),
                ],
            ],
            fill_color=[[row_fill] * 5, [row_fill] * 5],
            align="left",
            font=dict(size=11),
            height=28,
        ),
    )

    fig.add_trace(table)


def build_track_figure(
    title: str,
    metrics: dict,
    mode: str,
    seq_parts: list[pd.DataFrame] | None = None,
    turn_parts: list[pd.DataFrame] | None = None,
    window_parts: list[pd.DataFrame] | None = None,
    segment_metrics: dict | None = None,
    seq_metrics: dict | None = None,
    turn_metrics: dict | None = None,
    aggregate_table: dict | None = None,
) -> go.Figure:
    fig = go.Figure()

    if mode == "Complete segment":
        first_seq = True
        if seq_parts is not None:
            for part_df in seq_parts:
                if part_df.empty:
                    continue

                plot_part = thin_for_plot(part_df)

                fig.add_trace(
                    go.Scattergl(
                        x=plot_part["Easting"],
                        y=plot_part["Northing"],
                        mode="lines",
                        line=dict(width=2, color=ONLINE_COLOR),
                        name="Sequence",
                        showlegend=first_seq,
                        text=plot_part["Date"].astype(str),
                        customdata=plot_part[["Time", "Part_ID"]],
                        hovertemplate=(
                            "Part: Sequence %{customdata[1]}<br>"
                            "Date: %{text}<br>"
                            "Time: %{customdata[0]}<br>"
                            "Easting: %{x}<br>"
                            "Northing: %{y}<extra></extra>"
                        ),
                    )
                )
                first_seq = False

        first_turn = True
        if turn_parts is not None:
            for part_df in turn_parts:
                if part_df.empty:
                    continue

                plot_part = thin_for_plot(part_df)

                fig.add_trace(
                    go.Scattergl(
                        x=plot_part["Easting"],
                        y=plot_part["Northing"],
                        mode="lines",
                        line=dict(width=2, color=OFFLINE_COLOR),
                        name="Line change",
                        showlegend=first_turn,
                        text=plot_part["Date"].astype(str),
                        customdata=plot_part[["Time", "Part_ID"]],
                        hovertemplate=(
                            "Part: Line change %{customdata[1]}<br>"
                            "Date: %{text}<br>"
                            "Time: %{customdata[0]}<br>"
                            "Easting: %{x}<br>"
                            "Northing: %{y}<extra></extra>"
                        ),
                    )
                )
                first_turn = False

    else:
        color = ONLINE_COLOR if mode == "Sequence only" else OFFLINE_COLOR
        label = "Sequence" if mode == "Sequence only" else "Line change"

        if window_parts is not None and len(window_parts) > 0:
            first_trace = True
            for part_df in window_parts:
                if part_df.empty:
                    continue

                plot_part = thin_for_plot(part_df)

                fig.add_trace(
                    go.Scattergl(
                        x=plot_part["Easting"],
                        y=plot_part["Northing"],
                        mode="lines",
                        line=dict(width=2, color=color),
                        name=label,
                        showlegend=first_trace,
                        text=plot_part["Date"].astype(str),
                        customdata=plot_part[["Time", "Part_ID"]],
                        hovertemplate=(
                            f"Part: {label} %{{customdata[1]}}<br>"
                            "Date: %{text}<br>"
                            "Time: %{customdata[0]}<br>"
                            "Easting: %{x}<br>"
                            "Northing: %{y}<extra></extra>"
                        ),
                    )
                )
                first_trace = False

    fig.update_layout(
        title=title,
        template="seaborn",
        height=800,
        xaxis_title="Easting",
        yaxis_title="Northing",
    )

    if mode == "Complete segment" and segment_metrics and seq_metrics and turn_metrics:
        add_metrics_table_annotation(fig, segment_metrics, seq_metrics, turn_metrics)
    elif aggregate_table is not None:
        add_aggregate_metrics_table_annotation(
            fig=fig,
            total_metrics=aggregate_table["total_metrics"],
            avg_distance_km=aggregate_table["avg_distance_km"],
            avg_duration_hr=aggregate_table["avg_duration_hr"],
            mode_label=aggregate_table["mode_label"],
        )
    else:
        fig.update_layout(
            annotations=[
                dict(
                    x=0.02, y=0.98, xref="paper", yref="paper",
                    text=f"Duration: {metrics['duration_hr']:.2f} hours",
                    showarrow=False, font=dict(size=14)
                ),
                dict(
                    x=0.02, y=0.94, xref="paper", yref="paper",
                    text=f"Distance travelled: {metrics['distance_km']:.2f} km",
                    showarrow=False, font=dict(size=14)
                ),
                dict(
                    x=0.02, y=0.90, xref="paper", yref="paper",
                    text=f"Average speed: {metrics['avg_speed_knots']:.2f} knots",
                    showarrow=False, font=dict(size=14)
                ),
                dict(
                    x=0.02, y=0.03, xref="paper", yref="paper",
                    text=f"Start: {metrics['start']}",
                    showarrow=False, font=dict(size=14)
                ),
                dict(
                    x=0.02, y=0.00, xref="paper", yref="paper",
                    text=f"End: {metrics['end']}",
                    showarrow=False, font=dict(size=14)
                ),
            ]
        )

    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return fig


def build_speed_histogram(
    df: pd.DataFrame,
    title: str,
    color: str,
    x_min: float | None = None,
    x_max: float | None = None,
    n_bins: int = 30,
    height: int = 800,
) -> go.Figure:
    speed = df["Bottom Speed"].dropna()

    if speed.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            template="seaborn",
            height=height,
            xaxis_title="Bottom Speed (knots)",
            yaxis_title="Frequency",
        )
        return fig

    if x_min is None:
        x_min = float(speed.min())
    if x_max is None:
        x_max = float(speed.max())

    bin_size = (x_max - x_min) / n_bins if x_max > x_min else 0.1

    fig = go.Figure(
        data=[
            go.Histogram(
                x=speed,
                xbins=dict(start=x_min, end=x_max, size=bin_size),
                marker=dict(color=color, line=dict(color="black", width=1)),
                opacity=0.6,
            )
        ]
    )

    fig.update_layout(
        title=title,
        template="seaborn",
        height=height,
        bargap=0.0,
        showlegend=False,
    )
    fig.update_xaxes(title_text="Bottom Speed (knots)")
    fig.update_yaxes(title_text="Frequency")
    return fig


def get_selected_rows_by_range(segment_windows: pd.DataFrame, start_no: int, end_no: int) -> pd.DataFrame:
    selected_rows = segment_windows[
        (segment_windows["Segment No"] >= start_no) &
        (segment_windows["Segment No"] <= end_no)
    ].copy().sort_values("Segment No").reset_index(drop=True)

    if selected_rows.empty:
        raise ValueError("No segments found in selected range.")

    return selected_rows


def get_selected_rows_by_list(segment_windows: pd.DataFrame, selected_numbers: list[int]) -> pd.DataFrame:
    selected_rows = segment_windows[
        segment_windows["Segment No"].isin(selected_numbers)
    ].copy().sort_values("Segment No").reset_index(drop=True)

    if selected_rows.empty:
        raise ValueError("No segments found in selected list.")

    return selected_rows


def concat_windows(source_df: pd.DataFrame, windows: list[tuple]) -> pd.DataFrame:
    parts = []

    for start_time, end_time in windows:
        part = slice_track_by_time(source_df, start_time, end_time)
        if not part.empty:
            parts.append(part)

    if not parts:
        return pd.DataFrame(columns=source_df.columns)

    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values("DateTime").reset_index(drop=True)
    return out


def get_window_parts(source_df: pd.DataFrame, windows: list[tuple], ids: list[int]) -> list[pd.DataFrame]:
    parts = []

    for (start_time, end_time), item_id in zip(windows, ids):
        part = slice_track_by_time(source_df, start_time, end_time)
        if not part.empty:
            part = part.sort_values("DateTime").reset_index(drop=True).copy()
            part["Part_ID"] = item_id
            parts.append(part)

    return parts


def build_title_suffix(selection_type: str, selected_mode: str, start_segment=None, end_segment=None, selected_segments=None) -> str:
    if selection_type == "Single":
        return f"Segment {start_segment} - {selected_mode}"
    if selection_type == "Range":
        return f"Segments {start_segment} to {end_segment} - {selected_mode}"
    if selection_type == "Multiple":
        selected_str = ", ".join(str(x) for x in selected_segments)
        return f"Segments {selected_str} - {selected_mode}"
    raise ValueError(f"Unknown selection type: {selection_type}")


def build_aggregate_metrics(window_parts: list[pd.DataFrame], selected_df: pd.DataFrame, mode_label: str) -> dict:
    total_metrics = build_summary_metrics(selected_df)

    part_metrics = [build_summary_metrics(df) for df in window_parts if not df.empty]

    if part_metrics:
        avg_distance_km = sum(m["distance_km"] for m in part_metrics) / len(part_metrics)
        avg_duration_hr = sum(m["duration_hr"] for m in part_metrics) / len(part_metrics)
    else:
        avg_distance_km = 0.0
        avg_duration_hr = 0.0

    return {
        "total_metrics": total_metrics,
        "avg_distance_km": avg_distance_km,
        "avg_duration_hr": avg_duration_hr,
        "mode_label": mode_label,
    }


def build_pdf_report(figures: list[tuple[str, go.Figure]]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    page_w, page_h = landscape(A4)

    for title, fig in figures:
        img_bytes = fig.to_image(format="png", scale=2)
        img = ImageReader(io.BytesIO(img_bytes))

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(36, page_h - 28, title)

        margin_x = 36
        margin_bottom = 28
        margin_top = 56

        max_w = page_w - (2 * margin_x)
        max_h = page_h - margin_top - margin_bottom

        iw, ih = img.getSize()
        scale = min(max_w / iw, max_h / ih)

        draw_w = iw * scale
        draw_h = ih * scale

        x = (page_w - draw_w) / 2
        y = margin_bottom

        pdf.drawImage(
            img,
            x,
            y,
            width=draw_w,
            height=draw_h,
            preserveAspectRatio=True,
            mask="auto",
        )
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def get_report_filename(selection_type: str, selected_mode: str, start_segment=None, end_segment=None, selected_segments=None) -> str:
    mode_slug = selected_mode.lower().replace(" ", "_")

    if selection_type == "Single":
        base = f"segment_{start_segment}_{mode_slug}"
    elif selection_type == "Range":
        base = f"segments_{start_segment}_to_{end_segment}_{mode_slug}"
    else:
        joined = "_".join(str(x) for x in selected_segments)
        base = f"segments_{joined}_{mode_slug}"

    return f"{base}_report.pdf"


# -----------------------------
# Load base data
# -----------------------------
try:
    if st.session_state.segment_source_df is None:
        st.session_state.segment_source_df = get_database()

    if st.session_state.segment_windows is None:
        st.session_state.segment_windows = get_segment_windows()

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

if st.session_state.segment_source_df.empty:
    st.error("The database is empty.")
    st.stop()

if st.session_state.segment_windows is None or st.session_state.segment_windows.empty:
    st.warning("No complete segments available. A segment requires a sequence followed by a next sequence.")
    st.stop()


# -----------------------------
# Sidebar
# -----------------------------
if st.sidebar.button("Refresh plots"):
    st.session_state.segment_windows = get_segment_windows()
    st.session_state.segment_plot_cache = None

segment_numbers = sorted(
    st.session_state.segment_windows["Segment No"].astype(int).tolist(),
    reverse=True
)

selection_type = st.sidebar.radio(
    "Selection type",
    options=["Single", "Range", "Multiple"],
    key="segment_selection_type",
)

selected_mode = st.sidebar.radio(
    "Display mode",
    options=["Complete segment", "Sequence only", "Line change only"],
    key="selected_segment_mode",
)

selected_segments = None
start_segment = None
end_segment = None

if selection_type == "Single":
    start_segment = st.sidebar.selectbox(
        "Select segment",
        options=segment_numbers,
        key="selected_segment_number",
    )
    end_segment = start_segment

elif selection_type == "Range":
    start_segment = st.sidebar.selectbox(
        "Start segment",
        options=sorted(segment_numbers),
        key="selected_segment_start_range",
    )

    valid_end_options = [n for n in sorted(segment_numbers) if n >= start_segment]

    end_segment = st.sidebar.selectbox(
        "End segment",
        options=valid_end_options,
        key="selected_segment_end_range",
    )

else:
    selected_segments = st.sidebar.multiselect(
        "Select segments",
        options=sorted(segment_numbers),
        default=[sorted(segment_numbers)[0]] if segment_numbers else [],
        key="selected_segments_multiple",
    )

    if not selected_segments:
        st.warning("Please select at least one segment.")
        st.stop()

    selected_segments = sorted(selected_segments)


# -----------------------------
# Build selected plot
# -----------------------------
cache_key = (
    selection_type,
    tuple(selected_segments) if selected_segments is not None else None,
    start_segment,
    end_segment,
    selected_mode,
)

needs_refresh = (
    st.session_state.segment_plot_cache is None
    or st.session_state.segment_plot_cache.get("cache_key") != cache_key
)

if needs_refresh:
    source_df = st.session_state.segment_source_df
    segment_windows = st.session_state.segment_windows

    if selection_type == "Single":
        rows = get_selected_rows_by_range(segment_windows, start_segment, end_segment)
    elif selection_type == "Range":
        rows = get_selected_rows_by_range(segment_windows, start_segment, end_segment)
    else:
        rows = get_selected_rows_by_list(segment_windows, selected_segments)

    title_suffix = build_title_suffix(
        selection_type=selection_type,
        selected_mode=selected_mode,
        start_segment=start_segment,
        end_segment=end_segment,
        selected_segments=selected_segments,
    )

    if selected_mode == "Complete segment":
        seq_windows = [(row["Sequence Start"], row["Sequence End"]) for _, row in rows.iterrows()]
        turn_windows = [(row["Turn Start"], row["Turn End"]) for _, row in rows.iterrows()]
        seq_ids = rows["Segment No"].astype(int).tolist()
        turn_ids = rows["Segment No"].astype(int).tolist()

        seq_parts = get_window_parts(source_df, seq_windows, seq_ids)
        turn_parts = get_window_parts(source_df, turn_windows, turn_ids)

        seq_df = concat_windows(source_df, seq_windows)
        turn_df = concat_windows(source_df, turn_windows)

        selected_df = pd.concat([seq_df, turn_df], ignore_index=True).sort_values("DateTime").reset_index(drop=True)

        if selected_df.empty or len(selected_df) < 2:
            st.warning("No sufficient data found for the selected segments and mode.")
            st.stop()

        metrics = build_summary_metrics(selected_df)
        seq_metrics = build_summary_metrics(seq_df)
        turn_metrics = build_summary_metrics(turn_df)

        fig_track = build_track_figure(
            title=title_suffix,
            metrics=metrics,
            mode=selected_mode,
            seq_parts=seq_parts,
            turn_parts=turn_parts,
            segment_metrics=metrics,
            seq_metrics=seq_metrics,
            turn_metrics=turn_metrics,
        )

        combined_speed = selected_df["Bottom Speed"].dropna()
        x_min = float(combined_speed.min()) if not combined_speed.empty else 0.0
        x_max = float(combined_speed.max()) if not combined_speed.empty else 1.0

        fig_speed_online = build_speed_histogram(
            df=seq_df,
            title=f"Speed distribution - {title_suffix} - Sequence",
            color=ONLINE_COLOR,
            x_min=x_min,
            x_max=x_max,
            n_bins=30,
            height=390,
        )

        fig_speed_offline = build_speed_histogram(
            df=turn_df,
            title=f"Speed distribution - {title_suffix} - Line change",
            color=OFFLINE_COLOR,
            x_min=x_min,
            x_max=x_max,
            n_bins=30,
            height=390,
        )

        st.session_state.segment_plot_cache = {
            "cache_key": cache_key,
            "fig_track": fig_track,
            "fig_speed_mode": "split",
            "fig_speed_online": fig_speed_online,
            "fig_speed_offline": fig_speed_offline,
            "n_points_full": len(selected_df),
            "n_points_plot": sum(len(df) for df in seq_parts) + sum(len(df) for df in turn_parts),
            "report_title": title_suffix,
        }

    elif selected_mode == "Sequence only":
        seq_windows = [(row["Sequence Start"], row["Sequence End"]) for _, row in rows.iterrows()]
        seq_ids = rows["Segment No"].astype(int).tolist()
        window_parts = get_window_parts(source_df, seq_windows, seq_ids)
        selected_df = concat_windows(source_df, seq_windows)

        if selected_df.empty or len(selected_df) < 2:
            st.warning("No sufficient data found for the selected segments and mode.")
            st.stop()

        metrics = build_summary_metrics(selected_df)

        aggregate_table = None
        if selection_type in ["Range", "Multiple"]:
            aggregate_table = build_aggregate_metrics(
                window_parts=window_parts,
                selected_df=selected_df,
                mode_label="Sequence",
            )

        fig_track = build_track_figure(
            title=title_suffix,
            metrics=metrics,
            mode=selected_mode,
            window_parts=window_parts,
            aggregate_table=aggregate_table,
        )

        fig_speed = build_speed_histogram(
            df=selected_df,
            title=f"Speed distribution - {title_suffix}",
            color=ONLINE_COLOR,
            height=800,
        )

        st.session_state.segment_plot_cache = {
            "cache_key": cache_key,
            "fig_track": fig_track,
            "fig_speed_mode": "single",
            "fig_speed": fig_speed,
            "n_points_full": len(selected_df),
            "n_points_plot": sum(len(df) for df in window_parts),
            "report_title": title_suffix,
        }

    elif selected_mode == "Line change only":
        turn_windows = [(row["Turn Start"], row["Turn End"]) for _, row in rows.iterrows()]
        turn_ids = rows["Segment No"].astype(int).tolist()
        window_parts = get_window_parts(source_df, turn_windows, turn_ids)
        selected_df = concat_windows(source_df, turn_windows)

        if selected_df.empty or len(selected_df) < 2:
            st.warning("No sufficient data found for the selected segments and mode.")
            st.stop()

        metrics = build_summary_metrics(selected_df)

        aggregate_table = None
        if selection_type in ["Range", "Multiple"]:
            aggregate_table = build_aggregate_metrics(
                window_parts=window_parts,
                selected_df=selected_df,
                mode_label="Line change",
            )

        fig_track = build_track_figure(
            title=title_suffix,
            metrics=metrics,
            mode=selected_mode,
            window_parts=window_parts,
            aggregate_table=aggregate_table,
        )

        fig_speed = build_speed_histogram(
            df=selected_df,
            title=f"Speed distribution - {title_suffix}",
            color=OFFLINE_COLOR,
            height=800,
        )

        st.session_state.segment_plot_cache = {
            "cache_key": cache_key,
            "fig_track": fig_track,
            "fig_speed_mode": "single",
            "fig_speed": fig_speed,
            "n_points_full": len(selected_df),
            "n_points_plot": sum(len(df) for df in window_parts),
            "report_title": title_suffix,
        }


# -----------------------------
# Display
# -----------------------------
result = st.session_state.segment_plot_cache

st.caption(
    f"Showing {result['n_points_plot']:,} plotted points "
    f"from {result['n_points_full']:,} total points."
)

col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(result["fig_track"], theme=None, use_container_width=True)

with col2:
    if result["fig_speed_mode"] == "split":
        st.plotly_chart(result["fig_speed_online"], theme=None, use_container_width=True)
        st.plotly_chart(result["fig_speed_offline"], theme=None, use_container_width=True)
    else:
        st.plotly_chart(result["fig_speed"], theme=None, use_container_width=True)


# -----------------------------
# PDF report
# -----------------------------
if result["fig_speed_mode"] == "split":
    report_figures = [
        (f"{result['report_title']} - Track", result["fig_track"]),
        (f"{result['report_title']} - Sequence speed", result["fig_speed_online"]),
        (f"{result['report_title']} - Line change speed", result["fig_speed_offline"]),
    ]
else:
    report_figures = [
        (f"{result['report_title']} - Track", result["fig_track"]),
        (f"{result['report_title']} - Speed", result["fig_speed"]),
    ]

report_bytes = build_pdf_report(report_figures)

report_filename = get_report_filename(
    selection_type=selection_type,
    selected_mode=selected_mode,
    start_segment=start_segment,
    end_segment=end_segment,
    selected_segments=selected_segments,
)

st.download_button(
    label="Print report",
    data=report_bytes,
    file_name=report_filename,
    mime="application/pdf",
)