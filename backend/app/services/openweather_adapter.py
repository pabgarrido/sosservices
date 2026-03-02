"""Weather Adapter — Current conditions from OpenWeatherMap or Open-Meteo."""

from typing import List
from datetime import datetime, timedelta
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

# WMO weather code descriptions (used by Open-Meteo)
WMO_CODES = {
    0: ("Clear sky", "Clear"),
    1: ("Mainly clear", "Clear"),
    2: ("Partly cloudy", "Clouds"),
    3: ("Overcast", "Clouds"),
    45: ("Fog", "Fog"),
    48: ("Depositing rime fog", "Fog"),
    51: ("Light drizzle", "Drizzle"),
    53: ("Moderate drizzle", "Drizzle"),
    55: ("Dense drizzle", "Drizzle"),
    56: ("Light freezing drizzle", "Drizzle"),
    57: ("Dense freezing drizzle", "Drizzle"),
    61: ("Slight rain", "Rain"),
    63: ("Moderate rain", "Rain"),
    65: ("Heavy rain", "Rain"),
    66: ("Light freezing rain", "Rain"),
    67: ("Heavy freezing rain", "Rain"),
    71: ("Slight snowfall", "Snow"),
    73: ("Moderate snowfall", "Snow"),
    75: ("Heavy snowfall", "Snow"),
    77: ("Snow grains", "Snow"),
    80: ("Slight rain showers", "Rain"),
    81: ("Moderate rain showers", "Rain"),
    82: ("Violent rain showers", "Rain"),
    85: ("Slight snow showers", "Snow"),
    86: ("Heavy snow showers", "Snow"),
    95: ("Thunderstorm", "Thunderstorm"),
    96: ("Thunderstorm with slight hail", "Thunderstorm"),
    99: ("Thunderstorm with heavy hail", "Thunderstorm"),
}


