# SurvMon 🌊

### Survey Vessel Monitoring — Streamlit Application

A Streamlit application for analyzing and visualizing marine survey vessel movements, operational segments, directional performance, and survey statistics. Built around a central database workflow, SurvMon processes vessel position data exported from ORCA and turns it into actionable insights.

---

## Features

- 🗃️ **Database Management** — Combine daily vessel CSV exports into one master database with automatic backup and metadata tracking
- 🗺️ **Daily Track Visualization** — Interactive vessel track plots with online/offline classification and speed distributions
- 📐 **Segment Analysis** — Inspect complete segments, sequences, and line changes individually with PDF report export
- 🧭 **Directional Analysis** — Compare sequences and line changes by cardinal heading direction, with shapefile export
- 📊 **Survey Overview** — Daily and weekly distance and speed summaries across the full survey campaign

---

## Project Structure

```
repo-survMon/
│
├── Start.py                        # Application entry point and documentation
├── orca-web.csv                    # ORCA Web sequence export
├── requirements.txt                # Python dependencies
├── README.md                       # Project documentation
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
└── 24hrVesselPosition/             # Folder for daily vessel position CSV files
    ├── database.csv                # Master database (auto-generated)
    └── database_meta.json          # Database metadata (auto-generated)
```

---

## Installation

### Prerequisites

- Python 3.8+
- pip

### Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:rdallagnolo/repo_survMon.git
   cd repo-survMon
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create the vessel position data folder:**
   ```bash
   mkdir 24hrVesselPosition
   ```

---

## Input Data

### Vessel Position Files
Exported from the 24-hour databases in the Orca OQC application. From the main+NRT tree, select V1 and export Easting, Northing and Bottom Speed.

Each daily CSV file will contain:

| Column | Description |
|---|---|
| `Unnamed: 0` | Unix timestamp |
| `Unnamed: 1` | Time in HH:MM:SS format |
| `V1 Easting` | Vessel easting coordinate |
| `V1 Northing` | Vessel northing coordinate |
| `V1 Bottom Speed` | Vessel speed in m/s |

### ORCA Web File (`orca-web.csv`)
Exported from OrcaWeb by saving all sequences to CSV.

| Column | Description |
|---|---|
| `Seq No` | Sequence number |
| `Line Name` | Survey line identifier |
| `Heading` | Compass heading in degrees |
| `SOL Date` | Start of line date |
| `SOL Time` | Start of line time |
| `EOL Date` | End of line date |
| `EOL Time` | End of line time |

---

## Workflow

```
1. Place daily vessel position CSV files into 24hrVesselPosition/
2. Place orca-web.csv in the project root
3. Open Database Manager → build or refresh database.csv
4. Use the analysis pages to explore the data
```

---

## Application Pages

### 1. 🗃️ Database Manager
Central hub for managing the vessel position database.
- Scans `24hrVesselPosition/` for daily CSV files and combines them into a single `database.csv`
- Detects file changes automatically using hash-based comparison
- Creates a timestamped backup of the existing database before each rebuild
- Tracks build metadata (source files, timestamps) in `database_meta.json`
- Displays the ORCA Web sequence table for reference

### 2. 🗺️ Daily Analysis
Day-by-day vessel track inspection.
- Displays vessel track for a selected day, colour-coded by online (sequence) and offline (line change) status
- Shows key metrics: total time, total distance, online/offline distance and average speeds
- Separate speed distribution histograms for online and offline periods

### 3. 📐 Segment Analysis
Detailed analysis of survey segments, with flexible selection and PDF export.

**Segment definition:**
- **Sequence** — SOL to EOL (vessel actively on survey line)
- **Line change** — EOL to next SOL (vessel repositioning)
- **Complete segment** — SOL to next SOL (sequence + line change combined)

**Display modes:**
- Complete segment — shows sequence and line change in a single combined track plot
- Sequence only — isolates the active survey portions
- Line change only — isolates the repositioning portions

**Selection modes:**
- Single — inspect one segment at a time
- Range — select a contiguous range of segments
- Multiple — pick any combination of segments

Each view includes a vessel track plot, speed distribution histogram(s), and a summary metrics table. A **PDF report** can be exported for any selection and mode.

### 4. 🧭 Directional Analysis
Compares survey performance broken down by cardinal heading direction.
- Classifies sequences and line changes into cardinal directions (N, NE, E, SE, S, SW, W, NW)
- Combined track plot showing all sequences and line changes colour-coded by direction
- Per-direction speed histograms, speed boxplots, and average speed trend lines
- Summary table with count, average distance, average duration, and average speed per direction
- **Shapefile export** of all tracks for use in GIS applications

### 5. 📊 Survey Overview
High-level statistics across the full survey campaign.
- Key metrics: total survey days, total online distance, total offline distance
- Daily stacked bar chart — online vs offline distance travelled
- Daily line chart — average online vs offline speed
- Weekly line chart — average online vs offline speed aggregated by week

---

## Technical Notes

- **Speed** is stored in m/s and converted to knots for all displays
- **Distance** is computed from Easting/Northing coordinates in metres, reported in kilometres
- **Online/offline classification** is based on sequence windows derived from the ORCA Web file (SOL/EOL timestamps)
- **Caching** uses Streamlit `@st.cache_data` with file-hash awareness, so changes to `database.csv` or `orca-web.csv` are automatically detected
- **Plot thinning** is applied on large datasets to keep rendering responsive (configurable `MAX_PLOT_POINTS` per page)

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit >= 1.30` | Web application framework |
| `pandas >= 2.0` | Data manipulation |
| `numpy >= 1.24` | Numerical computing |
| `plotly >= 5.18` | Interactive visualizations |
| `pyshp >= 2.3` | Shapefile export |
| `reportlab >= 4.0` | PDF report generation |
| `kaleido >= 0.2.1` | Plotly static image export (used by reportlab) |

---

## License

This project is licensed under the MIT License.

---

*Happy Surveying!* 🌊⚓