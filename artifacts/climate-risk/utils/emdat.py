"""EM-DAT disaster database utilities.

Expects data/emdat.csv with columns that typically include:
  Country, Disaster Type, Year, Total Deaths, Total Affected,
  Total Damage ('000 US$), Latitude, Longitude
If the file is absent the functions return zero-exposure defaults.
"""
import os
import streamlit as st
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "emdat.csv")


@st.cache_data(ttl=86400)
def _load_emdat() -> pd.DataFrame | None:
    if not os.path.exists(DATA_PATH):
        return None
    try:
        df = pd.read_csv(DATA_PATH, low_memory=False)
        # Normalise column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception:
        return None


@st.cache_data(ttl=86400)
def get_disaster_history(country: str | None = None) -> pd.DataFrame:
    """Return EM-DAT records, optionally filtered by country."""
    df = _load_emdat()
    if df is None or df.empty:
        return pd.DataFrame()
    if country:
        country_col = next((c for c in df.columns if "country" in c), None)
        if country_col:
            df = df[df[country_col].str.lower().str.contains(country.lower(), na=False)]
    return df


def calculate_catastrophe_exposure(country: str | None = None) -> dict:
    """Summarise EM-DAT disaster statistics for a country."""
    df = get_disaster_history(country)

    if df.empty:
        return {
            "disaster_count": 0,
            "total_deaths": 0,
            "total_affected": 0,
            "economic_loss_musd": 0.0,
            "catastrophe_score": 0.0,
        }

    disaster_count = len(df)

    death_col = next((c for c in df.columns if "death" in c or "kill" in c), None)
    affected_col = next((c for c in df.columns if "affected" in c), None)
    damage_col = next((c for c in df.columns if "damage" in c or "loss" in c), None)

    total_deaths = int(pd.to_numeric(df[death_col], errors="coerce").sum()) if death_col else 0
    total_affected = int(pd.to_numeric(df[affected_col], errors="coerce").sum()) if affected_col else 0
    economic_loss = float(pd.to_numeric(df[damage_col], errors="coerce").sum()) / 1000 if damage_col else 0.0

    # Normalised catastrophe score (0–100)
    count_score = min(disaster_count / 100, 1.0) * 100
    catastrophe_score = round(count_score, 2)

    return {
        "disaster_count": disaster_count,
        "total_deaths": total_deaths,
        "total_affected": total_affected,
        "economic_loss_musd": round(economic_loss, 2),
        "catastrophe_score": catastrophe_score,
    }
