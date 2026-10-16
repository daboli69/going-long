"""Static stadium geography for travel / time-zone features.

Coordinates are public stadium locations (precision ~0.01 deg, ample for travel
distance) and IANA time zones. They are static facts, so they carry no
time-of-availability risk. Keys are nflverse/nfldata `stadium_id`; a few
neutral-site games are listed under a team's id with a foreign stadium name, so
names are checked first.
"""
from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

STADIUMS = {
    "ATL00": (33.758, -84.401, "America/New_York"), "ATL97": (33.755, -84.401, "America/New_York"),
    "BAL00": (39.278, -76.623, "America/New_York"), "BOS00": (42.091, -71.264, "America/New_York"),
    "BUF00": (42.774, -78.787, "America/New_York"), "CAR00": (35.226, -80.853, "America/New_York"),
    "CHI98": (41.862, -87.617, "America/Chicago"), "CIN00": (39.096, -84.516, "America/New_York"),
    "CLE00": (41.506, -81.700, "America/New_York"), "DAL00": (32.747, -97.095, "America/Chicago"),
    "DEN00": (39.744, -105.020, "America/Denver"), "DET00": (42.340, -83.046, "America/Detroit"),
    "GNB00": (44.501, -88.062, "America/Chicago"), "HOU00": (29.685, -95.411, "America/Chicago"),
    "IND00": (39.760, -86.164, "America/Indiana/Indianapolis"), "JAX00": (30.324, -81.637, "America/New_York"),
    "KAN00": (39.049, -94.484, "America/Chicago"), "LAX01": (33.954, -118.339, "America/Los_Angeles"),
    "LAX97": (33.864, -118.261, "America/Los_Angeles"), "LAX99": (34.014, -118.288, "America/Los_Angeles"),
    "MIA00": (25.958, -80.239, "America/New_York"), "MIN01": (44.974, -93.258, "America/Chicago"),
    "MIN98": (44.977, -93.225, "America/Chicago"), "NAS00": (36.167, -86.771, "America/Chicago"),
    "NOR00": (29.951, -90.081, "America/Chicago"), "NYC01": (40.814, -74.075, "America/New_York"),
    "OAK00": (37.752, -122.201, "America/Los_Angeles"), "PHI00": (39.901, -75.168, "America/New_York"),
    "PHO00": (33.528, -112.263, "America/Phoenix"), "PIT00": (40.447, -80.016, "America/New_York"),
    "SDG00": (32.783, -117.120, "America/Los_Angeles"), "SEA00": (47.595, -122.332, "America/Los_Angeles"),
    "SFO01": (37.403, -121.970, "America/Los_Angeles"), "STL00": (38.633, -90.189, "America/Chicago"),
    "TAM00": (27.976, -82.503, "America/New_York"), "VEG00": (36.091, -115.183, "America/Los_Angeles"),
    "WAS00": (38.908, -76.865, "America/New_York"),
    # international / neutral venues
    "LON00": (51.556, -0.280, "Europe/London"), "LON01": (51.456, -0.342, "Europe/London"),
    "LON02": (51.604, -0.066, "Europe/London"), "MEX00": (19.303, -99.151, "America/Mexico_City"),
    "GER00": (48.219, 11.625, "Europe/Berlin"), "MUN01": (48.219, 11.625, "Europe/Berlin"),
    "FRA00": (50.069, 8.646, "Europe/Berlin"), "MAD01": (40.453, -3.688, "Europe/Madrid"),
    "PAR00": (48.924, 2.360, "Europe/Paris"), "SAO00": (-23.545, -46.474, "America/Sao_Paulo"),
    "RIO00": (-22.912, -43.230, "America/Sao_Paulo"), "MEL00": (-37.820, 144.983, "Australia/Melbourne"),
}
NAME_OVERRIDES = {"tottenham": "LON02", "wembley": "LON00", "twickenham": "LON01", "azteca": "MEX00", "banorte": "MEX00",
                  "allianz": "GER00", "deutsche bank park": "FRA00", "bernabeu": "MAD01", "corinthians": "SAO00",
                  "maracana": "RIO00", "melbourne cricket": "MEL00", "stade de france": "PAR00"}


def site_key(stadium_id: str, stadium_name: str | None) -> str | None:
    name = (stadium_name or "").lower()
    for k, v in NAME_OVERRIDES.items():
        if k in name:
            return v
    return stadium_id if stadium_id in STADIUMS else None


def km(a: str | None, b: str | None) -> float:
    if a not in STADIUMS or b not in STADIUMS:
        return float("nan")
    la1, lo1, _ = STADIUMS[a]
    la2, lo2, _ = STADIUMS[b]
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    c = math.sin(p1) * math.sin(p2) + math.cos(p1) * math.cos(p2) * math.cos(dl)
    return 6371.0 * math.acos(max(-1.0, min(1.0, c)))


def utc_offset_hours(key: str | None, when: datetime) -> float:
    if key not in STADIUMS:
        return float("nan")
    return pd.Timestamp(when).tz_convert(STADIUMS[key][2]).utcoffset().total_seconds() / 3600


def local_hour(key: str | None, when_utc: datetime) -> float:
    if key not in STADIUMS:
        return float("nan")
    t = pd.Timestamp(when_utc).tz_convert(STADIUMS[key][2])
    return t.hour + t.minute / 60
