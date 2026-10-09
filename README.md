# SurvMon 🌊

### Survey Vessel Monitoring — Streamlit Application
### Release Version 1.0

A Streamlit application for analyzing and visualizing marine survey vessel movements, operational segments, directional performance, and survey statistics. Built around a central database workflow, SurvMon processes vessel position data exported from ORCA to help review survey performance.

---

## Features

- 🗃️ **Database Management** — Combine daily vessel CSV exports into one master database with automatic backup and metadata tracking
- 🗺️ **Daily Track Visualization** — Interactive vessel track plots with online/offline classification and speed distributions
- 📐 **Segment Analysis** — Inspect complete segments, sequences, and line changes using single, range, or multiple selections
- 🧭 **Directional Analysis** — Compare sequences and line changes by heading direction, with shapefile export
- 📊 **Survey Overview** — Daily distance summaries and daily and weekly speed comparisons across the available survey data

---

## Project Structure

```text
repo-survMon/
│
├── Start.py                        # Application entry point; displays README.md
├── orca-web.csv                    # ORCA Web sequence export
├── requirements.txt                # Python dependencies
├── README.md                       # Shared GitHub and dashboard documentation
│
├── utils/
│   ├── __init__.py
│   └── data_loader.py              # Shared data loading and processing functions
│
├── pages/
│   ├── 1_Database_manager.py       # Database builder and file manager
│   ├── 2_Daily_analysis.py         # Daily vessel track analysis
│   ├── 3_Segment_analysis.py       # Segment, sequence and line change analysis
│   ├── 4_Directional_analysis.py   # Directional performance comparison
│   └── 5_Survey_overview.py        # Daily and weekly survey statistics
│
└── 24hrVesselPosition/             # Daily vessel position CSV files and backups
    ├── database.csv                # Master database (auto-generated)
    └── database_meta.json          # Database metadata (auto-generated)
```

---

## Installation

### Prerequisites

- Python 3.10 or newer
- pip
- Conda, if using the environment setup below

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/rdallagnolo/repo-survMon.git
   cd repo-survMon
   ```

2. **Create and activate a Conda environment:**

   ```bash
   conda create -n survmon python=3.12 pip
   conda activate survmon
   ```

   If you already have a suitable environment, activate it instead.

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create the vessel position data folder:**

   ```bash
   mkdir -p 24hrVesselPosition
   ```

5. **Launch the dashboard:**

   ```bash
   streamlit run Start.py
   ```

   Open the local URL shown in the terminal, usually `http://localhost:8501`.

### Subsequent Launches

From the project folder, activate your environment and start Streamlit:

```bash
conda activate survmon
streamlit run Start.py
```

---

## Input Data

### Vessel Position Files

Exported from the 24-hour databases in the Orca OQC application. From the main+NRT tree, select V1 and export Easting, Northing and Bottom Speed.

Preserve the exported column names:

| Column | Description |
|---|---|
| `Unnamed: 0` | Unix timestamp |
| `Unnamed: 1` | Time in HH:MM:SS format |
| `V1 Easting` | Vessel easting coordinate in metres |
| `V1 Northing` | Vessel northing coordinate in metres |
| `V1 Bottom Speed` | Vessel speed in m/s |

### ORCA Web File (`orca-web.csv`)

Exported from OrcaWeb by saving all sequences to CSV.

The main analysis fields are:

| Column | Description |
|---|---|
| `Seq No` | Sequence number |
| `Line Name` | Survey line identifier |
| `Heading` | Compass heading in degrees |
| `SOL Date` | Start of line date |
| `SOL Time` | Start of line time |
| `EOL Date` | End of line date |
| `EOL Time` | End of line time |

Preserve the complete export. The loader also requires these columns:

- `Type`
- `Incr`
- `Orca Status`
- `NRT Status`
- `Reprocess`
- `Start of Line (FGSP)`
- `End of Line (LGSP)`

The loader accepts the original exported date/time column names `Unnamed: 9`, `Unnamed: 10`, `Unnamed: 12` and `Unnamed: 13`, renaming them to the SOL/EOL date and time fields.

