"""Geocoding via OpenStreetMap Nominatim."""
import time
import requests
import streamlit as st

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "ClimateRiskDashboard/1.0"}


def _request_with_retry(url: str, params: dict, max_retries: int = 3) -> dict | list:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 503):
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
        except requests.RequestException:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Nominatim API failed after retries")


@st.cache_data(ttl=86400)
def get_coordinates(location: str) -> dict | None:
    """Convert a location string to latitude/longitude.

    Returns dict with keys: lat, lon, display_name, or None on failure.
    """
    params = {
        "q": location,
        "format": "json",
        "limit": 1,
    }
    results = _request_with_retry(f"{NOMINATIM_BASE}/search", params)
    if not results:
        return None
    r = results[0]
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", location),
    }


@st.cache_data(ttl=86400)
def reverse_geocode(lat: float, lon: float) -> str:
    """Convert lat/lon to a human-readable address."""
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
    }
    result = _request_with_retry(f"{NOMINATIM_BASE}/reverse", params)
    return result.get("display_name", f"{lat:.4f}, {lon:.4f}")
