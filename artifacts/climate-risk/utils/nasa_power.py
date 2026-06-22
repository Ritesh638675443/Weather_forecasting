"""NASA POWER Climate API utilities."""
import time
import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime


NASA_BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"
VARIABLES = "PRECTOTCORR,T2M,T2M_MAX,T2M_MIN,RH2M,WS2M"


def _request_with_retry(url: str, params: dict, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 503):
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            resp.raise_for_status()
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f"NASA POWER API failed after {max_retries} retries")


@st.cache_data(ttl=86400)
def get_climate_data(latitude: float, longitude: float, start_date: str, end_date: str) -> dict:
    """Fetch daily climate data from NASA POWER API."""
    params = {
        "parameters": VARIABLES,
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "format": "JSON",
    }
    return _request_with_retry(NASA_BASE, params)


def process_climate_data(response: dict) -> pd.DataFrame:
    """Convert NASA POWER JSON response to a tidy DataFrame."""
    try:
        props = response["properties"]["parameter"]
    except KeyError:
        return pd.DataFrame()

    df = pd.DataFrame(props)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"

    rename = {
        "PRECTOTCORR": "rainfall_mm",
        "T2M": "temp_avg_c",
        "T2M_MAX": "temp_max_c",
        "T2M_MIN": "temp_min_c",
        "RH2M": "humidity_pct",
        "WS2M": "wind_speed_ms",
    }
    df = df.rename(columns=rename)

    # Replace NASA fill value -999 with NaN
    df = df.replace(-999.0, np.nan)
    return df


def generate_climate_features(df: pd.DataFrame) -> dict:
    """Compute aggregated climate risk features from daily data."""
    if df.empty:
        return {}

    features = {}

    # Annual rainfall
    annual = df["rainfall_mm"].resample("YE").sum()
    features["annual_rainfall_mean"] = float(annual.mean())
    features["annual_rainfall_trend"] = float(
        np.polyfit(range(len(annual)), annual.fillna(0), 1)[0]
        if len(annual) > 1 else 0
    )

    # Temperature
    features["avg_temperature"] = float(df["temp_avg_c"].mean())

    # Heavy rain days
    features["heavy_rain_days"] = int((df["rainfall_mm"] > 100).sum())
    features["extreme_rain_days"] = int((df["rainfall_mm"] > 200).sum())

    # Heatwave days
    features["heatwave_days"] = int((df["temp_max_c"] > 40).sum())

    # Consecutive dry days (max streak of rainfall < 1 mm)
    dry = (df["rainfall_mm"].fillna(0) < 1).astype(int)
    max_streak = 0
    streak = 0
    for v in dry:
        streak = streak + 1 if v else 0
        max_streak = max(max_streak, streak)
    features["max_consecutive_dry_days"] = max_streak

    # Years of data
    features["years_of_data"] = len(df) / 365.25

    return features
