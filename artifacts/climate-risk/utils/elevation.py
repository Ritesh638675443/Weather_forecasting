"""Elevation data via Open-Elevation (free, no key required)."""
import time
import requests
import streamlit as st

# Open-Elevation is a free, open-source alternative that needs no API key
OPEN_ELEVATION_BASE = "https://api.open-elevation.com/api/v1/lookup"


def _request_with_retry(url: str, json_body: dict, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=json_body, timeout=20)
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
    raise RuntimeError("Elevation API failed after retries")


@st.cache_data(ttl=86400)
def get_elevation(lat: float, lon: float) -> float | None:
    """Return elevation in metres for a given coordinate.

    Falls back to None if the service is unavailable.
    """
    try:
        body = {"locations": [{"latitude": lat, "longitude": lon}]}
        data = _request_with_retry(OPEN_ELEVATION_BASE, body)
        results = data.get("results", [])
        if results:
            return float(results[0]["elevation"])
    except Exception:
        pass
    return None


def elevation_to_flood_risk(elevation_m: float | None) -> float:
    """Convert elevation (m) to a flood susceptibility score (0–100).

    Lower elevation → higher risk.
    """
    if elevation_m is None:
        return 50.0  # unknown → neutral
    if elevation_m <= 0:
        return 100.0
    if elevation_m >= 200:
        return 0.0
    # Linear interpolation: 0m → 100, 200m → 0
    return max(0.0, min(100.0, (1 - elevation_m / 200) * 100))
