"""API Routes — REST endpoints for the SOS Services backend."""

from typing import List, Optional
from fastapi import APIRouter, Query

from app.models import GeoEvent, HazardAlert, MapLayer, EventType, SystemStatus
from app.ingestion.scheduler import data_store, scheduler

router = APIRouter()


@router.get("/events", response_model=List[GeoEvent])
async def get_events(
    type: Optional[str] = Query(None, description="Filter by event type"),
    severity: Optional[str] = Query(None, description="Minimum severity"),
    lat: Optional[float] = Query(None, description="Center latitude for radius search"),
    lng: Optional[float] = Query(None, description="Center longitude for radius search"),
    radius_km: Optional[float] = Query(None, description="Radius in km"),
):
    """Get all active events, optionally filtered."""
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

    return events


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


@router.get("/layers", response_model=List[MapLayer])
async def get_layers():
    """Get available map layers with event counts."""
    events = await data_store.get_all_events()

    layer_config = [
        {"id": "weather", "name": "Weather", "type": EventType.WEATHER, "color": "#3498db", "icon": "cloud"},
        {"id": "fire", "name": "Fires", "type": EventType.FIRE, "color": "#e74c3c", "icon": "fire"},
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
