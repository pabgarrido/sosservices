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
                lat, lng = self._area_to_coords(area_id)

                event_id = hashlib.md5(
                    f"ipma_warning_{area_id}_{start}_{awareness_type}".encode()
                ).hexdigest()

                severity = WEATHER_SEVERITY_MAP.get(awareness_level, Severity.LOW)

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.WEATHER,
                    category=f"weather_warning_{awareness_type.lower().replace(' ', '_')}",
                    title=f"IPMA {awareness_level.upper()} Warning: {awareness_type}",
                    description=warning.get("text", f"{awareness_type} warning for {area_id}"),
                    location=Location(lat=lat, lng=lng),
                    radius_km=30.0,
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
        """Fetch district-level forecast data from IPMA."""
        events = []
        try:
            url = f"{self.base_url}/forecast/meteorology/cities/daily/hp-daily-forecast-day0.json"
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json().get("data", [])

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
                category = "weather_forecast"

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
                    category = "heavy_rain_risk"
                if temp_max_val > 38:
                    severity = Severity.MEDIUM
                    category = "extreme_heat"
                if temp_max_val > 42:
                    severity = Severity.HIGH
                    category = "extreme_heat"
                if int(wind_class or 0) >= 4:
                    severity = Severity.MEDIUM
                    category = "strong_wind"

                event_id = hashlib.md5(
                    f"ipma_forecast_{global_id}_{datetime.utcnow().date()}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.WEATHER,
                    category=category,
                    title=f"{district['name']}: {temp_min}°–{temp_max}°C, Rain {precip_prob}%",
                    description=(
                        f"Forecast for {district['name']}: "
                        f"Temperature {temp_min}°–{temp_max}°C, "
                        f"Precipitation probability {precip_prob}%, "
                        f"Wind class {wind_class}"
                    ),
                    location=Location(lat=district["lat"], lng=district["lng"]),
                    radius_km=20.0,
                    severity=severity,
                    source="ipma",
                    start_time=datetime.utcnow().replace(hour=0, minute=0, second=0),
                    end_time=datetime.utcnow().replace(hour=23, minute=59, second=59),
                    metadata={
                        "temp_max": temp_max,
                        "temp_min": temp_min,
                        "wind_class": wind_class,
                        "precip_prob": precip_prob,
                        "district": district["name"],
                    },
                ))
        except Exception as e:
            self.logger.warning(f"Failed to fetch IPMA forecasts: {e}")

        return events

    def _area_to_coords(self, area_id: str) -> tuple:
        """Map an IPMA area ID to approximate coordinates."""
        # IPMA area IDs don't directly map to globalIdLocal
        # Default to center of Portugal
        return 39.5, -8.0

    def _parse_time(self, time_str: str) -> datetime:
        """Parse IPMA time format."""
        if not time_str:
            return datetime.utcnow()
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return datetime.utcnow()
