"""Climate Risk Engine — combines all data sources into normalised scores."""


def calculate_heat_score(heatwave_days: int) -> float:
    """Normalised heat risk score (0–100). Caps at 60 heatwave days."""
    return round(min(heatwave_days / 60, 1.0) * 100, 2)


def calculate_drought_score(max_consecutive_dry_days: int) -> float:
    """Normalised drought risk score (0–100). Caps at 180 consecutive dry days."""
    return round(min(max_consecutive_dry_days / 180, 1.0) * 100, 2)


def calculate_climate_risk(
    flood_score: float,
    cyclone_score: float,
    heat_score: float,
    drought_score: float,
) -> float:
    """Composite climate risk score (0–100) using specified weights."""
    score = (
        0.40 * flood_score
        + 0.25 * cyclone_score
        + 0.15 * heat_score
        + 0.20 * drought_score
    )
    return round(min(max(score, 0.0), 100.0), 2)


def risk_label(score: float) -> str:
    if score >= 75:
        return "Very High"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Moderate"
    return "Low"


def risk_color(score: float) -> str:
    if score >= 75:
        return "red"
    if score >= 50:
        return "orange"
    if score >= 25:
        return "yellow"
    return "green"
