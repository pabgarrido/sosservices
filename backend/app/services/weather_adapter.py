"""IPMA Weather Adapter — Portuguese Meteorological Institute (api.ipma.pt)"""

from typing import List
from datetime import datetime, timedelta
import hashlib

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


# IPMA district coordinates (mainland Portugal)
DISTRICT_COORDS = {
    1010500: {"name": "Aveiro", "lat": 40.6405, "lng": -8.6538},
    1020500: {"name": "Beja", "lat": 38.0154, "lng": -7.8631},
    1030300: {"name": "Braga", "lat": 41.5503, "lng": -8.4200},
    1040200: {"name": "Bragança", "lat": 41.8072, "lng": -6.7589},
    1050200: {"name": "Castelo Branco", "lat": 39.8222, "lng": -7.4914},
    1060300: {"name": "Coimbra", "lat": 40.2115, "lng": -8.4292},
    1070500: {"name": "Évora", "lat": 38.5711, "lng": -7.9093},
    1080500: {"name": "Faro", "lat": 37.0194, "lng": -7.9322},
    1090700: {"name": "Guarda", "lat": 40.5373, "lng": -7.2676},
    1100900: {"name": "Leiria", "lat": 39.7437, "lng": -8.8071},
    1110600: {"name": "Lisboa", "lat": 38.7223, "lng": -9.1393},
    1121400: {"name": "Portalegre", "lat": 39.2967, "lng": -7.4310},
    1131200: {"name": "Porto", "lat": 41.1579, "lng": -8.6291},
    1141600: {"name": "Santarém", "lat": 39.2369, "lng": -8.6850},
    1151200: {"name": "Setúbal", "lat": 38.5254, "lng": -8.8882},
    1160900: {"name": "Viana do Castelo", "lat": 41.6935, "lng": -8.8327},
    1171400: {"name": "Vila Real", "lat": 41.2960, "lng": -7.7469},
    1180500: {"name": "Viseu", "lat": 40.6610, "lng": -7.9097},
}

# IPMA weather type mapping
WEATHER_SEVERITY_MAP = {
    # Awareness levels from IPMA
    "green": Severity.LOW,
    "yellow": Severity.MEDIUM,
    "orange": Severity.HIGH,
    "red": Severity.CRITICAL,
}


