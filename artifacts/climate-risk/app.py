"""Climate & Catastrophe Risk Dashboard — Streamlit main app."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta

from utils.geocoder import get_coordinates, reverse_geocode
from utils.nasa_power import get_climate_data, process_climate_data, generate_climate_features
from utils.openmeteo import get_current_weather, get_forecast
from utils.elevation import get_elevation, elevation_to_flood_risk
from utils.cyclone import calculate_cyclone_exposure
from utils.flood import calculate_flood_frequency, calculate_flood_risk, get_flood_events
from utils.emdat import calculate_catastrophe_exposure
from utils.risk_engine import (
    calculate_heat_score,
    calculate_drought_score,
    calculate_climate_risk,
    risk_label,
    risk_color,
)

st.set_page_config(
    page_title="Climate Intelligence Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🌍 Climate Intelligence")
    st.caption("Powered by NASA POWER · Open-Meteo · OSM Nominatim · IBTrACS")
    st.divider()

    input_mode = st.radio("Location input", ["Search by name", "Enter coordinates"])

    if input_mode == "Search by name":
        location_query = st.text_input(
            "City / District / State / Country",
            placeholder="e.g. Chennai, Tamil Nadu, India",
        )
        lat_input = lon_input = None
    else:
        location_query = None
        lat_input = st.number_input("Latitude", value=13.0827, format="%.4f")
        lon_input = st.number_input("Longitude", value=80.2707, format="%.4f")

    st.divider()
    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input("History start", value=date(2010, 1, 1))
    with col_e:
        end_date = st.date_input("History end", value=date(2023, 12, 31))

    country_filter = st.text_input(
        "Country (for EM-DAT filter)",
        placeholder="India",
        help="Used to filter the EM-DAT disaster database",
    )

    analyse = st.button("⚡ Analyse Location", use_container_width=True, type="primary")

# ── Welcome screen ─────────────────────────────────────────────────────────────
if not analyse:
    st.title("🌍 Climate Intelligence Dashboard")
    st.markdown(
        """
        Assess **flood, cyclone, heat and drought risk** for any location on Earth,
        combining live weather, 20+ years of climate history, and global disaster databases.

        **Data sources:**
        | Source | Purpose |
        |---|---|
        | NASA POWER | 20-year daily climate history |
        | Open-Meteo | Current weather & 7-day forecast |
        | OpenStreetMap Nominatim | Geocoding |
        | Open-Elevation | Flood susceptibility via terrain |
        | IBTrACS | Cyclone track exposure |
        | Global Flood Database | Historical flood events |
        | EM-DAT | Catastrophe loss analytics |

        👈 **Enter a location in the sidebar and click Analyse.**
        """
    )

    st.info(
        "💡 **Tip:** IBTrACS (`data/ibtracs.csv`), flood events (`data/flood_events.csv`), "
        "and EM-DAT (`data/emdat.csv`) datasets are read from local files. "
        "Download them and place them in the `data/` folder for full analysis. "
        "All other data sources are fetched live."
    )
    st.stop()

# ── Resolve location ──────────────────────────────────────────────────────────
with st.spinner("Resolving location…"):
    if input_mode == "Search by name" and location_query:
        geo = get_coordinates(location_query)
        if not geo:
            st.error(f"Could not geocode **{location_query}**. Try a more specific name.")
            st.stop()
        lat, lon = geo["lat"], geo["lon"]
        display_name = geo["display_name"]
    elif input_mode == "Enter coordinates" and lat_input is not None:
        lat, lon = lat_input, lon_input
        display_name = reverse_geocode(lat, lon)
    else:
        st.warning("Please enter a location.")
        st.stop()

st.title(f"🌍 {display_name}")
st.caption(f"Coordinates: {lat:.4f}°N, {lon:.4f}°E  |  Analysis period: {start_date} → {end_date}")
st.divider()

# ── Fetch all data ─────────────────────────────────────────────────────────────
progress = st.progress(0, text="Fetching current weather…")

with st.spinner("Loading data — this may take up to 30 seconds on first run…"):
    # 1. Current weather
    try:
        weather = get_current_weather(lat, lon)
    except Exception as e:
        weather = {}
        st.warning(f"Open-Meteo unavailable: {e}")
    progress.progress(15, "Fetching forecast…")

    # 2. Forecast
    try:
        forecast_raw = get_forecast(lat, lon)
    except Exception:
        forecast_raw = {}
    progress.progress(25, "Fetching NASA POWER climate history…")

    # 3. NASA POWER
    climate_features = {}
    climate_df = pd.DataFrame()
    try:
        nasa_resp = get_climate_data(lat, lon, str(start_date), str(end_date))
        climate_df = process_climate_data(nasa_resp)
        climate_features = generate_climate_features(climate_df)
    except Exception as e:
        st.warning(f"NASA POWER data unavailable: {e}")
    progress.progress(50, "Fetching elevation…")

    # 4. Elevation
    elevation_m = get_elevation(lat, lon)
    elev_risk = elevation_to_flood_risk(elevation_m)
    progress.progress(60, "Calculating cyclone exposure…")

    # 5. Cyclone
    cyclone_data = calculate_cyclone_exposure(lat, lon)
    progress.progress(70, "Calculating flood frequency…")

    # 6. Flood
    flood_freq = calculate_flood_frequency(lat, lon)
    progress.progress(80, "Loading EM-DAT disaster data…")

    # 7. EM-DAT
    catastro = calculate_catastrophe_exposure(country_filter or None)
    progress.progress(90, "Computing risk scores…")

    # ── Risk scores ────────────────────────────────────────────────────────────
    heavy_rain = climate_features.get("heavy_rain_days", 0)
    heatwave_days = climate_features.get("heatwave_days", 0)
    dry_days = climate_features.get("max_consecutive_dry_days", 0)

    flood_score = calculate_flood_risk(heavy_rain, flood_freq, elev_risk)
    cyclone_score = cyclone_data["cyclone_score"]
    heat_score = calculate_heat_score(heatwave_days)
    drought_score = calculate_drought_score(dry_days)
    overall_score = calculate_climate_risk(flood_score, cyclone_score, heat_score, drought_score)

    progress.progress(100, "Done!")
    progress.empty()

# ══════════════════════════════════════════════════════════════════════════════
# Section 1 — Current Weather
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🌤️ Current Conditions")
w1, w2, w3, w4 = st.columns(4)
w1.metric("🌡️ Temperature", f"{weather.get('temperature_c', 'N/A')} °C")
w2.metric("💧 Humidity", f"{weather.get('humidity_pct', 'N/A')} %")
w3.metric("🌧️ Precipitation (today)", f"{weather.get('precipitation_mm', 'N/A')} mm")
w4.metric("💨 Wind Speed", f"{weather.get('wind_speed_kmh', 'N/A')} km/h")

# 7-day forecast
if forecast_raw and "daily" in forecast_raw:
    daily = forecast_raw["daily"]
    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    if dates:
        fc_df = pd.DataFrame({
            "Date": pd.to_datetime(dates),
            "Max Temp (°C)": t_max,
            "Min Temp (°C)": t_min,
            "Precipitation (mm)": precip,
        })
        fig_fc = go.Figure()
        fig_fc.add_trace(go.Scatter(x=fc_df["Date"], y=fc_df["Max Temp (°C)"],
                                    name="Max Temp", line=dict(color="#ef4444")))
        fig_fc.add_trace(go.Scatter(x=fc_df["Date"], y=fc_df["Min Temp (°C)"],
                                    name="Min Temp", line=dict(color="#3b82f6"),
                                    fill="tonexty", fillcolor="rgba(59,130,246,0.1)"))
        fig_fc.add_trace(go.Bar(x=fc_df["Date"], y=fc_df["Precipitation (mm)"],
                                name="Precipitation", yaxis="y2",
                                marker_color="rgba(96,165,250,0.5)"))
        fig_fc.update_layout(
            title="7-Day Forecast",
            yaxis=dict(title="Temperature (°C)"),
            yaxis2=dict(title="Precipitation (mm)", overlaying="y", side="right"),
            legend=dict(orientation="h"),
            height=300,
        )
        st.plotly_chart(fig_fc, use_container_width=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 2 — Risk Score Cards
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🚨 Climate Risk Scores")

def gauge(value: float, title: str) -> go.Figure:
    color = "#22c55e" if value < 25 else "#eab308" if value < 50 else "#f97316" if value < 75 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 25], "color": "#dcfce7"},
                {"range": [25, 50], "color": "#fef9c3"},
                {"range": [50, 75], "color": "#ffedd5"},
                {"range": [75, 100], "color": "#fee2e2"},
            ],
            "threshold": {"line": {"color": "darkred", "width": 3}, "value": value},
        },
        number={"suffix": "/100"},
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=10, l=10, r=10))
    return fig


g1, g2, g3, g4, g5 = st.columns(5)
with g1:
    st.plotly_chart(gauge(overall_score, "🌍 Overall Risk"), use_container_width=True)
    st.caption(f"**{risk_label(overall_score)}**")
with g2:
    st.plotly_chart(gauge(flood_score, "🌊 Flood Risk"), use_container_width=True)
    st.caption(f"**{risk_label(flood_score)}**")
with g3:
    st.plotly_chart(gauge(cyclone_score, "🌀 Cyclone Risk"), use_container_width=True)
    st.caption(f"**{risk_label(cyclone_score)}**")
with g4:
    st.plotly_chart(gauge(heat_score, "🔥 Heat Risk"), use_container_width=True)
    st.caption(f"**{risk_label(heat_score)}**")
with g5:
    st.plotly_chart(gauge(drought_score, "🏜️ Drought Risk"), use_container_width=True)
    st.caption(f"**{risk_label(drought_score)}**")

# Risk breakdown table
risk_df = pd.DataFrame({
    "Risk Type": ["Flood", "Cyclone", "Heat", "Drought", "Composite Climate Risk"],
    "Score (0–100)": [flood_score, cyclone_score, heat_score, drought_score, overall_score],
    "Level": [
        risk_label(flood_score), risk_label(cyclone_score),
        risk_label(heat_score), risk_label(drought_score), risk_label(overall_score),
    ],
    "Weight": ["40%", "25%", "15%", "20%", "—"],
})
st.dataframe(risk_df, use_container_width=True, hide_index=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 3 — Historical Climate Analytics
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📊 Historical Climate Analytics (NASA POWER)")

if not climate_df.empty:
    tab1, tab2, tab3, tab4 = st.tabs(["Rainfall", "Temperature", "Humidity & Wind", "Summary Stats"])

    with tab1:
        annual_rain = climate_df["rainfall_mm"].resample("YE").sum().reset_index()
        annual_rain.columns = ["Year", "Annual Rainfall (mm)"]
        fig_r = px.bar(annual_rain, x="Year", y="Annual Rainfall (mm)",
                       title="Annual Rainfall", color="Annual Rainfall (mm)",
                       color_continuous_scale="Blues")
        st.plotly_chart(fig_r, use_container_width=True)

        # Monthly pattern (average across all years)
        climate_df["month"] = climate_df.index.month
        monthly_rain = climate_df.groupby("month")["rainfall_mm"].mean().reset_index()
        monthly_rain["month"] = monthly_rain["month"].apply(
            lambda m: ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1]
        )
        fig_mr = px.bar(monthly_rain, x="month", y="rainfall_mm",
                        title="Average Monthly Rainfall", labels={"rainfall_mm": "Avg Rainfall (mm)"})
        st.plotly_chart(fig_mr, use_container_width=True)

    with tab2:
        annual_temp = climate_df[["temp_avg_c","temp_max_c","temp_min_c"]].resample("YE").mean().reset_index()
        fig_t = go.Figure()
        fig_t.add_trace(go.Scatter(x=annual_temp["date"], y=annual_temp["temp_max_c"],
                                   name="Max Temp", line=dict(color="#ef4444")))
        fig_t.add_trace(go.Scatter(x=annual_temp["date"], y=annual_temp["temp_avg_c"],
                                   name="Avg Temp", line=dict(color="#f97316")))
        fig_t.add_trace(go.Scatter(x=annual_temp["date"], y=annual_temp["temp_min_c"],
                                   name="Min Temp", line=dict(color="#3b82f6"),
                                   fill="tonexty", fillcolor="rgba(59,130,246,0.05)"))
        fig_t.update_layout(title="Annual Temperature Trends", yaxis_title="°C", height=350)
        st.plotly_chart(fig_t, use_container_width=True)

    with tab3:
        annual_hw = climate_df[["humidity_pct","wind_speed_ms"]].resample("YE").mean().reset_index()
        col_h, col_w = st.columns(2)
        with col_h:
            fig_h = px.line(annual_hw, x="date", y="humidity_pct",
                            title="Annual Avg Humidity (%)", markers=True)
            st.plotly_chart(fig_h, use_container_width=True)
        with col_w:
            fig_w = px.line(annual_hw, x="date", y="wind_speed_ms",
                            title="Annual Avg Wind Speed (m/s)", markers=True,
                            color_discrete_sequence=["#8b5cf6"])
            st.plotly_chart(fig_w, use_container_width=True)

    with tab4:
        feat_display = {
            "Annual Rainfall Mean (mm)": round(climate_features.get("annual_rainfall_mean", 0), 1),
            "Annual Rainfall Trend (mm/yr)": round(climate_features.get("annual_rainfall_trend", 0), 2),
            "Average Temperature (°C)": round(climate_features.get("avg_temperature", 0), 2),
            "Heavy Rain Days (>100 mm)": climate_features.get("heavy_rain_days", 0),
            "Extreme Rain Days (>200 mm)": climate_features.get("extreme_rain_days", 0),
            "Heatwave Days (>40 °C)": climate_features.get("heatwave_days", 0),
            "Max Consecutive Dry Days": climate_features.get("max_consecutive_dry_days", 0),
            "Years of Data": round(climate_features.get("years_of_data", 0), 1),
        }
        feat_df = pd.DataFrame(list(feat_display.items()), columns=["Feature", "Value"])
        st.dataframe(feat_df, use_container_width=True, hide_index=True)
else:
    st.info("NASA POWER data not available for this location or period.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 4 — Terrain & Elevation
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("⛰️ Terrain & Flood Susceptibility")
e1, e2, e3 = st.columns(3)
e1.metric("Elevation", f"{elevation_m:.0f} m" if elevation_m is not None else "Unknown")
e2.metric("Elevation Flood Risk Score", f"{elev_risk:.1f} / 100")
e3.metric("Terrain Risk Level", risk_label(elev_risk))

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 5 — Cyclone Exposure
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🌀 Cyclone Exposure (IBTrACS)")

cy1, cy2, cy3, cy4 = st.columns(4)
cy1.metric("Unique Storms (500 km radius)", cyclone_data["unique_storms"])
cy2.metric("Max Wind Speed (knots)", f"{cyclone_data['max_wind_knots']:.0f}")
cy3.metric("Nearest Track Distance", f"{cyclone_data['nearest_track_km']:.0f} km")
cy4.metric("Cyclone Score", f"{cyclone_data['cyclone_score']:.1f} / 100")

if cyclone_data["unique_storms"] == 0:
    st.info(
        "No cyclone data found. Place `data/ibtracs.csv` in the app folder "
        "(download from https://www.ncei.noaa.gov/products/international-best-track-archive) "
        "for cyclone analysis."
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 6 — Flood Events
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🌊 Historical Flood Events (Global Flood Database)")

flood_events = get_flood_events(lat, lon)
c_f1, c_f2 = st.columns(2)
c_f1.metric("Flood Events (300 km radius)", len(flood_events))
c_f2.metric("Flood Frequency Score", f"{flood_freq:.1f} / 100")

if not flood_events.empty:
    st.dataframe(flood_events.head(20), use_container_width=True, hide_index=True)
else:
    st.info(
        "No flood data found. Place `data/flood_events.csv` in the app folder "
        "for flood history analysis."
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 7 — EM-DAT Catastrophe Analytics
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("💥 Catastrophe Loss Analytics (EM-DAT)")

em1, em2, em3, em4 = st.columns(4)
em1.metric("Disaster Events", catastro["disaster_count"])
em2.metric("Total Deaths", f"{catastro['total_deaths']:,}")
em3.metric("Total Affected", f"{catastro['total_affected']:,}")
em4.metric("Economic Loss (M USD)", f"{catastro['economic_loss_musd']:,.1f}")

if catastro["disaster_count"] == 0:
    st.info(
        "No EM-DAT data found. Download from https://www.emdat.be/ and place as "
        "`data/emdat.csv` for catastrophe analytics."
    )

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 8 — Interactive Map
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🗺️ Location Map")

try:
    import folium
    from streamlit_folium import st_folium

    m = folium.Map(location=[lat, lon], zoom_start=7, tiles="CartoDB positron")
    folium.Marker(
        [lat, lon],
        popup=f"<b>{display_name}</b><br>Overall Risk: {overall_score:.1f}/100 ({risk_label(overall_score)})",
        tooltip=display_name,
        icon=folium.Icon(color="red" if overall_score >= 75 else "orange" if overall_score >= 50 else "blue"),
    ).add_to(m)

    # Circle showing analysis radius
    folium.Circle(
        [lat, lon],
        radius=300_000,  # 300 km
        color="#3b82f6",
        fill=True,
        fill_opacity=0.05,
        tooltip="300 km flood event radius",
    ).add_to(m)

    folium.Circle(
        [lat, lon],
        radius=500_000,  # 500 km
        color="#8b5cf6",
        fill=False,
        tooltip="500 km cyclone exposure radius",
    ).add_to(m)

    st_folium(m, use_container_width=True, height=450)
except ImportError:
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}))

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Section 9 — Full Risk Report Summary
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📋 Risk Report Summary")

report_md = f"""
| Category | Value |
|---|---|
| **Location** | {display_name} |
| **Coordinates** | {lat:.4f}°N, {lon:.4f}°E |
| **Elevation** | {f"{elevation_m:.0f} m" if elevation_m else "Unknown"} |
| **Analysis Period** | {start_date} → {end_date} |
| | |
| **Overall Climate Risk** | {overall_score:.1f} / 100 — **{risk_label(overall_score)}** |
| **Flood Risk** | {flood_score:.1f} / 100 — {risk_label(flood_score)} |
| **Cyclone Risk** | {cyclone_score:.1f} / 100 — {risk_label(cyclone_score)} |
| **Heat Risk** | {heat_score:.1f} / 100 — {risk_label(heat_score)} |
| **Drought Risk** | {drought_score:.1f} / 100 — {risk_label(drought_score)} |
| | |
| **Annual Rainfall** | {climate_features.get("annual_rainfall_mean", "N/A")} mm/yr |
| **Avg Temperature** | {climate_features.get("avg_temperature", "N/A")} °C |
| **Heavy Rain Days** | {climate_features.get("heavy_rain_days", "N/A")} (>100 mm) |
| **Heatwave Days** | {climate_features.get("heatwave_days", "N/A")} (>40 °C) |
| **Max Dry Streak** | {climate_features.get("max_consecutive_dry_days", "N/A")} days |
| | |
| **Nearby Cyclones** | {cyclone_data["unique_storms"]} unique storms |
| **Max Wind (cyclone)** | {cyclone_data["max_wind_knots"]:.0f} knots |
| **Flood Events** | {len(flood_events)} (300 km radius) |
| **EM-DAT Disasters** | {catastro["disaster_count"]} events |
| **Economic Loss** | USD {catastro["economic_loss_musd"]:,.1f}M |
"""
st.markdown(report_md)

st.caption(
    "Scores are normalised 0–100. Composite weights: Flood 40%, Cyclone 25%, Drought 20%, Heat 15%. "
    "IBTrACS, flood, and EM-DAT data require local CSV files — see `data/` folder instructions."
)
