"""API Routes — REST endpoints for the SOS Services backend."""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Query

from app.models import GeoEvent, HazardAlert, MapLayer, EventType, SystemStatus
from app.ingestion.scheduler import data_store, scheduler
from app.analytics.hazard_scoring import HazardScoringEngine

router = APIRouter()

# Lightweight scoring engine for on-demand time-windowed queries
_windowed_scorer = HazardScoringEngine()


def _parse_time(val: Optional[str], default) -> datetime:
    """Parse ISO8601 string to datetime, returning default on failure."""
    if not val:
        return default
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return default


def _filter_events_by_time(events: List[GeoEvent], time_start: Optional[str], time_end: Optional[str]) -> List[GeoEvent]:
    """Filter events that overlap the [time_start, time_end] window."""
    if not time_start and not time_end:
        return events
    t_start = _parse_time(time_start, datetime.min)
    t_end = _parse_time(time_end, datetime.max)
    filtered = []
    for e in events:
        ev_start = e.start_time
        ev_end = e.end_time or e.start_time
        if ev_start <= t_end and ev_end >= t_start:
            filtered.append(e)
    return filtered


@router.get("/events", response_model=List[GeoEvent])
async def get_events(
    type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Minimum severity"),
    lat: Optional[float] = Query(None, description="Center latitude for radius search"),
    lng: Optional[float] = Query(None, description="Center longitude for radius search"),
    radius_km: Optional[float] = Query(None, description="Radius in km"),
    time_start: Optional[str] = Query(None, description="ISO8601 start of time window"),
    time_end: Optional[str] = Query(None, description="ISO8601 end of time window"),
):
    """Get all active events, optionally filtered by type, severity, location, or time window."""
    events = await data_store.get_all_events()

    if type:
        events = [e for e in events if e.type == type]

    if severity:
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_sev = severity_order.get(severity, 0)
        events = [e for e in events if severity_order.get(e.severity, 0) >= min_sev]

    if lat is not None and lng is not None and radius_km is not None:
        from app.analytics.correlation_engine import haversine_km
        from app.models import Location
        center = Location(lat=lat, lng=lng)
        events = [
            e for e in events
            if haversine_km(center, e.location) <= radius_km
        ]

    # Time window filtering
    if time_start or time_end:
        events = _filter_events_by_time(events, time_start, time_end)

    return events


@router.get("/time-range")
async def get_time_range():
    """Get the available time range across all events (min start_time, max end_time)."""
    events = await data_store.get_all_events()
    if not events:
        now = datetime.utcnow()
        return {
            "min_time": now.isoformat(),
            "max_time": now.isoformat(),
            "now": now.isoformat(),
            "total_events": 0,
            "forecast_events": 0,
            "current_events": 0,
        }

    now = datetime.utcnow()
    min_time = min(e.start_time for e in events)
    max_time = max(e.end_time or e.start_time for e in events)
    forecast_count = sum(1 for e in events if e.metadata.get("is_forecast", False))

    return {
        "min_time": min_time.isoformat(),
        "max_time": max_time.isoformat(),
        "now": now.isoformat(),
        "total_events": len(events),
        "forecast_events": forecast_count,
        "current_events": len(events) - forecast_count,
    }


@router.get("/alerts", response_model=List[HazardAlert])
async def get_alerts(
    level: Optional[str] = Query(None, description="Minimum hazard level"),
):
    """Get all active hazard alerts from the correlation engine."""
    alerts = await data_store.get_all_alerts()

    if level:
        level_order = {"none": 0, "watch": 1, "warning": 2, "danger": 3, "extreme": 4}
        min_level = level_order.get(level, 0)
        alerts = [a for a in alerts if level_order.get(a.level, 0) >= min_level]

    return alerts


