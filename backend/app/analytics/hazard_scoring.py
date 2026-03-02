"""
Predictive Hazard Scoring Engine — Real-time risk quantification.

Assigns a hazard score (0–100) to every GeoEvent based on:
  1. Base severity weight
  2. Cross-domain amplification (weather×fire, events×traffic, etc.)
  3. Spatial clustering (nearby events compound risk)
  4. Temporal decay (recent events score higher)
  5. Environmental modifiers (wind, humidity, temperature)

Also produces location-based Risk Zones by aggregating nearby event scores
onto a grid covering Portugal.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from app.models import (
    EventType,
    GeoEvent,
    HazardLevel,
    Location,
    Severity,
)

logger = logging.getLogger("analytics.hazard_scoring")

# ── Weight tables ──────────────────────────────────────────────────

SEVERITY_BASE_SCORE: Dict[Severity, float] = {
    Severity.LOW: 10,
    Severity.MEDIUM: 30,
    Severity.HIGH: 60,
    Severity.CRITICAL: 85,
}

TYPE_BASE_MODIFIER: Dict[EventType, float] = {
    EventType.WEATHER: 1.0,
    EventType.EMERGENCY: 1.2,
    EventType.TRAFFIC: 0.6,
    EventType.EVENT: 0.3,
}

# Cross-domain amplification matrix.
# Key = (influencer_type, affected_type) → multiplier added to affected event.
# Note: fires are now under EMERGENCY with fire-related categories.
CROSS_DOMAIN_AMPLIFICATION: Dict[Tuple[EventType, EventType], float] = {
    # Weather amplifies emergency risk (includes fires)
    (EventType.WEATHER, EventType.EMERGENCY): 0.30,
    # Weather amplifies traffic risk (rain/fog → accidents)
    (EventType.WEATHER, EventType.TRAFFIC): 0.20,
    # Large events amplify traffic congestion risk
    (EventType.EVENT, EventType.TRAFFIC): 0.15,
    # Emergency near events = crowd safety issue
    (EventType.EMERGENCY, EventType.EVENT): 0.30,
    # Traffic jams near emergencies slow response
    (EventType.TRAFFIC, EventType.EMERGENCY): 0.20,
}

# Category-specific danger weights for fire-weather correlation
FIRE_WEATHER_CATEGORIES = {
    "wildfire", "wildfire_detection", "fire", "forest_fire",
}
ADVERSE_WEATHER_CATEGORIES = {
    "extreme_heat", "high_wind", "thunderstorm", "drought",
    "heat_wave", "red_extreme_uv", "extreme_weather",
}
RAIN_CATEGORIES = {
    "heavy_rain", "precipitation", "flood_warning", "rain_warning",
}

# Categories that are informational / low-danger — apply dampening factor
ROADWORK_CATEGORIES = {
    "road_works", "road_works_major",
}
ROADWORK_DAMPENING = 0.45  # Roadworks score at 45% of normal

# Public holidays are informational, not hazards — heavy dampening
HOLIDAY_CATEGORIES = {
    "public_event", "public_holiday",
}
HOLIDAY_DAMPENING = 0.30  # Holidays score at 30% of normal

# Proximity thresholds (km) for cross-domain correlation
PROXIMITY_THRESHOLD_KM = 25.0
CLUSTER_RADIUS_KM = 15.0

# Temporal decay half-life in hours
DECAY_HALF_LIFE_HOURS = 6.0

# Portugal grid for risk zones
PT_LAT_MIN, PT_LAT_MAX = 36.96, 42.15
PT_LON_MIN, PT_LON_MAX = -9.50, -6.19
GRID_CELL_DEG = 0.25  # ~25 km cells


# ── Data classes ───────────────────────────────────────────────────

@dataclass
class ScoredEvent:
    """An event with its computed hazard score and breakdown."""
    event_id: str
    event_type: str
    category: str
    title: str
    location: Dict  # {lat, lng}
    severity: str
    source: str
    score: float  # 0-100
    base_score: float
    amplification: float
    cluster_bonus: float
    temporal_factor: float
    environmental_modifier: float
    contributing_factors: List[str] = field(default_factory=list)
    hazard_level: str = "none"


@dataclass
class RiskZone:
    """Aggregated risk for a geographic grid cell."""
    cell_id: str
    lat: float
    lng: float
    score: float  # 0-100
    event_count: int
    dominant_type: str
    hazard_level: str
    top_factors: List[str] = field(default_factory=list)


# ── Helper functions ───────────────────────────────────────────────

def haversine_km(loc1: Location, loc2: Location) -> float:
    """Distance in km between two locations."""
    R = 6371.0
    lat1, lon1 = math.radians(loc1.lat), math.radians(loc1.lng)
    lat2, lon2 = math.radians(loc2.lat), math.radians(loc2.lng)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _temporal_decay(event: GeoEvent, now: datetime) -> float:
    """Decay factor (0–1) based on how recent the event is.
    Future events (forecasts) get no decay — their discount is handled separately."""
    if event.start_time > now:
        return 1.0  # No decay for future/forecast events
    age_hours = max(0, (now - event.start_time).total_seconds() / 3600)
    return math.exp(-0.693 * age_hours / DECAY_HALF_LIFE_HOURS)  # ln(2)=0.693


def _env_modifier(event: GeoEvent) -> Tuple[float, List[str]]:
    """
    Environmental modifier (0–0.3 bonus) based on metadata.
    Returns (modifier_value, list_of_factor_descriptions).
    """
    meta = event.metadata or {}
    modifier = 0.0
    factors: List[str] = []

    # Wind speed
    wind = meta.get("wind_speed") or meta.get("wind_kmh") or 0
    if isinstance(wind, (int, float)) and wind > 30:
        modifier += 0.15
        factors.append(f"High wind {wind:.0f} km/h")
    elif isinstance(wind, (int, float)) and wind > 15:
        modifier += 0.05
        factors.append(f"Moderate wind {wind:.0f} km/h")

    # Temperature
    temp = meta.get("temperature") or meta.get("temp_c") or meta.get("tMax")
    if isinstance(temp, (int, float)) and temp > 40:
        modifier += 0.15
        factors.append(f"Extreme heat {temp:.0f}°C")
    elif isinstance(temp, (int, float)) and temp > 35:
        modifier += 0.08
        factors.append(f"High temperature {temp:.0f}°C")

    # Low humidity (fire danger)
    humidity = meta.get("humidity") or meta.get("humidity_pct")
    if isinstance(humidity, (int, float)) and humidity < 20:
        modifier += 0.12
        factors.append(f"Very low humidity {humidity:.0f}%")
    elif isinstance(humidity, (int, float)) and humidity < 30:
        modifier += 0.05
        factors.append(f"Low humidity {humidity:.0f}%")

    # Precipitation probability (flood risk)
    precip = meta.get("precip_prob") or meta.get("precipitation_probability")
    if isinstance(precip, (int, float)) and precip > 80:
        modifier += 0.10
        factors.append(f"Heavy rain probability {precip:.0f}%")

    # Traffic congestion ratio
    ratio = meta.get("freeFlow_ratio")
    if isinstance(ratio, (int, float)) and ratio < 0.3:
        modifier += 0.10
        factors.append(f"Severe congestion (ratio {ratio:.2f})")
    elif isinstance(ratio, (int, float)) and ratio < 0.5:
        modifier += 0.05
        factors.append(f"Congestion (ratio {ratio:.2f})")

    return min(modifier, 0.30), factors


def _score_to_level(score: float) -> str:
    """Convert numeric score to hazard level string."""
    if score >= 80:
        return "extreme"
    elif score >= 60:
        return "danger"
    elif score >= 40:
        return "warning"
    elif score >= 20:
        return "watch"
    return "none"


# ── Main scoring engine ───────────────────────────────────────────

class HazardScoringEngine:
    """
    Computes per-event hazard scores and per-location risk zones
    using cross-domain correlation, spatial clustering, temporal
    decay, and environmental modifiers.
    """

    def __init__(self):
        self._last_scored: List[ScoredEvent] = []
        self._last_zones: List[RiskZone] = []

    def score_events(self, events: List[GeoEvent]) -> List[ScoredEvent]:
        """
        Main entry: score every event and return sorted list.

        Algorithm per event:
          1. base = SEVERITY_BASE_SCORE × TYPE_BASE_MODIFIER
          2. amplification = sum of cross-domain multipliers from nearby events
          3. cluster_bonus = bonus for spatially-clustered same-type events
          4. temporal = decay factor (recent events count more)
          5. environmental = metadata-based modifier
          6. final = clamp(base × (1 + amplification + cluster + env) × temporal, 0, 100)
        """
        if not events:
            self._last_scored = []
            return []

        now = datetime.utcnow()

        # Pre-index events by type for efficient cross-domain lookup
        by_type: Dict[EventType, List[GeoEvent]] = defaultdict(list)
        for ev in events:
            by_type[ev.type].append(ev)

        scored: List[ScoredEvent] = []

        for ev in events:
            factors: List[str] = []

            # 1. Base score
            base = SEVERITY_BASE_SCORE.get(ev.severity, 10)
            type_mod = TYPE_BASE_MODIFIER.get(ev.type, 1.0)
            base_score = base * type_mod
            factors.append(f"Base: {ev.severity.value} severity × {ev.type.value} type")

            # 2. Cross-domain amplification
            amplification = 0.0
            for other_type, other_events in by_type.items():
                if other_type == ev.type:
                    continue
                amp_key = (other_type, ev.type)
                amp_factor = CROSS_DOMAIN_AMPLIFICATION.get(amp_key)
                if amp_factor is None:
                    continue

                # Check if any event of other_type is within proximity
                nearby_count = 0
                for other_ev in other_events:
                    dist = haversine_km(ev.location, other_ev.location)
                    if dist <= PROXIMITY_THRESHOLD_KM:
                        nearby_count += 1

                if nearby_count > 0:
                    # Amplification grows sub-linearly with count
                    effective_amp = amp_factor * min(math.log2(nearby_count + 1), 3.0)
                    amplification += effective_amp
                    factors.append(
                        f"+{effective_amp:.0%} from {nearby_count} nearby "
                        f"{other_type.value} event(s)"
                    )

            # Special bonus: fire-category emergencies near adverse weather
            if ev.type == EventType.EMERGENCY and ev.category in FIRE_WEATHER_CATEGORIES:
                for w in by_type.get(EventType.WEATHER, []):
                    if w.category in ADVERSE_WEATHER_CATEGORIES:
                        if haversine_km(ev.location, w.location) <= 50:
                            amplification += 0.25
                            factors.append(
                                "+25% fire-weather compound risk"
                            )
                            break

            amplification = min(amplification, 1.0)  # cap at +100%

            # 3. Spatial cluster bonus (same-type events nearby)
            cluster_bonus = 0.0
            same_type = by_type.get(ev.type, [])
            neighbors = sum(
                1 for other in same_type
                if other.id != ev.id
                and haversine_km(ev.location, other.location) <= CLUSTER_RADIUS_KM
            )
            if neighbors >= 5:
                cluster_bonus = 0.30
                factors.append(f"+30% cluster: {neighbors} same-type events within {CLUSTER_RADIUS_KM}km")
            elif neighbors >= 3:
                cluster_bonus = 0.20
                factors.append(f"+20% cluster: {neighbors} same-type events within {CLUSTER_RADIUS_KM}km")
            elif neighbors >= 1:
                cluster_bonus = 0.10
                factors.append(f"+10% cluster: {neighbors} same-type events within {CLUSTER_RADIUS_KM}km")

            # 4. Temporal decay
            temporal = _temporal_decay(ev, now)

            # 4b. Forecast confidence discount — future events scored lower
            forecast_discount = 1.0
            if ev.metadata.get("is_forecast", False):
                forecast_hours = ev.metadata.get("forecast_hours", 0)
                if not forecast_hours:
                    forecast_hours = max(0, (ev.start_time - now).total_seconds() / 3600)
                # Discount increases with how far in the future
                forecast_discount = max(0.4, 1.0 - forecast_hours * 0.012)
                factors.append(f"Forecast -{(1-forecast_discount)*100:.0f}% confidence")

            # 5. Environmental modifier
            env_mod, env_factors = _env_modifier(ev)
            factors.extend(env_factors)

            # 6. Final score
            raw = base_score * (1 + amplification + cluster_bonus + env_mod) * temporal * forecast_discount

            # 6b. Roadwork dampening — construction zones are informational,
            # not emergency-level hazards
            if ev.category in ROADWORK_CATEGORIES:
                raw *= ROADWORK_DAMPENING
                factors.append(f"Roadwork dampening ×{ROADWORK_DAMPENING}")

            # 6c. Holiday dampening — public holidays are informational
            if ev.category in HOLIDAY_CATEGORIES:
                raw *= HOLIDAY_DAMPENING
                factors.append(f"Holiday dampening ×{HOLIDAY_DAMPENING}")

            final_score = round(min(max(raw, 0), 100), 1)
            level = _score_to_level(final_score)

            scored.append(ScoredEvent(
                event_id=ev.id,
                event_type=ev.type.value,
                category=ev.category,
                title=ev.title,
                location={"lat": ev.location.lat, "lng": ev.location.lng},
                severity=ev.severity.value,
                source=ev.source,
                score=final_score,
                base_score=round(base_score, 1),
                amplification=round(amplification, 3),
                cluster_bonus=round(cluster_bonus, 3),
                temporal_factor=round(temporal, 3),
                environmental_modifier=round(env_mod, 3),
                contributing_factors=factors,
                hazard_level=level,
            ))

        # Sort by score descending
        scored.sort(key=lambda s: s.score, reverse=True)
        self._last_scored = scored
        logger.info(
            f"Scored {len(scored)} events | "
            f"top={scored[0].score if scored else 0} "
            f"({scored[0].hazard_level if scored else 'n/a'})"
        )
        return scored

    def compute_risk_zones(
        self,
        events: List[GeoEvent],
        scored: Optional[List[ScoredEvent]] = None,
    ) -> List[RiskZone]:
        """
        Build a grid of risk zones across Portugal.
        Each cell aggregates the hazard scores of nearby events.
        Only cells with at least one event are returned.
        """
        if scored is None:
            scored = self._last_scored

        # Build quick lookup: event_id → score
        score_map: Dict[str, float] = {s.event_id: s.score for s in scored}

        # Build grid
        zones: Dict[str, dict] = {}

        for ev in events:
            # Determine which cell this event falls into
            if not (PT_LAT_MIN <= ev.location.lat <= PT_LAT_MAX
                    and PT_LON_MIN <= ev.location.lng <= PT_LON_MAX):
                continue

            cell_lat = int((ev.location.lat - PT_LAT_MIN) / GRID_CELL_DEG)
            cell_lng = int((ev.location.lng - PT_LON_MIN) / GRID_CELL_DEG)
            cell_id = f"{cell_lat}_{cell_lng}"

            if cell_id not in zones:
                center_lat = PT_LAT_MIN + (cell_lat + 0.5) * GRID_CELL_DEG
                center_lng = PT_LON_MIN + (cell_lng + 0.5) * GRID_CELL_DEG
                zones[cell_id] = {
                    "cell_id": cell_id,
                    "lat": round(center_lat, 4),
                    "lng": round(center_lng, 4),
                    "scores": [],
                    "types": defaultdict(int),
                    "type_scores": defaultdict(float),  # score-weighted by type
                    "factors": [],
                }

            ev_score = score_map.get(ev.id, 0)
            zones[cell_id]["scores"].append(ev_score)
            zones[cell_id]["types"][ev.type.value] += 1
            zones[cell_id]["type_scores"][ev.type.value] += ev_score

        # Compute aggregate score per zone
        result: List[RiskZone] = []
        for z in zones.values():
            if not z["scores"]:
                continue

            # Aggregate: max score + sqrt-sum bonus for multiple events
            max_score = max(z["scores"])
            count = len(z["scores"])
            # Sub-linear aggregation: each extra event adds diminishing bonus
            aggregate = max_score + 5 * math.sqrt(max(count - 1, 0))
            aggregate = min(aggregate, 100)

            # Dominant type by total score contribution, not raw count
            dominant = max(z["type_scores"], key=z["type_scores"].get)

            result.append(RiskZone(
                cell_id=z["cell_id"],
                lat=z["lat"],
                lng=z["lng"],
                score=round(aggregate, 1),
                event_count=count,
                dominant_type=dominant,
                hazard_level=_score_to_level(aggregate),
                top_factors=[
                    f"{ct} {tp} (score {z['type_scores'].get(tp, 0):.0f})"
                    for tp, ct in sorted(
                        z["types"].items(),
                        key=lambda x: -z["type_scores"].get(x[0], 0)
                    )
                ],
            ))

        result.sort(key=lambda r: r.score, reverse=True)
        self._last_zones = result
        logger.info(
            f"Computed {len(result)} risk zones | "
            f"top={result[0].score if result else 0}"
        )
        return result

    def get_summary(self, scored: List[ScoredEvent]) -> Dict:
        """Produce an analytics summary for the frontend dashboard."""
        if not scored:
            return {
                "total_events": 0,
                "overall_risk": "none",
                "overall_score": 0,
                "by_level": {},
                "by_type": {},
                "top_hazards": [],
                "cross_domain_alerts": [],
            }

        # Count by level
        by_level: Dict[str, int] = defaultdict(int)
        for s in scored:
            by_level[s.hazard_level] += 1

        # Count by type
        by_type: Dict[str, dict] = {}
        type_scores: Dict[str, List[float]] = defaultdict(list)
        for s in scored:
            type_scores[s.event_type].append(s.score)
        for tp, scores in type_scores.items():
            by_type[tp] = {
                "count": len(scores),
                "avg_score": round(sum(scores) / len(scores), 1),
                "max_score": round(max(scores), 1),
            }

        # Overall score = weighted average of top 10 events
        top_n = scored[:10]
        overall = sum(s.score for s in top_n) / len(top_n) if top_n else 0

        # Cross-domain alerts: events with amplification > 0
        cross_domain = [
            {
                "event_id": s.event_id,
                "title": s.title,
                "score": s.score,
                "amplification": s.amplification,
                "factors": [f for f in s.contributing_factors if "nearby" in f.lower()],
            }
            for s in scored
            if s.amplification > 0
        ][:15]  # top 15

        return {
            "total_events": len(scored),
            "overall_risk": _score_to_level(overall),
            "overall_score": round(overall, 1),
            "by_level": dict(by_level),
            "by_type": by_type,
            "top_hazards": [
                {
                    "event_id": s.event_id,
                    "title": s.title,
                    "score": s.score,
                    "level": s.hazard_level,
                    "type": s.event_type,
                    "category": s.category,
                    "source": s.source,
                    "location": s.location,
                    "severity": s.severity,
                    "factors": s.contributing_factors[:4],
                }
                for s in scored[:15]
            ],
            "cross_domain_alerts": [
                {
                    **cd,
                    "location": cd_scored.location if cd_scored else None,
                    "category": cd_scored.category if cd_scored else None,
                    "type": cd_scored.event_type if cd_scored else None,
                }
                for cd in cross_domain
                for cd_scored in [next((s for s in scored if s.event_id == cd["event_id"]), None)]
            ],
        }
