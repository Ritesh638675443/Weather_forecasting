"""IBTrACS cyclone dataset utilities.

The IBTrACS CSV is large (~50 MB). We load it lazily and cache it.
If the file is absent we fall back to a zero-exposure result so the
rest of the app still works.
"""
import math
import os
import streamlit as st
import pandas as pd
import numpy as np

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ibtracs.csv")


@st.cache_data(ttl=86400)
def _load_ibtracs() -> pd.DataFrame | None:
    if not os.path.exists(DATA_PATH):
        return None
    try:
        df = pd.read_csv(
            DATA_PATH,
            skiprows=[1],          # IBTrACS has a unit row after the header
            low_memory=False,
            usecols=["SID", "NAME", "LAT", "LON", "WMO_WIND", "SEASON"],
        )
        df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
        df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
        df["WMO_WIND"] = pd.to_numeric(df["WMO_WIND"], errors="coerce")
        return df.dropna(subset=["LAT", "LON"])
    except Exception:
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@st.cache_data(ttl=86400)
def get_nearby_cyclones(lat: float, lon: float, radius_km: float = 500) -> pd.DataFrame:
    """Return IBTrACS track points within `radius_km` of the target location."""
    df = _load_ibtracs()
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["dist_km"] = df.apply(
        lambda r: _haversine_km(lat, lon, r["LAT"], r["LON"]), axis=1
    )
    return df[df["dist_km"] <= radius_km].sort_values("dist_km")


def calculate_cyclone_exposure(lat: float, lon: float, radius_km: float = 500) -> dict:
    """Compute cyclone exposure metrics for a location."""
    nearby = get_nearby_cyclones(lat, lon, radius_km)

    if nearby.empty:
        return {
            "cyclone_count": 0,
            "unique_storms": 0,
            "max_wind_knots": 0.0,
            "nearest_track_km": radius_km,
            "cyclone_score": 0.0,
        }

    unique_storms = nearby["SID"].nunique()
    max_wind = float(nearby["WMO_WIND"].max() or 0)
    nearest_km = float(nearby["dist_km"].min())

    # Normalise count (cap at 50 storms → score 100)
    count_score = min(unique_storms / 50, 1.0) * 100
    # Normalise wind (cap at 150 knots → score 100)
    wind_score = min(max_wind / 150, 1.0) * 100

    cyclone_score = 0.5 * count_score + 0.5 * wind_score

    return {
        "cyclone_count": unique_storms,
        "unique_storms": unique_storms,
        "max_wind_knots": max_wind,
        "nearest_track_km": nearest_km,
        "cyclone_score": round(cyclone_score, 2),
    }
