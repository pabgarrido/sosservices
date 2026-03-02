"""
Hazard Correlation Engine — Detects compound risks from overlapping events.

This engine analyzes all active GeoEvents and identifies situations where
the combination of multiple factors creates elevated risk. It generates
HazardAlerts when correlation rules are triggered.
"""

from typing import List, Dict
from datetime import datetime, timedelta
from itertools import combinations
import hashlib
import logging
import math

from app.models import (
    GeoEvent, HazardAlert, EventType, Severity, HazardLevel, Location,
)
from app.config import settings

logger = logging.getLogger("analytics.correlation")


SEVERITY_RANK = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}

HAZARD_LEVEL_RANK = {
    HazardLevel.NONE: 0,
    HazardLevel.WATCH: 1,
    HazardLevel.WARNING: 2,
    HazardLevel.DANGER: 3,
    HazardLevel.EXTREME: 4,
}


def severity_at_least(severity: Severity, minimum: Severity) -> bool:
    return SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK.get(minimum, 0)


def haversine_km(loc1: Location, loc2: Location) -> float:
    """Calculate distance in km between two points."""
    R = 6371.0
    lat1, lon1 = math.radians(loc1.lat), math.radians(loc1.lng)
    lat2, lon2 = math.radians(loc2.lat), math.radians(loc2.lng)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def midpoint(loc1: Location, loc2: Location) -> Location:
    """Calculate geographic midpoint of two locations."""
    return Location(
        lat=(loc1.lat + loc2.lat) / 2,
        lng=(loc1.lng + loc2.lng) / 2,
    )


