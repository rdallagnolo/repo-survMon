from __future__ import annotations

from pathlib import Path
from typing import Iterable
import pandas as pd
import numpy as np

DEFAULT_DB_PATH = Path("24hrVesselPosition") / "database.csv"
DEFAULT_ORCA_PATH = Path("orca-web.csv")

RAW_DB_REQUIRED_COLUMNS = [
    "Unnamed: 0",
    "Unnamed: 1",
    "V1 Easting",
    "V1 Northing",
    "V1 Bottom Speed",
]

ORCA_REQUIRED_COLUMNS = [
    "Seq No",
    "Line Name",
    "Heading",
    "Type",
    "Incr",
    "Orca Status",
    "NRT Status",
    "Reprocess",
    "Start of Line (FGSP)",
    "SOL Date",
    "SOL Time",
    "End of Line (LGSP)",
    "EOL Date",
    "EOL Time",
]

KNOTS_PER_MPS = 1.943844
KM_PER_NM = 1.852


def validate_columns(df: pd.DataFrame, required_columns: Iterable[str], source_name: str) -> None:
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"{source_name} is missing required columns: {', '.join(missing)}")


def compute_distance_km(
    df: pd.DataFrame,
    easting_col: str = "Easting",
    northing_col: str = "Northing",
    datetime_col: str = "DateTime",
) -> float:
    if df.empty or len(df) < 2:
        return 0.0

    validate_columns(df, [easting_col, northing_col, datetime_col], "Distance input dataframe")

    working = (
        df[[datetime_col, easting_col, northing_col]]
        .copy()
        .sort_values(datetime_col)
        .reset_index(drop=True)
    )

    working[easting_col] = pd.to_numeric(working[easting_col], errors="coerce")
    working[northing_col] = pd.to_numeric(working[northing_col], errors="coerce")
    working = working.dropna(subset=[easting_col, northing_col])

    if len(working) < 2:
        return 0.0

    dist_m = np.sqrt(
        (working[easting_col] - working[easting_col].shift()) ** 2 +
        (working[northing_col] - working[northing_col].shift()) ** 2
    )
    dist_m.iloc[0] = 0.0

    return float(dist_m.sum() / 1000.0)


def compute_duration_hours(df: pd.DataFrame, datetime_col: str = "DateTime") -> float:
    if df.empty or len(df) < 2:
        return 0.0

    validate_columns(df, [datetime_col], "Duration input dataframe")

    working = df[[datetime_col]].copy().sort_values(datetime_col).reset_index(drop=True)
    return float((working[datetime_col].iloc[-1] - working[datetime_col].iloc[0]).total_seconds() / 3600.0)


def expected_distance_from_speed_km(avg_speed_knots: float, duration_hours: float) -> float:
    if pd.isna(avg_speed_knots) or pd.isna(duration_hours):
        return 0.0
    return float(avg_speed_knots * duration_hours * KM_PER_NM)


