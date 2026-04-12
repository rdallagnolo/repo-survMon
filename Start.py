import streamlit as st

st.set_page_config(
    page_title="Start page",
    page_icon=":eagle:",
    layout="centered",
    initial_sidebar_state="auto",
    menu_items=None,
)

start_text = """
# SurvMon app
## Monitoring your Survey performance

A Streamlit application for analyzing and visualizing survey vessel movements, operational segments, directional performance, and survey statistics.

This application processes vessel position data exported from ORCA and builds a workflow around one central database.

The app allows you to:

- combine daily vessel CSV files into one master database
- inspect vessel tracks day by day
- analyze operational segments:
  - complete segment
  - sequence only
  - line change only
- compare performance by direction
- review daily and weekly survey statistics

## Project structure

    repo-survMon/
    │
    ├── Start.py
    ├── orca-web.csv
    ├── requirements.txt
    ├── README.md
    │
    ├── utils/
    │   ├── __init__.py
    │   └── data_loader.py
    │
    ├── pages/
    │   ├── 1_Database_manager.py
    │   ├── 2_Daily_analysis.py
    │   ├── 3_Segment_analysis.py
    │   ├── 4_Directional_analysis.py
    │   └── 5_Survey_overview.py
    │
    └── 24hrVesselPosition/

## Input data

### Vessel position files
Data extracted from the 24 Hour databases in Orca OQC application.
From main+NRT tree, select V1 and elements Easting, Northing and Bottom Speed.

Export the csv file with will contain the following columns:
- `Unnamed: 0` → Unix timestamp
- `Unnamed: 1` → Time in HH:MM:SS format
- `V1 Easting`
- `V1 Northing`
- `V1 Bottom Speed`

### ORCA web dataframe
From OrcaWeb save all sequences to a csv file.
The dataframe will containthe following columns:
- `Seq No`
- `Line Name`
- `Heading`
- `SOL Date`
- `SOL Time`
- `EOL Date`
- `EOL Time`

## Workflow

1. Put exported daily CSV files into `24hrVesselPosition/`
2. Make sure `orca-web.csv` is in the project root
3. Open the Database Manager page and build or refresh `database.csv`
4. Use the analysis pages to explore:
   - daily vessel activity
   - segment performance
   - directional trends
   - survey overview statistics

## Page summary

### 1. Database manager
Builds and updates the central database from daily vessel exports.

### 2. Daily analysis
Displays daily vessel tracks and compares online and offline speed distributions.

### 3. Segment analysis
Displays:
- complete segment = sequence + line change
- sequence only
- line change only

Includes vessel track plots and speed distributions.

### 4. Directional analysis
Compares sequences and line changes by heading direction.

### 7. Survey overview
Summarizes daily and weekly online/offline distance and speed performance.

## Notes

- Speed is converted from m/s to knots
- Distance is computed from Easting/Northing coordinates
- Segment analysis is based on:
  - sequence = SOL to EOL
  - line change = EOL to next SOL
  - complete segment = SOL to next SOL
- Data loading uses file-aware caching, so updates to `database.csv` and `orca-web.csv` are automatically detected
"""

st.markdown(start_text)
st.write("v 3.0")