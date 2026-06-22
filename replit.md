# Climate & Catastrophe Risk Dashboard

A Streamlit web app that assesses flood, cyclone, heat, and drought risk for any location on Earth using live and historical climate datasets.

## Run & Operate

- `cd artifacts/climate-risk && streamlit run app.py --server.port 5000` — run the dashboard
- Workflow: **Climate Risk Dashboard** (auto-starts, port 5000)

## Stack

- Python 3.11 + Streamlit
- Data: pandas, numpy, plotly, folium, streamlit-folium
- HTTP: requests (with exponential-backoff retry on 429/500/503)
- Caching: `@st.cache_data(ttl=86400)`

## Where things live

```
artifacts/climate-risk/
├── app.py                  # Main Streamlit app (all UI & orchestration)
├── .streamlit/config.toml  # Server config (port 5000, headless)
├── utils/
│   ├── nasa_power.py       # NASA POWER climate API (historical daily data)
│   ├── openmeteo.py        # Open-Meteo current weather & forecast
│   ├── geocoder.py         # OSM Nominatim geocoding / reverse geocoding
│   ├── elevation.py        # Open-Elevation terrain data → flood susceptibility
│   ├── cyclone.py          # IBTrACS cyclone track exposure
│   ├── flood.py            # Global Flood Database event analysis
│   ├── emdat.py            # EM-DAT catastrophe loss analytics
│   └── risk_engine.py      # Normalised risk score calculations
└── data/                   # Local CSV datasets (see below)
    ├── ibtracs.csv          # Download from NCEI (IBTrACS)
    ├── flood_events.csv     # Global Flood Database
    └── emdat.csv            # EM-DAT disaster database
```

## Local Datasets

Three datasets must be downloaded manually and placed in `artifacts/climate-risk/data/`:

| File | Source |
|------|--------|
| `ibtracs.csv` | https://www.ncei.noaa.gov/products/international-best-track-archive |
| `flood_events.csv` | Global Flood Database |
| `emdat.csv` | https://www.emdat.be/ |

All live APIs (NASA POWER, Open-Meteo, Nominatim, Open-Elevation) require no API keys.

## Risk Score Formulas

- **Flood** = 0.5 × HeavyRainDays_norm + 0.3 × FloodFrequency + 0.2 × ElevationRisk
- **Cyclone** = 0.5 × CycloneCount_norm + 0.5 × MaxWindExposure_norm
- **Heat** = HeatwaveDays / 60 × 100
- **Drought** = MaxDryDays / 180 × 100
- **Climate Risk** = 0.40 × Flood + 0.25 × Cyclone + 0.15 × Heat + 0.20 × Drought

All scores normalised 0–100.

## Architecture decisions

- All API calls cached with `@st.cache_data(ttl=86400)` to avoid redundant requests.
- Retry logic (max 3 attempts, exponential backoff) on 429/500/503 for all HTTP clients.
- Local CSV datasets are optional — app degrades gracefully when files are absent.
- Open-Elevation used instead of OpenTopography (no API key required).
- Risk engine is pure Python with no external dependencies.

## Product

Users enter a location (city name or coordinates), select a historical date range, and instantly get:
- Live current weather + 7-day forecast
- Five normalised risk gauges (Overall, Flood, Cyclone, Heat, Drought)
- 20-year climate history charts (rainfall, temperature, humidity, wind)
- Cyclone track exposure, flood event history, and EM-DAT disaster analytics
- Interactive Folium map with analysis radius circles
- Printable risk report summary table

## User preferences

_Populate as needed._

## Gotchas

- IBTrACS CSV has a unit row after the header row — skip it with `skiprows=[1]`.
- NASA POWER uses fill value `-999.0` for missing data — replace with NaN.
- NASA POWER date format is `YYYYMMDD` (no dashes).
- Streamlit `experimental_rerun` is not supported — use `st.rerun()`.