def load_raw_database(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    df = pd.read_csv(db_path)
    validate_columns(df, RAW_DB_REQUIRED_COLUMNS, f"Database file '{db_path}'")
    return df


def clean_database(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, RAW_DB_REQUIRED_COLUMNS, "Raw database dataframe")

    out = df.copy()

    out["Unnamed: 1"] = out["Unnamed: 1"].astype(str).str.split(".").str[0]
    out["Time"] = pd.to_datetime(out["Unnamed: 1"], format="%H:%M:%S", errors="coerce").dt.time
    out["Unnamed: 0"] = pd.to_datetime(out["Unnamed: 0"], unit="s", errors="coerce")
    out["Date"] = out["Unnamed: 0"].dt.strftime("%d/%m/%Y")

    out = out[
        ["Unnamed: 0", "Date", "Time", "V1 Easting", "V1 Northing", "V1 Bottom Speed"]
    ].copy()

    out.columns = ["DateTime", "Date", "Time", "Easting", "Northing", "Bottom Speed"]

    out["Bottom Speed"] = pd.to_numeric(out["Bottom Speed"], errors="coerce") * KNOTS_PER_MPS
    out["Easting"] = pd.to_numeric(out["Easting"], errors="coerce")
    out["Northing"] = pd.to_numeric(out["Northing"], errors="coerce")

    out = out.dropna(subset=["DateTime", "Easting", "Northing", "Bottom Speed"]).copy()
    out = out.sort_values("DateTime").reset_index(drop=True)

    return out


def load_database_clean(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    raw = load_raw_database(db_path)
    return clean_database(raw)


def load_orca_web(orca_path: str | Path = DEFAULT_ORCA_PATH) -> pd.DataFrame:
    orca_path = Path(orca_path)

    if not orca_path.exists():
        raise FileNotFoundError(f"ORCA file not found: {orca_path}")

    df = pd.read_csv(orca_path)

    rename_map = {}

    if "Unnamed: 9" in df.columns:
        rename_map["Unnamed: 9"] = "SOL Date"
    if "Unnamed: 10" in df.columns:
        rename_map["Unnamed: 10"] = "SOL Time"
    if "Unnamed: 12" in df.columns:
        rename_map["Unnamed: 12"] = "EOL Date"
    if "Unnamed: 13" in df.columns:
        rename_map["Unnamed: 13"] = "EOL Time"

    df = df.rename(columns=rename_map)

    validate_columns(df, ORCA_REQUIRED_COLUMNS, f"ORCA file '{orca_path}'")
    return df.copy()


def clean_orca_web(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df, ORCA_REQUIRED_COLUMNS, "ORCA dataframe")

    out = df.copy()
    out["Seq No"] = pd.to_numeric(out["Seq No"], errors="coerce")

    out["SOL DateTime"] = pd.to_datetime(
        out["SOL Date"].astype(str) + " " + out["SOL Time"].astype(str),
        format="%d-%b-%Y %H:%M:%S",
        errors="coerce",
    )

    out["EOL DateTime"] = pd.to_datetime(
        out["EOL Date"].astype(str) + " " + out["EOL Time"].astype(str),
        format="%d-%b-%Y %H:%M:%S",
        errors="coerce",
    )

    out = out.dropna(subset=["Seq No", "SOL DateTime", "EOL DateTime"]).copy()
    out["Seq No"] = out["Seq No"].astype(int)
    out = out.sort_values("Seq No").reset_index(drop=True)

    return out


def load_orca_web_clean(orca_path: str | Path = DEFAULT_ORCA_PATH) -> pd.DataFrame:
    raw = load_orca_web(orca_path)
    return clean_orca_web(raw)


def split_database_by_day(df: pd.DataFrame) -> dict[pd.Timestamp, pd.DataFrame]:
    validate_columns(df, ["DateTime"], "Daily split dataframe")

    temp = df.copy().sort_values("DateTime").reset_index(drop=True)
    temp["Day"] = pd.to_datetime(temp["DateTime"]).dt.date

    daily_map: dict[pd.Timestamp, pd.DataFrame] = {}
    for day, group in temp.groupby("Day"):
        daily_map[pd.Timestamp(day)] = group.drop(columns=["Day"]).reset_index(drop=True)

    return daily_map


def build_sequence_windows(orca_df: pd.DataFrame) -> pd.DataFrame:
    required = ["Seq No", "Heading", "SOL DateTime", "EOL DateTime"]
    validate_columns(orca_df, required, "Clean ORCA dataframe")

    seq = orca_df[["Seq No", "Heading", "SOL DateTime", "EOL DateTime"]].copy()
    seq = seq.rename(
        columns={
            "Seq No": "Sequence No",
            "SOL DateTime": "Start",
            "EOL DateTime": "End",
        }
    )

    seq = seq.sort_values("Sequence No").reset_index(drop=True)
    return seq


#def build_turn_windows(orca_df: pd.DataFrame) -> pd.DataFrame:
#    required = ["Seq No", "Heading", "SOL DateTime", "EOL DateTime"]
#    validate_columns(orca_df, required, "Clean ORCA dataframe")
#
#    turns = orca_df[["Seq No", "Heading", "SOL DateTime", "EOL DateTime"]].copy()
#    turns = turns.sort_values("Seq No").reset_index(drop=True)
#
#    rows = []
#    for i in range(1, len(turns)):
#        prev_row = turns.iloc[i - 1]
#        curr_row = turns.iloc[i]
#
#        rows.append(
#            {
#                "Turn No": int(curr_row["Seq No"]),
#                "Start": prev_row["EOL DateTime"],
#                "End": curr_row["SOL DateTime"],
#                "Heading": prev_row["Heading"],
#            }
#        )
#
#    return pd.DataFrame(rows)


def slice_track_by_time(df: pd.DataFrame, start_time, end_time) -> pd.DataFrame:
    validate_columns(df, ["DateTime"], "Track slicing dataframe")

    start_time = pd.to_datetime(start_time)
    end_time = pd.to_datetime(end_time)

    sliced = df[(df["DateTime"] >= start_time) & (df["DateTime"] <= end_time)].copy()
    return sliced.sort_values("DateTime").reset_index(drop=True)


def build_summary_metrics(df: pd.DataFrame) -> dict[str, float | str]:
    if df.empty:
        return {
            "start": "",
            "end": "",
            "duration_hr": 0.0,
            "distance_km": 0.0,
            "avg_speed_knots": 0.0,
            "expected_distance_km": 0.0,
        }

    working = df.sort_values("DateTime").reset_index(drop=True)
    duration_hr = compute_duration_hours(working)
    avg_speed_knots = float(working["Bottom Speed"].mean())
    distance_km = compute_distance_km(working)
    expected_distance_km = expected_distance_from_speed_km(avg_speed_knots, duration_hr)

    return {
        "start": working["DateTime"].iloc[0].strftime("%Y-%m-%d %H:%M:%S"),
        "end": working["DateTime"].iloc[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "duration_hr": duration_hr,
        "distance_km": distance_km,
        "avg_speed_knots": avg_speed_knots,
        "expected_distance_km": expected_distance_km,
    }


def degrees_to_cardinal(degrees: float) -> str:
    degrees = degrees % 360
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    sector = int((degrees + 22.5) / 45) % 8
    return directions[sector]


def add_cardinal_direction(orca_df: pd.DataFrame, heading_col: str = "Heading") -> pd.DataFrame:
    out = orca_df.copy()

    numeric_heading = (
        out[heading_col]
        .astype(str)
        .str.replace(r"[^\d.]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )

    out["Cardinal_Direction"] = numeric_heading.apply(degrees_to_cardinal)
    return out

from pathlib import Path
import streamlit as st


# -----------------------------
# File signature (detect changes)
# -----------------------------
def _get_file_signature(path: str | Path) -> tuple:
    path = Path(path)

    if not path.exists():
        return (str(path), None, None)

    stat = path.stat()
    return (str(path), stat.st_mtime_ns, stat.st_size)


# -----------------------------
# Internal cached loader
# -----------------------------
@st.cache_data
def _cached_loader(_load_func, signature):
    path_str = signature[0]
    return _load_func(path_str)


# -----------------------------
# Public cached loaders
# -----------------------------
def load_database_cached(path: str | Path):
    signature = _get_file_signature(path)
    return _cached_loader(load_database_clean, signature)


def load_orca_cached(path: str | Path):
    signature = _get_file_signature(path)
    return _cached_loader(load_orca_web_clean, signature)