---

## Workflow

1. Place daily vessel position CSV files into `24hrVesselPosition/`.
2. Place `orca-web.csv` in the project root.
3. Open **Database Manager** and select **Update database** when required.
4. Use the analysis pages to explore the data.
5. After changing input files or rebuilding the database, stop and restart Streamlit to ensure the analysis pages load the updated data.

---

## Application Pages

### 1. 🗃️ Database Manager

Central hub for managing the vessel position database.

- Scans `24hrVesselPosition/` for daily CSV files and combines them into a single `database.csv`
- Detects source-file changes using hash-based comparison
- Creates a timestamped backup of the existing database before rebuilding it
- Tracks build metadata in `database_meta.json`
- Displays source-file information, database row counts and data coverage
- Displays the ORCA Web sequence table for reference

### 2. 🗺️ Daily Analysis

Day-by-day vessel track inspection.

- Displays the vessel track for a selected day, colour-coded by online and offline status
- Shows key metrics: total time, total distance, online/offline distance and average speeds
- Displays separate speed distribution histograms for online and offline periods

Online periods correspond to sequence SOL/EOL windows. Positions outside these windows are classified as offline.

### 3. 📐 Segment Analysis

Detailed analysis of survey segments, with flexible selection.

**Segment definition:**

- **Sequence** — SOL to EOL
- **Line change** — EOL to the next sequence's SOL
- **Complete segment** — SOL to the next sequence's SOL, combining the sequence and following line change

**Display modes:**

- Complete segment — shows the sequence and line change in a combined track plot
- Sequence only — isolates the sequence portions
- Line change only — isolates the repositioning portions

**Selection modes:**

- Single — inspect one segment at a time
- Range — select a contiguous range of segment numbers
- Multiple — pick any combination of segments

Each view includes a vessel track plot, speed distribution histogram(s), and summary metrics.

A segment requires a following sequence to define its end. The final sequence is therefore excluded from this page.

### 4. 🧭 Directional Analysis

Compares survey performance by heading direction.

- Classifies sequences and line changes into eight directions: N, NE, E, SE, S, SW, W and NW
- Groups line changes using the preceding sequence's heading
- Displays a combined track plot and separate sequence and line-change track plots
- Displays per-direction speed histograms, speed boxplots and average-speed trends
- Provides summary tables by direction
- Exports combined tracks as a **shapefile ZIP** for use in GIS applications

This page processes all available sequence and line-change windows. Plots and the shapefile export are built on first load or when **Refresh data** is selected.

The shapefile ZIP contains `.shp`, `.shx`, `.dbf` and `.cpg` files. Coordinates retain the source Easting/Northing system; no projection file is included.

### 5. 📊 Survey Overview

High-level statistics across the available survey data.

- Key metrics: days represented in the daily distance summary, total online distance and total offline distance
- Daily stacked bar chart — online vs offline distance travelled
- Daily line chart — average online vs offline speed
- Weekly line chart — average online vs offline speed aggregated by week

---

## Technical Notes

- **Speed** is converted from m/s to knots for display.
- **Distance** is computed from successive Easting/Northing coordinates and reported in kilometres. Coordinates must be in metres and use a consistent projected coordinate system.
- **Online/offline classification** is based on sequence windows derived from the ORCA Web file.
- **Caching** uses Streamlit `@st.cache_data` and session state. Analysis pages can retain previously loaded data after input files change. Restart Streamlit to reliably reload updated inputs.
- **Plot thinning** is applied to large tracks to reduce rendering time.
- **Documentation** is maintained in `README.md`, which is also displayed by `Start.py`.

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit >= 1.30` | Web application framework |
| `pandas >= 2.0` | Data manipulation |
| `numpy >= 1.24` | Numerical computing |
| `plotly >= 5.18` | Interactive visualizations |
| `pyshp >= 2.3` | Shapefile export |

---

*Happy Surveying!* 🌊⚓