class IPMAWeatherAdapter(BaseAdapter):
    """Fetches weather warnings and forecasts from IPMA."""

    def __init__(self):
        super().__init__("ipma_weather")
        self.base_url = settings.ipma_base_url

    async def fetch(self) -> List[GeoEvent]:
        events: List[GeoEvent] = []

        # Fetch weather warnings
        warning_events = await self._fetch_warnings()
        events.extend(warning_events)

        # Fetch current forecasts for each district
        forecast_events = await self._fetch_forecasts()
        events.extend(forecast_events)

        return events

    async def _fetch_warnings(self) -> List[GeoEvent]:
        """Fetch active weather warnings from IPMA."""
        events = []
        try:
            url = f"{self.base_url}/forecast/warnings/warnings_www.json"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()

            for warning in data:
                awareness_level = warning.get("awarenessLevelID", "green")
                if awareness_level == "green":
                    continue  # Skip normal conditions

                awareness_type = warning.get("awarenessTypeName", "Unknown")
                area_id = warning.get("idAreaAviso", "")
                start = warning.get("startTime", "")
                end = warning.get("endTime", "")

                # Map area to coordinates (approximate by district)
                coords = self._area_to_coords(area_id)
                if coords[0] is None:
                    continue  # Unknown area — skip

                lat, lng = coords

                event_id = hashlib.md5(
                    f"ipma_warning_{area_id}_{start}_{awareness_type}".encode()
                ).hexdigest()

                severity = WEATHER_SEVERITY_MAP.get(awareness_level, Severity.LOW)

                # Label maritime/island zones in the title
                MARITIME_AREAS = {"MCN", "MCS", "MPS"}
                AREA_LABELS = {
                    "MCN": "Mar Costa Norte",
                    "MCS": "Mar Costa Sul",
                    "MPS": "Porto Santo",
                    "MRM": "Madeira",
                    "ACE": "Açores (Este)",
                    "AOC": "Açores (Central)",
                    "AOR": "Açores (Oeste)",
                }
                area_label = AREA_LABELS.get(area_id, "")
                if area_label:
                    title = f"IPMA {awareness_level.upper()} Warning: {awareness_type} — {area_label}"
                else:
                    title = f"IPMA {awareness_level.upper()} Warning: {awareness_type}"

                # Maritime zones get larger radius but reduced severity
                # (they are offshore, not affecting land populations the same way)
                if area_id in MARITIME_AREAS:
                    radius = 50.0
                else:
                    radius = 30.0

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.WEATHER,
                    category=f"weather_warning_{awareness_type.lower().replace(' ', '_')}",
                    title=title,
                    description=warning.get("text", f"{awareness_type} warning for {area_id}"),
                    location=Location(lat=lat, lng=lng),
                    radius_km=radius,
                    severity=severity,
                    source="ipma",
                    start_time=self._parse_time(start),
                    end_time=self._parse_time(end) if end else None,
                    metadata={
                        "awareness_level": awareness_level,
                        "awareness_type": awareness_type,
                        "area_id": area_id,
                        "raw": warning,
                    },
                ))
        except Exception as e:
            self.logger.warning(f"Failed to fetch IPMA warnings: {e}")

        return events

    async def _fetch_forecasts(self) -> List[GeoEvent]:
        """Fetch district-level forecast data from IPMA (day0 through day4)."""
        events = []

        for day_offset in range(5):  # day0 = today, day1 = tomorrow, ..., day4
            try:
                url = f"{self.base_url}/forecast/meteorology/cities/daily/hp-daily-forecast-day{day_offset}.json"
                resp = await self._client.get(url)
                resp.raise_for_status()
                data = resp.json().get("data", [])

                forecast_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset)
                is_forecast = day_offset > 0

                for forecast in data:
                    global_id = forecast.get("globalIdLocal")
                    if global_id not in DISTRICT_COORDS:
                        continue

                    district = DISTRICT_COORDS[global_id]
                    temp_max = forecast.get("tMax", "")
                    temp_min = forecast.get("tMin", "")
                    wind_class = forecast.get("classWindSpeed", 0)
                    precip_prob = forecast.get("precipitaProb", "0")

                    # Only create events for notable conditions
                    severity = Severity.LOW
                    category = "weather_forecast" if not is_forecast else "forecast"

                    try:
                        precip_val = float(precip_prob)
                    except (ValueError, TypeError):
                        precip_val = 0

                    try:
                        temp_max_val = float(temp_max)
                    except (ValueError, TypeError):
                        temp_max_val = 20

                    if precip_val > 70:
                        severity = Severity.MEDIUM
                        category = "forecast_heavy_rain" if is_forecast else "heavy_rain_risk"
                    if temp_max_val > 38:
                        severity = Severity.MEDIUM
                        category = "forecast_extreme_heat" if is_forecast else "extreme_heat"
                    if temp_max_val > 42:
                        severity = Severity.HIGH
                        category = "forecast_extreme_heat" if is_forecast else "extreme_heat"
                    if int(wind_class or 0) >= 4:
                        severity = Severity.MEDIUM
                        category = "forecast_strong_wind" if is_forecast else "strong_wind"

                    day_label = f"[+{day_offset}d] " if is_forecast else ""

                    event_id = hashlib.md5(
                        f"ipma_forecast_{global_id}_{forecast_date.date()}".encode()
                    ).hexdigest()

                    events.append(GeoEvent(
                        id=event_id,
                        type=EventType.WEATHER,
                        category=category,
                        title=f"{day_label}{district['name']}: {temp_min}°–{temp_max}°C, Rain {precip_prob}%",
                        description=(
                            f"{'Forecast' if is_forecast else 'Today'} for {district['name']} "
                            f"({forecast_date.strftime('%a %d %b')}): "
                            f"Temperature {temp_min}°–{temp_max}°C, "
                            f"Precipitation probability {precip_prob}%, "
                            f"Wind class {wind_class}"
                        ),
                        location=Location(lat=district["lat"], lng=district["lng"]),
                        radius_km=20.0,
                        severity=severity,
                        source="ipma",
                        start_time=forecast_date,
                        end_time=forecast_date + timedelta(hours=23, minutes=59, seconds=59),
                        metadata={
                            "temp_max": temp_max,
                            "temp_min": temp_min,
                            "wind_class": wind_class,
                            "precip_prob": precip_prob,
                            "district": district["name"],
                            "is_forecast": is_forecast,
                            "forecast_day": day_offset,
                        },
                    ))
            except Exception as e:
                self.logger.warning(f"Failed to fetch IPMA forecast day{day_offset}: {e}")

        return events

    def _area_to_coords(self, area_id: str) -> tuple:
        """Map an IPMA warning area ID to approximate coordinates.

        IPMA uses two types of area IDs:
        - Land districts (3-letter codes like AVR, BGC, LSB …) → plot at district capitals
        - Maritime / island zones (MCN, MCS, MPS, MRM, ACE, AOC, AOR) → plot at
          representative ocean/island points far from mainland to avoid confusion
        """
        AREA_COORDS = {
            # ── Mainland district capitals ──
            "AVR": (40.6405, -8.6538),   # Aveiro
            "BJA": (38.0154, -7.8631),   # Beja
            "BRG": (41.5503, -8.4200),   # Braga
            "BGC": (41.8072, -6.7589),   # Bragança
            "CBO": (39.8222, -7.4914),   # Castelo Branco
            "CBR": (40.2115, -8.4292),   # Coimbra
            "EVR": (38.5711, -7.9093),   # Évora
            "FAR": (37.0194, -7.9322),   # Faro
            "GDA": (40.5373, -7.2676),   # Guarda
            "LRA": (39.7437, -8.8071),   # Leiria
            "LSB": (38.7223, -9.1393),   # Lisboa
            "PTG": (39.2967, -7.4310),   # Portalegre
            "PTO": (41.1579, -8.6291),   # Porto
            "STM": (39.2369, -8.6850),   # Santarém
            "STB": (38.5254, -8.8882),   # Setúbal
            "VCT": (41.6935, -8.8327),   # Viana do Castelo
            "VRL": (41.2960, -7.7469),   # Vila Real
            "VIS": (40.6610, -7.9097),   # Viseu
            # ── Maritime zones — placed offshore so they don't mislead land users ──
            "MCN": (41.5, -9.8),         # Mar Costa Norte (north coast sea)
            "MCS": (37.0, -9.5),         # Mar Costa Sul (south coast sea)
            # ── Azores groups ──
            "ACE": (37.7412, -25.6756),  # Açores — Eastern (São Miguel)
            "AOC": (38.5345, -28.6299),  # Açores — Central (Faial)
            "AOR": (39.4500, -31.1100),  # Açores — Western (Flores)
            # ── Madeira ──
            "MRM": (32.6669, -16.9241),  # Madeira (Funchal region)
            "MPS": (33.0600, -16.3400),  # Porto Santo
        }

        coords = AREA_COORDS.get(area_id)
        if coords:
            return coords

        # Unknown area — log and skip by returning None sentinel
        self.logger.warning(f"Unknown IPMA area ID '{area_id}', skipping")
        return None, None

    def _parse_time(self, time_str: str) -> datetime:
        """Parse IPMA time format."""
        if not time_str:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return datetime.utcnow()