class OpenWeatherAdapter(BaseAdapter):
    """Fetches current weather conditions from OpenWeatherMap or Open-Meteo (keyless fallback)."""

    def __init__(self):
        super().__init__("openweather")
        self.api_key = settings.openweathermap_api_key

    async def fetch(self) -> List[GeoEvent]:
        if self.api_key:
            return await self._fetch_openweathermap()
        else:
            self.logger.info("No OpenWeatherMap key — using Open-Meteo (free, no key)")
            return await self._fetch_open_meteo()

    async def _fetch_open_meteo(self) -> List[GeoEvent]:
        """Fetch current weather + hourly forecast from Open-Meteo API (free, no key required)."""
        events = []

        for loc in MONITOR_LOCATIONS:
            try:
                url = (
                    f"https://api.open-meteo.com/v1/forecast"
                    f"?latitude={loc['lat']}&longitude={loc['lng']}"
                    f"&current=temperature_2m,relative_humidity_2m,"
                    f"wind_speed_10m,wind_direction_10m,weather_code"
                    f"&hourly=temperature_2m,relative_humidity_2m,"
                    f"wind_speed_10m,weather_code,precipitation_probability"
                    f"&forecast_hours=48"
                    f"&timezone=Europe/Lisbon"
                )
                resp = await self._client.get(url)
                resp.raise_for_status()
                data = resp.json()

                # ── Current conditions ──
                current = data.get("current", {})
                temp = current.get("temperature_2m", 0)
                humidity = current.get("relative_humidity_2m", 0)
                wind_speed_kmh = current.get("wind_speed_10m", 0)
                wind_speed = wind_speed_kmh / 3.6  # Convert km/h to m/s
                weather_code = current.get("weather_code", 0)

                weather_desc, weather_main = WMO_CODES.get(weather_code, ("Unknown", "Unknown"))

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
                if weather_main == "Thunderstorm":
                    severity = max(severity, Severity.MEDIUM)
                    category = "thunderstorm"
                if humidity < 20 and temp > 30:
                    severity = max(severity, Severity.MEDIUM)
                    category = "fire_weather"

                event_id = hashlib.md5(
                    f"meteo_{loc['name']}_{datetime.utcnow().strftime('%Y%m%d%H')}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.WEATHER,
                    category=category,
                    title=f"{loc['name']}: {temp:.0f}°C, {weather_desc.lower()}",
                    description=(
                        f"Current conditions in {loc['name']}: "
                        f"{temp:.1f}°C, {humidity}% humidity, "
                        f"wind {wind_speed:.1f} m/s. {weather_desc}"
                    ),
                    location=Location(lat=loc["lat"], lng=loc["lng"]),
                    radius_km=15.0,
                    severity=severity,
                    source="open_meteo",
                    start_time=datetime.utcnow(),
                    metadata={
                        "temp": temp,
                        "humidity": humidity,
                        "wind_speed": round(wind_speed, 1),
                        "wind_speed_kmh": wind_speed_kmh,
                        "weather_main": weather_main,
                        "weather_description": weather_desc,
                        "weather_code": weather_code,
                        "city": loc["name"],
                        "provider": "open-meteo.com",
                        "is_forecast": False,
                    },
                ))

                # ── Hourly forecast (next 48h) ──
                hourly = data.get("hourly", {})
                times = hourly.get("time", [])
                temps = hourly.get("temperature_2m", [])
                humids = hourly.get("relative_humidity_2m", [])
                winds = hourly.get("wind_speed_10m", [])
                codes = hourly.get("weather_code", [])
                precip_probs = hourly.get("precipitation_probability", [])

                now = datetime.utcnow()

                # Sample every 3 hours to avoid flooding (16 forecast events per location)
                for i in range(0, min(len(times), 48), 3):
                    try:
                        fc_time = datetime.fromisoformat(times[i])
                    except (ValueError, IndexError):
                        continue

                    # Only include future forecasts
                    if fc_time <= now:
                        continue

                    fc_temp = temps[i] if i < len(temps) else 0
                    fc_humid = humids[i] if i < len(humids) else 50
                    fc_wind_kmh = winds[i] if i < len(winds) else 0
                    fc_wind = fc_wind_kmh / 3.6
                    fc_code = codes[i] if i < len(codes) else 0
                    fc_precip = precip_probs[i] if i < len(precip_probs) else 0

                    fc_desc, fc_main = WMO_CODES.get(fc_code, ("Unknown", "Unknown"))

                    # Determine forecast severity
                    fc_severity = Severity.LOW
                    fc_category = "forecast"

                    if fc_temp > 38:
                        fc_severity = Severity.MEDIUM
                        fc_category = "forecast_extreme_heat"
                    if fc_temp > 42:
                        fc_severity = Severity.HIGH
                        fc_category = "forecast_extreme_heat"
                    if fc_wind > 15:
                        fc_severity = max(fc_severity, Severity.MEDIUM)
                        fc_category = "forecast_strong_wind"
                    if fc_wind > 25:
                        fc_severity = Severity.HIGH
                        fc_category = "forecast_storm_wind"
                    if fc_main == "Thunderstorm":
                        fc_severity = max(fc_severity, Severity.MEDIUM)
                        fc_category = "forecast_thunderstorm"
                    if fc_precip > 70:
                        fc_severity = max(fc_severity, Severity.MEDIUM)
                        fc_category = "forecast_heavy_rain"
                    if fc_humid < 20 and fc_temp > 30:
                        fc_severity = max(fc_severity, Severity.MEDIUM)
                        fc_category = "forecast_fire_weather"

                    hours_ahead = round((fc_time - now).total_seconds() / 3600)

                    fc_event_id = hashlib.md5(
                        f"meteo_fc_{loc['name']}_{times[i]}".encode()
                    ).hexdigest()

                    events.append(GeoEvent(
                        id=fc_event_id,
                        type=EventType.WEATHER,
                        category=fc_category,
                        title=f"[+{hours_ahead}h] {loc['name']}: {fc_temp:.0f}°C, {fc_desc.lower()}",
                        description=(
                            f"Forecast for {loc['name']} in {hours_ahead}h: "
                            f"{fc_temp:.1f}°C, {fc_humid}% humidity, "
                            f"wind {fc_wind:.1f} m/s, rain {fc_precip}%. {fc_desc}"
                        ),
                        location=Location(lat=loc["lat"], lng=loc["lng"]),
                        radius_km=15.0,
                        severity=fc_severity,
                        source="open_meteo",
                        start_time=fc_time,
                        end_time=fc_time + timedelta(hours=3),
                        metadata={
                            "temp": fc_temp,
                            "humidity": fc_humid,
                            "wind_speed": round(fc_wind, 1),
                            "wind_speed_kmh": fc_wind_kmh,
                            "weather_main": fc_main,
                            "weather_description": fc_desc,
                            "weather_code": fc_code,
                            "precip_prob": fc_precip,
                            "city": loc["name"],
                            "provider": "open-meteo.com",
                            "is_forecast": True,
                            "forecast_hours": hours_ahead,
                        },
                    ))

            except Exception as e:
                self.logger.debug(f"Open-Meteo failed for {loc['name']}: {e}")
                continue

        return events

    async def _fetch_openweathermap(self) -> List[GeoEvent]:
        """Fetch from OpenWeatherMap (requires API key)."""
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
