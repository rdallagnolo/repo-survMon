# Marine Survey Vessel Tracking System 🚢

A comprehensive Streamlit application for analyzing and visualizing marine survey vessel movements, track performance, and operational statistics.

## Overview

This application processes vessel position data from ORCA marine survey systems, providing detailed analysis of vessel tracks, survey sequences, turn maneuvers, and performance statistics. The system is designed for marine survey operators, and researchers who need to analyze vessel behavior during survey operations.

## Features

- 📊 **Real-time Data Processing**: Automatic conversion and processing of vessel position data
- 🗺️ **Interactive Track Visualization**: Dynamic plotting of vessel movements with Plotly
- 📈 **Performance Analytics**: Speed distribution analysis and statistical summaries
- 🧭 **Directional Analysis**: Cardinal direction conversion and directional performance comparison
- 📅 **Multi-temporal Analysis**: Daily, sequence, and turn-based track analysis
- 🔄 **Data Management**: Automated database building and file management
- ⚡ **Session State Caching**: Optimized performance with intelligent data caching

## Project Structure

```
repo-survMon/
│
├── README.md                           # Project documentation
├── requirements.txt                    # Python dependencies
├── Start.py                            # Main application entry point
│
├── pages/                              # Streamlit pages directory
│   ├── 1_Database_manager.py          # Main database management module
│   ├── 2_Daily_track.py               # Daily track analysis
│   ├── 3_Sequence_track.py            # Survey sequence analysis
│   ├── 4_Turn_track.py                # Turn maneuver analysis
│   ├── 5_Track_slicer.py              # Custom time-range analysis
│   └── 6_Stats.py                     # Statistics dashboard
│
├── orca-web.csv                        # ORCA survey configuration file
│
├── 24hrVesselPosition/                 # Raw vessel position data
│   ├── database.csv                    # Master database (auto-generated)
│   ├── daily_file_1.csv               # Daily position files
│   ├── daily_file_2.csv
│   └── ...
│
├── DailyTracks/                        # Generated daily track files
│   ├── 2024-01-15.csv                 # (auto-generated)
│   ├── 2024-01-16.csv
│   └── ...
│
├── Sequence-Tracks/                    # Generated sequence track files
│   ├── seq_001.csv                     # (auto-generated)
│   ├── seq_002.csv
│   └── ...
│
└── Turn-track/                         # Generated turn maneuver files
    ├── turn_001.csv                    # (auto-generated)
    ├── turn_002.csv
    └── ...
```

## Installation

### Prerequisites

- Python 3.8+
- pip package manager

### Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:rdallagnolo/repo_survMon.git
   cd marine-survey-vessel-tracking
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create required directories:**
   ```bash
   mkdir -p 24hrVesselPosition DailyTracks Sequence-Tracks Turn-track
   ```

## Usage

### Data Preparation

1. **Export daily CSV files** from your ORCA system and place them in the `24hrVesselPosition/` folder
2. **Ensure `orca-web.csv`** contains your survey configuration data with sequence information

### Running the Application

Start the Streamlit application:

```bash
streamlit run Start.py
```

The application will be available at `http://localhost:8501`

### Application Modules

#### 1. Database Manager 🗃️
- **Purpose**: Central hub for data management
- **Features**: 
  - Combine daily CSV files into master database
  - Backup and restore functionality
  - Data quality overview

#### 2. Daily Track Analyzer 📅
- **Purpose**: Day-by-day vessel movement analysis
- **Features**:
  - Interactive daily vessel tracks
  - Speed distribution analysis
  - Daily performance metrics
  - Distance and speed trends

#### 3. Sequence Track Analyzer 🛤️
- **Purpose**: Survey line performance analysis
- **Features**:
  - Individual survey sequence visualization
  - Sequence performance comparison
  - Survey line efficiency metrics

#### 4. Turn Track Analyzer 🔄
- **Purpose**: Turn maneuver analysis
- **Features**:
  - Turn behavior visualization
  - Turn duration and efficiency analysis
  - Comparative turn performance

#### 5. Track Slicer ✂️
- **Purpose**: Custom time-range analysis
- **Features**:
  - Flexible time period selection
  - Custom track visualization
  - Performance metrics for any time range

#### 6. Statistics Dashboard 📊
- **Purpose**: Comprehensive statistical analysis
- **Features**:
  - Cardinal direction analysis
  - Speed distribution comparisons
  - Statistical summaries by direction
  - Performance box plots and bar charts

## Data Format

### Input Data Requirements

**Vessel Position Files** should contain:
- `Unnamed: 0`: Unix timestamp
- `Unnamed: 1`: Time in HH:MM:SS format
- `V1 Easting`: Vessel easting coordinate
- `V1 Northing`: Vessel northing coordinate  
- `V1 Bottom Speed`: Vessel speed in m/s

**ORCA Web Configuration** should contain:
- `Seq No`: Sequence number
- `Line Name`: Survey line identifier
- `Heading`: Compass heading in degrees
- `SOL Date/Time`: Start of line timestamp
- `EOL Date/Time`: End of line timestamp

## Key Features

### Speed Conversion
- Automatic conversion from m/s to knots (1 m/s = 1.943844 knots)

### Coordinate System
- Uses Easting/Northing coordinate system
- Distance calculations in kilometers

### Cardinal Direction Mapping
- Automatic conversion of compass headings to 8-point cardinal directions
- Directional performance analysis (N, NE, E, SE, S, SW, W, NW)

### Performance Metrics
- **Distance**: Total distance traveled in kilometers
- **Speed**: Average, minimum, maximum speeds in knots
- **Duration**: Time-based analysis in hours
- **Efficiency**: Turn performance and sequence optimization

## Technical Details

### Dependencies

- **streamlit**: Web application framework
- **pandas**: Data manipulation and analysis
- **plotly**: Interactive visualization
- **numpy**: Numerical computing
- **natsort**: Natural sorting of filenames

### Performance Optimization

- **Session State Caching**: Prevents unnecessary recomputation
- **Lazy Loading**: Data loaded only when required
- **Memory Management**: Efficient handling of large datasets

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please create an issue in the GitHub repository or contact the development team.

## Acknowledgments

- ORCA Marine Survey System for data format standards
- Streamlit community for application framework
- Marine survey professionals for requirements and testing

---

**Happy Surveying!** 🌊⚓