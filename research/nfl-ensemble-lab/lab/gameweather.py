"""Kickoff weather for the Game Center from Open-Meteo (free, no API key, no account).

Display only: weather does not change any forecast. Forecasts exist about 15 days ahead; finished games show the
recorded weather. Results are cached in data/cache/weather so each game is fetched at most every few hours.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import pandas as pd

from .config import CACHE_DIR

CACHE = CACHE_DIR / "weather"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HORIZON_DAYS = 15  # Open-Meteo forecasts reach 16 days; one day of slack keeps the kickoff window inside it
PAST_DAYS = 90
REFRESH_HOURS = 3

# Latitude and longitude of every venue on the 2026 schedule, keyed by the schedule's stadium name.
STADIUMS = {
    "AT&T Stadium": (32.7473, -97.0945), "Acrisure Stadium": (40.4468, -80.0158), "Allegiant Stadium": (36.0909, -115.1833),
    "Bank of America Stadium": (35.2258, -80.8528), "Bernabeu": (40.4531, -3.6883), "Caesars Superdome": (29.9511, -90.0812),
    "Empower Field at Mile High": (39.7439, -105.0201), "Estadio Banorte": (19.3029, -99.1505), "EverBank Stadium": (30.3239, -81.6373),
    "FC Bayern Munich Stadium": (48.2188, 11.6247), "Ford Field": (42.3400, -83.0456), "GEHA Field at Arrowhead Stadium": (39.0489, -94.4839),
    "Gillette Stadium": (42.0909, -71.2643), "Hard Rock Stadium": (25.9580, -80.2389), "Highmark Stadium": (42.7738, -78.7870),
    "Huntington Bank Field": (41.5061, -81.6995), "Lambeau Field": (44.5013, -88.0622), "Levi's Stadium": (37.4033, -121.9694),
    "Lincoln Financial Field": (39.9008, -75.1675), "Lucas Oil Stadium": (39.7601, -86.1639), "Lumen Field": (47.5952, -122.3316),
    "M&T Bank Stadium": (39.2780, -76.6227), "Maracana Stadium": (-22.9121, -43.2302), "Melbourne Cricket Ground": (-37.8200, 144.9834),
    "Mercedes-Benz Stadium": (33.7554, -84.4008), "MetLife Stadium": (40.8135, -74.0745), "Nissan Stadium": (36.1665, -86.7713),
    "Northwest Stadium": (38.9078, -76.8645), "Paycor Stadium": (39.0955, -84.5161), "Raymond James Stadium": (27.9759, -82.5033),
    "Reliant Stadium": (29.6847, -95.4107), "SoFi Stadium": (33.9535, -118.3392), "Soldier Field": (41.8623, -87.6167),
    "Stade de France": (48.9245, 2.3602), "State Farm Stadium": (33.5276, -112.2626), "Tottenham Hotspur Stadium": (51.6043, -0.0664),
    "U.S. Bank Stadium": (44.9737, -93.2577), "Wembley Stadium": (51.5560, -0.2795),
}
RETRACTABLE = {"AT&T Stadium", "Lucas Oil Stadium", "Mercedes-Benz Stadium", "Reliant Stadium", "State Farm Stadium"}
INDOORS = {"Allegiant Stadium", "Caesars Superdome", "Ford Field", "SoFi Stadium", "U.S. Bank Stadium"}
# The schedule marks these open-air venues as domes; they have no roof over the field.
OPEN_AIR = {"FC Bayern Munich Stadium", "Melbourne Cricket Ground", "Stade de France"}

CODES = [(0, "Clear"), (3, "Partly cloudy"), (48, "Fog"), (57, "Drizzle"), (67, "Rain"), (77, "Snow"), (82, "Rain showers"),
         (86, "Snow showers"), (99, "Thunderstorms")]


def describe(code: int) -> str:
    if code in (2, 3):
        return "Cloudy" if code == 3 else "Partly cloudy"
    return next(text for top, text in CODES if code <= top)


def roof_kind(stadium: str, roof: str | None) -> str:
    if stadium in OPEN_AIR:
        return "outdoors"
    if stadium in INDOORS or (roof == "dome" and stadium not in RETRACTABLE):
        return "indoors"
    if stadium in RETRACTABLE:
        return "retractable"
    return "outdoors"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "nfl-ensemble-lab (local research)"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.load(resp)


def _summary(data: dict, kickoff: pd.Timestamp) -> dict | None:
    h = pd.DataFrame(data.get("hourly") or {})
    if h.empty:
        return None
    h["time"] = pd.to_datetime(h["time"], utc=True)
    start = kickoff.floor("h")
    w = h[(h["time"] >= start) & (h["time"] <= start + pd.Timedelta(hours=3))]
    if w.empty:
        return None
    k = w.iloc[0]
    precip = w["precipitation_probability"].dropna()
    return {"temp_f": round(float(k["temperature_2m"])), "condition": describe(int(k["weather_code"])),
            "wind_mph": round(float(w["wind_speed_10m"].max())), "gust_mph": round(float(w["wind_gusts_10m"].max())),
            "precip_chance": int(precip.max()) if len(precip) else None, "precip_in": round(float(w["precipitation"].sum()), 2)}


def kickoff_weather(gid: str, stadium: str, roof: str | None, kickoff_utc: pd.Timestamp, completed: bool, fetch=_get) -> dict:
    kind = roof_kind(stadium, roof)
    out = {"stadium": stadium, "roof": kind, "source": "Open-Meteo"}
    if kind == "indoors":
        return out | {"status": "indoors", "text": "Indoors, so weather does not apply."}
    if kind == "retractable" and completed and roof == "closed":
        return out | {"status": "indoors", "text": "The roof was closed, so weather did not apply."}
    if stadium not in STADIUMS:
        return out | {"status": "unavailable", "text": "No location saved for this stadium."}
    now = pd.Timestamp.now(tz="UTC")
    if kickoff_utc - now > pd.Timedelta(days=HORIZON_DAYS):
        return out | {"status": "too_early", "text": f"Forecast becomes available about {HORIZON_DAYS} days before kickoff."}
    if now - kickoff_utc > pd.Timedelta(days=PAST_DAYS):
        return out | {"status": "unavailable", "text": "Recorded weather is only kept for the last 90 days."}

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{gid}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        age = now - pd.Timestamp(cached["fetched_at"])
        if (cached.get("final") and completed) or age < pd.Timedelta(hours=REFRESH_HOURS):
            return cached["weather"]

    lat, lon = STADIUMS[stadium]
    day = kickoff_utc.strftime("%Y-%m-%d")
    end = min(kickoff_utc + pd.Timedelta(hours=4), now + pd.Timedelta(days=HORIZON_DAYS)).strftime("%Y-%m-%d")
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "timezone": "UTC", "start_date": day, "end_date": end,
                                "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
                                "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch"})
    try:
        s = _summary(fetch(f"{FORECAST_URL}?{q}"), kickoff_utc)
    except Exception as e:  # network down or service error: say so, never guess
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["weather"]
        return out | {"status": "unavailable", "text": f"Weather service could not be reached ({type(e).__name__})."}
    if s is None:
        return out | {"status": "unavailable", "text": "The weather service returned no data for kickoff."}
    recorded = kickoff_utc < now
    weather = out | s | {"status": "recorded" if recorded else "forecast", "fetched_at": now.isoformat(),
                         "text": ("Recorded at kickoff" if recorded else "Forecast for kickoff")
                         + ((". The roof was open." if roof == "open" and recorded else ". Retractable roof; it may be closed.") if kind == "retractable" else ".")}
    path.write_text(json.dumps({"fetched_at": now.isoformat(), "final": bool(completed and recorded), "weather": weather}), encoding="utf-8")
    return weather
