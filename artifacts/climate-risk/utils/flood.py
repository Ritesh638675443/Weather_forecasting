"""Global Flood Database utilities.

Expects data/flood_events.csv with at minimum columns:
  started, ended, country, centroid_x (lon), centroid_y (lat),
  severity, dead, displaced, maincause, began
If the file is absent, returns zero-exposure defaults.
"""
import math
import os
import streamlit as st
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "flood_events.csv")


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2 - lat1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@st.cache_data(ttl=86400)
def _load_flood_db() -> pd.DataFrame | None:
    if not os.path.exists(DATA_PATH):
        return None
    try:
        df = pd.read_csv(DATA_PATH, low_memory=False)
        # Normalise common column name variants
        col_map = {}
        for c in df.columns:
            lc = c.lower()
            if "lat" in lc or "centroid_y" in lc:
                col_map[c] = "lat"
            elif "lon" in lc or "centroid_x" in lc:
                col_map[c] = "lon"
            elif "severity" in lc:
                col_map[c] = "severity"
        df = df.rename(columns=col_map)
        df["lat"] = pd.to_numeric(df.get("lat", pd.Series(dtype=float)), errors="coerce")
        df["lon"] = pd.to_numeric(df.get("lon", pd.Series(dtype=float)), errors="coerce")
        df["severity"] = pd.to_numeric(df.get("severity", pd.Series(dtype=float)), errors="coerce").fillna(1)
        return df.dropna(subset=["lat", "lon"])
    except Exception:
        return None


@st.cache_data(ttl=86400)
def get_flood_events(lat: float, lon: float, radius_km: float = 300) -> pd.DataFrame:
    """Return flood events within radius_km of the target."""
    df = _load_flood_db()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["dist_km"] = df.apply(lambda r: _haversine_km(lat, lon, r["lat"], r["lon"]), axis=1)
    return df[df["dist_km"] <= radius_km].sort_values("dist_km")


def calculate_flood_frequency(lat: float, lon: float, radius_km: float = 300) -> float:
    """Return normalised flood frequency score (0–100)."""
    events = get_flood_events(lat, lon, radius_km)
    count = len(events)
    return min(count / 20, 1.0) * 100  # cap at 20 events → 100


def calculate_flood_risk(
    heavy_rain_days: int,
    flood_frequency: float,
    elevation_risk: float,
) -> float:
    """Weighted flood risk score (0–100)."""
    rain_score = min(heavy_rain_days / 50, 1.0) * 100
    score = 0.5 * rain_score + 0.3 * flood_frequency + 0.2 * elevation_risk
    return round(min(score, 100.0), 2)