@router.get("/hazard-scores")
async def get_hazard_scores(
    min_score: Optional[float] = Query(None, description="Minimum hazard score (0-100)"),
    type: Optional[str] = Query(None, description="Filter by event type"),
    level: Optional[str] = Query(None, description="Filter by hazard level"),
    limit: int = Query(200, description="Max results", ge=1, le=1000),
    time_start: Optional[str] = Query(None, description="ISO8601 start of time window"),
    time_end: Optional[str] = Query(None, description="ISO8601 end of time window"),
):
    """Get per-event hazard scores from the predictive analytics engine."""
    scored = await data_store.get_scored_events()

    if min_score is not None:
        scored = [s for s in scored if s.score >= min_score]
    if type:
        scored = [s for s in scored if s.event_type == type]
    if level:
        scored = [s for s in scored if s.hazard_level == level]

    # Time window filtering — look up event start_time from data store
    if time_start or time_end:
        events = await data_store.get_all_events()
        time_filtered_ids = {e.id for e in _filter_events_by_time(events, time_start, time_end)}
        scored = [s for s in scored if s.event_id in time_filtered_ids]

    # Convert dataclass to dict for JSON serialization
    return [
        {
            "event_id": s.event_id,
            "event_type": s.event_type,
            "category": s.category,
            "title": s.title,
            "location": s.location,
            "severity": s.severity,
            "source": s.source,
            "score": s.score,
            "base_score": s.base_score,
            "amplification": s.amplification,
            "cluster_bonus": s.cluster_bonus,
            "temporal_factor": s.temporal_factor,
            "environmental_modifier": s.environmental_modifier,
            "contributing_factors": s.contributing_factors,
            "hazard_level": s.hazard_level,
        }
        for s in scored[:limit]
    ]


@router.get("/risk-zones")
async def get_risk_zones(
    min_score: Optional[float] = Query(None, description="Minimum zone score"),
    time_start: Optional[str] = Query(None, description="ISO8601 start of time window"),
    time_end: Optional[str] = Query(None, description="ISO8601 end of time window"),
):
    """Get geographic risk zones. When time params are given, re-computes
    zones from only the events in that time window so scores reflect actual
    risk at that moment."""
    if time_start or time_end:
        # Re-score only events in this time window
        all_events = await data_store.get_all_events()
        windowed = _filter_events_by_time(all_events, time_start, time_end)
        scored = _windowed_scorer.score_events(windowed)
        zones = _windowed_scorer.compute_risk_zones(windowed, scored)
    else:
        zones = await data_store.get_risk_zones()

    if min_score is not None:
        zones = [z for z in zones if z.score >= min_score]

    return [
        {
            "cell_id": z.cell_id,
            "lat": z.lat,
            "lng": z.lng,
            "score": z.score,
            "event_count": z.event_count,
            "dominant_type": z.dominant_type,
            "hazard_level": z.hazard_level,
            "top_factors": z.top_factors,
        }
        for z in zones
    ]


@router.get("/analytics/summary")
async def get_analytics_summary(
    time_start: Optional[str] = Query(None, description="ISO8601 start of time window"),
    time_end: Optional[str] = Query(None, description="ISO8601 end of time window"),
):
    """Get predictive analytics summary. When time params are given,
    re-scores only events in that window for an accurate snapshot."""
    if time_start or time_end:
        all_events = await data_store.get_all_events()
        windowed = _filter_events_by_time(all_events, time_start, time_end)
        scored = _windowed_scorer.score_events(windowed)
        return _windowed_scorer.get_summary(scored)
    return await data_store.get_analytics_summary()


@router.get("/layers", response_model=List[MapLayer])
async def get_layers():
    """Get available map layers with event counts."""
    events = await data_store.get_all_events()

    layer_config = [
        {"id": "weather", "name": "Weather", "type": EventType.WEATHER, "color": "#3498db", "icon": "cloud"},
        {"id": "emergency", "name": "Emergencies", "type": EventType.EMERGENCY, "color": "#e67e22", "icon": "warning"},
        {"id": "traffic", "name": "Traffic", "type": EventType.TRAFFIC, "color": "#9b59b6", "icon": "car"},
        {"id": "event", "name": "Events", "type": EventType.EVENT, "color": "#2ecc71", "icon": "calendar"},
    ]

    layers = []
    for lc in layer_config:
        count = len([e for e in events if e.type == lc["type"]])
        layers.append(MapLayer(
            id=lc["id"],
            name=lc["name"],
            type=lc["type"],
            color=lc["color"],
            icon=lc["icon"],
            event_count=count,
        ))
    return layers


@router.get("/status", response_model=List[SystemStatus])
async def get_status():
    """Get health status of all data adapters."""
    return scheduler.get_status()


@router.post("/refresh")
async def force_refresh():
    """Force an immediate refresh of all data sources."""
    await scheduler._fetch_all()
    return {"message": "Data refresh triggered", "event_count": len(await data_store.get_all_events())}