class CorrelationEngine:
    """
    Analyzes active events and generates hazard alerts based on
    spatial and temporal correlation rules.
    """

    def __init__(self):
        self.rules = [
            self._rule_fire_weather,
            self._rule_fire_wind_dry,
            self._rule_flood_risk,
            self._rule_multi_fire_cluster,
            self._rule_emergency_concentration,
            self._rule_extreme_heat_fire,
        ]
        self._previous_alerts: Dict[str, HazardAlert] = {}

    def analyze(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """Run all correlation rules on active events and return alerts."""
        active_events = [e for e in events if e.active]
        alerts: List[HazardAlert] = []

        for rule in self.rules:
            try:
                rule_alerts = rule(active_events)
                alerts.extend(rule_alerts)
            except Exception as e:
                logger.error(f"Correlation rule {rule.__name__} failed: {e}")

        # Deduplicate alerts (same location + same contributing events)
        alerts = self._deduplicate(alerts)

        # Update cache
        self._previous_alerts = {a.id: a for a in alerts}

        logger.info(f"Correlation engine produced {len(alerts)} alerts from {len(active_events)} events")
        return alerts

    # ------------------------------------------------------------------
    # CORRELATION RULES
    # ------------------------------------------------------------------

    def _rule_fire_weather(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: Active fire + adverse weather conditions nearby = elevated risk."""
        alerts = []

        fires = [e for e in events if e.type == EventType.EMERGENCY
                 and e.category in ("wildfire", "wildfire_detection")]
        weather = [
            e for e in events
            if e.type == EventType.WEATHER and severity_at_least(e.severity, Severity.MEDIUM)
        ]

        for fire in fires:
            for wx in weather:
                dist = haversine_km(fire.location, wx.location)
                if dist <= settings.hazard_radius_km * 3:  # 30km proximity
                    wind_speed = wx.metadata.get("wind_speed", 0)
                    humidity = wx.metadata.get("humidity", 100)

                    # Fire + strong wind = danger
                    if wind_speed > 10 or humidity < 30:
                        level = HazardLevel.DANGER
                        if wind_speed > 20 or fire.severity == Severity.CRITICAL:
                            level = HazardLevel.EXTREME

                        alert_id = hashlib.md5(
                            f"fire_weather_{fire.id}_{wx.id}".encode()
                        ).hexdigest()

                        alerts.append(HazardAlert(
                            id=alert_id,
                            level=level,
                            title="Fire + Adverse Weather Risk",
                            description=(
                                f"Active fire detected near {fire.location.lat:.3f}, "
                                f"{fire.location.lng:.3f} with adverse weather conditions: "
                                f"wind {wind_speed:.1f} m/s, humidity {humidity}%. "
                                f"Risk of rapid fire spread."
                            ),
                            location=midpoint(fire.location, wx.location),
                            radius_km=dist + 5,
                            contributing_events=[fire.id, wx.id],
                            recommended_action=(
                                "Monitor fire progression. Alert nearby populations. "
                                "Pre-position firefighting resources downwind."
                            ),
                            expires_at=datetime.utcnow() + timedelta(hours=2),
                        ))
        return alerts

    def _rule_fire_wind_dry(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: High temperature + low humidity + wind = fire weather conditions."""
        alerts = []

        weather_events = [e for e in events if e.type == EventType.WEATHER]

        for wx in weather_events:
            temp = wx.metadata.get("temp", wx.metadata.get("temp_max", 0))
            humidity = wx.metadata.get("humidity", 100)
            wind_speed = wx.metadata.get("wind_speed", 0)
            wind_class = wx.metadata.get("wind_class", 0)

            try:
                temp = float(temp)
                humidity = float(humidity)
                wind_speed = float(wind_speed)
            except (ValueError, TypeError):
                continue

            # Fire Weather Index: hot + dry + windy
            if temp > 35 and humidity < 25 and (wind_speed > 8 or int(wind_class or 0) >= 3):
                level = HazardLevel.WARNING
                if temp > 40 or humidity < 15:
                    level = HazardLevel.DANGER

                alert_id = hashlib.md5(
                    f"fire_weather_conditions_{wx.id}".encode()
                ).hexdigest()

                city = wx.metadata.get("city", wx.metadata.get("district", "Unknown"))
                alerts.append(HazardAlert(
                    id=alert_id,
                    level=level,
                    title=f"Fire Weather Conditions — {city}",
                    description=(
                        f"Conditions conducive to wildfire near {city}: "
                        f"{temp:.0f}°C, {humidity:.0f}% humidity, "
                        f"wind {wind_speed:.1f} m/s. "
                        f"High risk of fire ignition and rapid spread."
                    ),
                    location=wx.location,
                    radius_km=25.0,
                    contributing_events=[wx.id],
                    recommended_action=(
                        "Issue fire weather alert. Restrict outdoor burning. "
                        "Pre-position resources in high-risk areas."
                    ),
                    expires_at=datetime.utcnow() + timedelta(hours=6),
                ))
        return alerts

    def _rule_flood_risk(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: Heavy rain warnings in known flood-prone areas."""
        alerts = []

        rain_events = [
            e for e in events
            if e.type == EventType.WEATHER
            and e.category in (
                "heavy_rain_risk",
                "weather_warning_precipitation",
                "weather_warning_heavy_rain",
            )
            and severity_at_least(e.severity, Severity.MEDIUM)
        ]

        for rain in rain_events:
            precip_prob = rain.metadata.get("precip_prob", "0")
            try:
                precip_val = float(precip_prob)
            except (ValueError, TypeError):
                precip_val = 0

            if precip_val > 70 or severity_at_least(rain.severity, Severity.HIGH):
                level = HazardLevel.WARNING
                if rain.severity == Severity.CRITICAL:
                    level = HazardLevel.DANGER

                alert_id = hashlib.md5(
                    f"flood_risk_{rain.id}".encode()
                ).hexdigest()

                alerts.append(HazardAlert(
                    id=alert_id,
                    level=level,
                    title="Flood Risk — Heavy Rain",
                    description=(
                        f"Heavy rainfall expected near {rain.location.lat:.3f}, "
                        f"{rain.location.lng:.3f}. "
                        f"Precipitation probability: {precip_prob}%. "
                        f"Monitor river levels and low-lying areas."
                    ),
                    location=rain.location,
                    radius_km=20.0,
                    contributing_events=[rain.id],
                    recommended_action=(
                        "Monitor river gauges. Alert populations in flood-prone areas. "
                        "Prepare evacuation routes if levels rise."
                    ),
                    expires_at=rain.end_time or (datetime.utcnow() + timedelta(hours=12)),
                ))
        return alerts

    def _rule_multi_fire_cluster(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: Multiple fires in close proximity = potential fire front."""
        alerts = []

        fires = [e for e in events if e.type == EventType.EMERGENCY
                 and e.category in ("wildfire_detection", "wildfire")]

        if len(fires) < 2:
            return alerts

        # Find clusters of fires within 15km of each other
        visited = set()
        for i, fire1 in enumerate(fires):
            if fire1.id in visited:
                continue
            cluster = [fire1]
            for j, fire2 in enumerate(fires):
                if i == j or fire2.id in visited:
                    continue
                if haversine_km(fire1.location, fire2.location) < 15:
                    cluster.append(fire2)
                    visited.add(fire2.id)

            if len(cluster) >= 3:
                # 3+ fires in close proximity = fire front
                visited.add(fire1.id)
                center_lat = sum(f.location.lat for f in cluster) / len(cluster)
                center_lng = sum(f.location.lng for f in cluster) / len(cluster)
                max_dist = max(
                    haversine_km(cluster[0].location, f.location) for f in cluster
                )

                alert_id = hashlib.md5(
                    f"fire_cluster_{'_'.join(sorted(f.id for f in cluster))}".encode()
                ).hexdigest()

                alerts.append(HazardAlert(
                    id=alert_id,
                    level=HazardLevel.EXTREME,
                    title=f"Fire Cluster — {len(cluster)} Active Fires",
                    description=(
                        f"{len(cluster)} active fires detected within {max_dist:.1f}km. "
                        f"Potential fire front forming. "
                        f"Center: ({center_lat:.3f}, {center_lng:.3f})"
                    ),
                    location=Location(lat=center_lat, lng=center_lng),
                    radius_km=max_dist + 5,
                    contributing_events=[f.id for f in cluster],
                    recommended_action=(
                        "URGENT: Multiple fire front detected. "
                        "Coordinate multi-agency response. "
                        "Evaluate evacuation of nearby communities. "
                        "Request aerial firefighting support."
                    ),
                    expires_at=datetime.utcnow() + timedelta(hours=4),
                ))
        return alerts

    def _rule_emergency_concentration(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: Many emergencies in a small area = systemic issue."""
        alerts = []

        emergencies = [e for e in events if e.type == EventType.EMERGENCY]

        if len(emergencies) < 5:
            return alerts

        # Grid-based clustering (simple approach)
        grid: Dict[str, List[GeoEvent]] = {}
        cell_size = 0.1  # ~11km grid cells

        for em in emergencies:
            cell_key = f"{em.location.lat // cell_size}_{em.location.lng // cell_size}"
            grid.setdefault(cell_key, []).append(em)

        for cell_key, cell_events in grid.items():
            if len(cell_events) >= 5:
                center_lat = sum(e.location.lat for e in cell_events) / len(cell_events)
                center_lng = sum(e.location.lng for e in cell_events) / len(cell_events)

                alert_id = hashlib.md5(
                    f"emergency_cluster_{cell_key}".encode()
                ).hexdigest()

                alerts.append(HazardAlert(
                    id=alert_id,
                    level=HazardLevel.DANGER,
                    title=f"Emergency Cluster — {len(cell_events)} Incidents",
                    description=(
                        f"{len(cell_events)} emergency incidents detected in concentrated area. "
                        f"Possible large-scale event or cascading emergencies."
                    ),
                    location=Location(lat=center_lat, lng=center_lng),
                    radius_km=15.0,
                    contributing_events=[e.id for e in cell_events],
                    recommended_action=(
                        "Investigate potential common cause. "
                        "Consider coordinated multi-agency response. "
                        "Escalate to district coordination center (CDOS)."
                    ),
                    expires_at=datetime.utcnow() + timedelta(hours=3),
                ))
        return alerts

    def _rule_extreme_heat_fire(self, events: List[GeoEvent]) -> List[HazardAlert]:
        """RULE: Extreme heat warning + any fire = critical compound hazard."""
        alerts = []

        heat_events = [
            e for e in events
            if e.type == EventType.WEATHER and e.category == "extreme_heat"
            and severity_at_least(e.severity, Severity.HIGH)
        ]
        fires = [e for e in events if e.type == EventType.EMERGENCY
                 and "fire" in e.category.lower()]

        for heat in heat_events:
            for fire in fires:
                dist = haversine_km(heat.location, fire.location)
                if dist <= 50:  # Within 50km
                    alert_id = hashlib.md5(
                        f"heat_fire_{heat.id}_{fire.id}".encode()
                    ).hexdigest()

                    alerts.append(HazardAlert(
                        id=alert_id,
                        level=HazardLevel.EXTREME,
                        title="Extreme Heat + Active Fire",
                        description=(
                            f"Active fire during extreme heat conditions. "
                            f"Temperature exceeds safe thresholds. "
                            f"Risk to firefighter safety and civilian evacuation."
                        ),
                        location=fire.location,
                        radius_km=dist + 10,
                        contributing_events=[heat.id, fire.id],
                        recommended_action=(
                            "CRITICAL: Compound heat-fire hazard. "
                            "Ensure firefighter hydration and rotation protocols. "
                            "Identify vulnerable populations (elderly, sick) in area. "
                            "Pre-alert hospitals for heat-related emergencies."
                        ),
                        expires_at=datetime.utcnow() + timedelta(hours=6),
                    ))
        return alerts

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _deduplicate(self, alerts: List[HazardAlert]) -> List[HazardAlert]:
        """Remove duplicate alerts based on contributing events overlap."""
        seen: Dict[str, HazardAlert] = {}
        for alert in alerts:
            key = "_".join(sorted(alert.contributing_events))
            if key not in seen or HAZARD_LEVEL_RANK.get(alert.level, 0) > HAZARD_LEVEL_RANK.get(seen[key].level, 0):
                seen[key] = alert
        return list(seen.values())
