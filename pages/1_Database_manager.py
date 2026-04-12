import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.data_loader import load_orca_web

st.set_page_config(page_title="Database Builder", page_icon=":boat:", layout="wide")

FOLDER_PATH = Path("24hrVesselPosition")
DB_FILE = FOLDER_PATH / "database.csv"
DB_META_FILE = FOLDER_PATH / "database_meta.json"
ORCA_FILE = Path("orca-web.csv")


# -----------------------------
# Helpers
# -----------------------------
def list_daily_files() -> list[Path]:
    if not FOLDER_PATH.exists():
        return []

    return sorted(
        f for f in FOLDER_PATH.iterdir()
        if f.is_file()
        and f.suffix.lower() == ".csv"
        and f.name != "database.csv"
        and not f.name.startswith("database_")
    )


def get_files_hash(files: list[Path]) -> str:
    if not files:
        return ""

    file_info = []
    for f in files:
        stat = f.stat()
        file_info.append(f"{f.name}_{stat.st_mtime_ns}_{stat.st_size}")

    return "_".join(sorted(file_info))


def get_orca_hash() -> str:
    if not ORCA_FILE.exists():
        return ""

    stat = ORCA_FILE.stat()
    return f"{ORCA_FILE.name}_{stat.st_mtime_ns}_{stat.st_size}"


