"""OpenWeatherMap Adapter — Current conditions and severe weather."""

from typing import List
from datetime import datetime
import hashlib

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


# Major Portuguese cities and towns for weather monitoring
MONITOR_LOCATIONS = [
    {"name": "Lisboa", "lat": 38.7223, "lng": -9.1393},
    {"name": "Porto", "lat": 41.1579, "lng": -8.6291},
    {"name": "Faro", "lat": 37.0194, "lng": -7.9322},
    {"name": "Coimbra", "lat": 40.2115, "lng": -8.4292},
    {"name": "Braga", "lat": 41.5503, "lng": -8.4200},
    {"name": "Funchal", "lat": 32.6669, "lng": -16.9241},
    {"name": "Ponta Delgada", "lat": 37.7483, "lng": -25.6666},
    {"name": "Évora", "lat": 38.5711, "lng": -7.9093},
    {"name": "Beja", "lat": 38.0154, "lng": -7.8631},
    {"name": "Viseu", "lat": 40.6610, "lng": -7.9097},
    {"name": "Leiria", "lat": 39.7437, "lng": -8.8071},
    {"name": "Setúbal", "lat": 38.5254, "lng": -8.8882},
    {"name": "Castelo Branco", "lat": 39.8222, "lng": -7.4914},
    {"name": "Guarda", "lat": 40.5373, "lng": -7.2676},
    {"name": "Vila Real", "lat": 41.2960, "lng": -7.7469},
    {"name": "Bragança", "lat": 41.8072, "lng": -6.7589},
    {"name": "Santarém", "lat": 39.2369, "lng": -8.6850},
    {"name": "Portalegre", "lat": 39.2967, "lng": -7.4310},
]


class OpenWeatherAdapter(BaseAdapter):
    """Fetches current weather conditions from OpenWeatherMap."""

    def __init__(self):
        super().__init__("openweather")
        self.api_key = settings.openweathermap_api_key

    async def fetch(self) -> List[GeoEvent]:
        if not self.api_key:
            self.logger.warning("OpenWeatherMap API key not configured")
            return []

        events = []

        for loc in MONITOR_LOCATIONS:
            try:
                url = (
                    f"https://api.openweathermap.org/data/2.5/weather"
                    f"?lat={loc['lat']}&lon={loc['lng']}"
                    f"&appid={self.api_key}&units=metric"
                )
                resp = await self._client.get(url)
                resp.raise_for_status()
                data = resp.json()

                temp = data.get("main", {}).get("temp", 0)
                humidity = data.get("main", {}).get("humidity", 0)
                wind_speed = data.get("wind", {}).get("speed", 0)
                weather_desc = data.get("weather", [{}])[0].get("description", "")
                weather_main = data.get("weather", [{}])[0].get("main", "")

                # Determine severity
                severity = Severity.LOW
                category = "current_weather"

                if temp > 38:
                    severity = Severity.MEDIUM
                    category = "extreme_heat"
                if temp > 42:
                    severity = Severity.HIGH
                    category = "extreme_heat"
                if wind_speed > 15:  # m/s (~54 km/h)
                    severity = max(severity, Severity.MEDIUM)
                    category = "strong_wind"
                if wind_speed > 25:  # m/s (~90 km/h)
                    severity = Severity.HIGH
                    category = "storm_wind"
                if weather_main in ("Thunderstorm",):
                    severity = max(severity, Severity.MEDIUM)
                    category = "thunderstorm"
                if humidity < 20 and temp > 30:
                    severity = max(severity, Severity.MEDIUM)
                    category = "fire_weather"

                event_id = hashlib.md5(
                    f"owm_{loc['name']}_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.WEATHER,
                    category=category,
                    title=f"{loc['name']}: {temp:.0f}°C, {weather_desc}",
                    description=(
                        f"Current conditions in {loc['name']}: "
                        f"{temp:.1f}°C, {humidity}% humidity, "
                        f"wind {wind_speed:.1f} m/s. {weather_desc.capitalize()}"
                    ),
                    location=Location(lat=loc["lat"], lng=loc["lng"]),
                    radius_km=15.0,
                    severity=severity,
                    source="openweathermap",
                    start_time=datetime.utcnow(),
                    metadata={
                        "temp": temp,
                        "humidity": humidity,
                        "wind_speed": wind_speed,
                        "weather_main": weather_main,
                        "weather_description": weather_desc,
                        "city": loc["name"],
                    },
                ))

            except Exception as e:
                self.logger.debug(f"Failed to fetch weather for {loc['name']}: {e}")
                continue

        return events
