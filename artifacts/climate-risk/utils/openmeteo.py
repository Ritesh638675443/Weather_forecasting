"""Open-Meteo current weather and forecast utilities."""
import time
import requests
import streamlit as st


FORECAST_BASE = "https://api.open-meteo.com/v1/forecast"


def _request_with_retry(url: str, params: dict, max_retries: int = 3) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
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
    raise RuntimeError("Open-Meteo API failed after retries")


@st.cache_data(ttl=86400)
def get_current_weather(latitude: float, longitude: float) -> dict:
    """Fetch current conditions (latest hourly observation)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "forecast_days": 1,
    }
    data = _request_with_retry(FORECAST_BASE, params)
    hourly = data.get("hourly", {})

    # Use most recent non-null index
    temps = hourly.get("temperature_2m", [None])
    humid = hourly.get("relative_humidity_2m", [None])
    precip = hourly.get("precipitation", [0])
    wind = hourly.get("wind_speed_10m", [None])

    idx = min(len(temps) - 1, 11)  # ~noon observation
    return {
        "temperature_c": temps[idx],
        "humidity_pct": humid[idx],
        "precipitation_mm": sum(p for p in precip if p),
        "wind_speed_kmh": wind[idx],
    }


@st.cache_data(ttl=86400)
def get_forecast(latitude: float, longitude: float, days: int = 7) -> dict:
    """Fetch multi-day forecast summary."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "forecast_days": days,
        "timezone": "auto",
    }
    return _request_with_retry(FORECAST_BASE, params)