def quick_file_summary(files: list[Path]) -> pd.DataFrame:
    data = []
    for f in files:
        stat = f.stat()
        data.append(
            {
                "filename": f.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return pd.DataFrame(data)


def load_db_quick_info() -> dict | None:
    if not DB_FILE.exists():
        return None

    try:
        df = pd.read_csv(DB_FILE, usecols=["Unnamed: 0"])

        if df.empty:
            return {"rows": 0, "start": "", "end": ""}

        dt = pd.to_datetime(df["Unnamed: 0"], unit="s", errors="coerce").dropna()

        return {
            "rows": int(len(df)),
            "start": str(dt.min()) if not dt.empty else "",
            "end": str(dt.max()) if not dt.empty else "",
        }

    except Exception as e:
        st.error(f"Error reading database quick info: {e}")
        return None


def save_database_metadata(source_hash: str, source_files: list[Path]) -> None:
    payload = {
        "source_hash": source_hash,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_files": [f.name for f in source_files],
        "source_count": len(source_files),
    }
    DB_META_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_database_metadata() -> dict | None:
    if not DB_META_FILE.exists():
        return None

    try:
        return json.loads(DB_META_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def rebuild_database(files: list[Path], current_files_hash: str) -> bool:
    try:
        if DB_FILE.exists():
            backup_name = f"database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            backup_path = FOLDER_PATH / backup_name
            DB_FILE.rename(backup_path)
            st.sidebar.info(f"Old database backed up as: {backup_name}")

        dfs = []
        for f in files:
            try:
                df = pd.read_csv(f, skiprows=[1])
                dfs.append(df)
            except Exception as e:
                st.error(f"Error reading file {f.name}: {e}")

        if not dfs:
            st.error("No valid files found to build database")
            return False

        combined_df = pd.concat(dfs, ignore_index=True)
        combined_df.to_csv(DB_FILE, index=False)
        save_database_metadata(current_files_hash, files)

        return True

    except Exception as e:
        st.error(f"Error rebuilding database: {e}")
        return False


@st.cache_data
def get_orca_table():
    return load_orca_web(ORCA_FILE)


# -----------------------------
# Session state
# -----------------------------
for key in [
    "db_daily_files",
    "db_files_hash",
    "db_file_summary",
    "db_quick_info",
    "db_meta",
    "db_up_to_date",
    "db_orca_web",
]:
    if key not in st.session_state:
        st.session_state[key] = None


# -----------------------------
# Main logic
# -----------------------------
if not FOLDER_PATH.exists():
    st.warning("Folder '24hrVesselPosition' not found.")
    st.stop()

current_files = list_daily_files()

# 🔥 UPDATED HASH (includes ORCA)
current_files_hash = get_files_hash(current_files) + "_" + get_orca_hash()

need_refresh = (
    st.session_state.db_daily_files is None
    or st.session_state.db_files_hash != current_files_hash
)

if st.sidebar.button("Refresh data"):
    need_refresh = True

    # 🔥 Clear ORCA cache
    get_orca_table.clear()

    st.session_state.db_daily_files = None
    st.session_state.db_files_hash = None
    st.session_state.db_file_summary = None
    st.session_state.db_quick_info = None
    st.session_state.db_meta = None
    st.session_state.db_up_to_date = None
    st.session_state.db_orca_web = None


if not current_files:
    st.warning("No CSV files found in folder.")
    st.session_state.db_daily_files = []
    st.session_state.db_file_summary = pd.DataFrame()
    st.session_state.db_quick_info = None
    st.session_state.db_meta = None
    st.session_state.db_up_to_date = False

else:
    if need_refresh:
        with st.spinner("Refreshing file status..."):
            st.session_state.db_daily_files = current_files
            st.session_state.db_files_hash = current_files_hash
            st.session_state.db_file_summary = quick_file_summary(current_files)
            st.session_state.db_quick_info = load_db_quick_info()
            st.session_state.db_meta = load_database_metadata()

            meta = st.session_state.db_meta
            st.session_state.db_up_to_date = (
                DB_FILE.exists()
                and meta is not None
                and meta.get("source_hash") == current_files_hash
            )

    if st.session_state.db_orca_web is None:
        try:
            st.session_state.db_orca_web = get_orca_table()
        except Exception as e:
            st.error(f"Error loading orca-web.csv: {e}")
            st.session_state.db_orca_web = None


# -----------------------------
# Sidebar
# -----------------------------
daily_files = st.session_state.db_daily_files
summary_df = st.session_state.db_file_summary
db_info = st.session_state.db_quick_info
db_meta = st.session_state.db_meta
db_up_to_date = st.session_state.db_up_to_date

with st.sidebar.expander("Files info"):
    if summary_df is not None and not summary_df.empty:
        st.code(f"Files: {len(daily_files)}")
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.write("No file info available")

with st.sidebar.expander("Database info"):
    if db_info is not None:
        st.code(f"Rows: {db_info['rows']:,}")
        st.code(f"Start: {db_info['start']}")
        st.code(f"End: {db_info['end']}")
    else:
        st.write("No database")

    if db_meta is not None:
        st.caption(f"Last built: {db_meta.get('updated_at', 'unknown')}")
        st.caption(f"Source files: {db_meta.get('source_count', 0)}")

st.sidebar.markdown("---")

if db_up_to_date:
    st.sidebar.success("Database up to date")
else:
    if DB_FILE.exists():
        st.sidebar.warning("Database needs update")
    else:
        st.sidebar.error("No database found")

    if st.sidebar.button("Update database"):
        with st.spinner("Updating database..."):
            success = rebuild_database(daily_files, current_files_hash)

            if success:
                st.sidebar.success("Updated successfully")
                st.session_state.db_quick_info = load_db_quick_info()
                st.session_state.db_meta = load_database_metadata()
                st.session_state.db_up_to_date = True
                st.rerun()
            else:
                st.sidebar.error("Update failed")


# -----------------------------
# Main content
# -----------------------------
st.header("Database Manager")
st.subheader("Central hub for vessel data")

if st.session_state.db_orca_web is not None:
    with st.expander("ORCA Web table", expanded=True):
        st.dataframe(st.session_state.db_orca_web, use_container_width=True)
else:
    st.info("orca-web.csv not loaded")

if not current_files:
    st.info("Add CSV files to start")
else:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Files", len(daily_files))

    with col2:
        if summary_df is not None and not summary_df.empty:
            total_kb = summary_df["size_kb"].sum()
            st.metric("Total file size", f"{total_kb:,.1f} KB")
        else:
            st.metric("Total file size", "0 KB")

    with col3:
        if db_info is not None:
            st.metric("Database rows", f"{db_info['rows']:,}")
        else:
            st.metric("Database rows", "No DB")

    st.markdown("---")

    if db_up_to_date:
        st.success("Database ready")
    elif DB_FILE.exists():
        st.warning("Database needs update")
    else:
        st.error("No database found")

    st.info(f"Data coverage: {len(daily_files)} daily files available")