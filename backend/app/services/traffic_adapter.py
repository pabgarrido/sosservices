"""Traffic Adapter — Real Portuguese road traffic data only.

Sources:
  1. TomTom Traffic Flow API (real-time speed/congestion on key roads)
  2. TomTom Traffic Incidents API (accidents, closures, etc.)
  3. Overpass API (OpenStreetMap) — road construction zones
  
All sources require real data. TomTom needs a free API key from developer.tomtom.com.
"""

from typing import List
from datetime import datetime
import asyncio
import hashlib

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


# Key monitoring points on major Portuguese roads.
# TomTom Flow API returns real-time speed data for the road segment
# nearest to each point.
FLOW_MONITOR_POINTS = [
    # Lisbon metro
    {"name": "Ponte 25 de Abril", "lat": 38.6913, "lng": -9.1775, "road": "A2/IC17"},
    {"name": "Ponte Vasco da Gama", "lat": 38.7628, "lng": -9.0318, "road": "A12"},
    {"name": "CRIL Amadora", "lat": 38.7560, "lng": -9.2310, "road": "IC17"},
    {"name": "A1 Vila Franca de Xira", "lat": 38.9550, "lng": -8.9930, "road": "A1"},
    {"name": "A5 Carcavelos", "lat": 38.6850, "lng": -9.3350, "road": "A5"},
    {"name": "IC19 Queluz", "lat": 38.7560, "lng": -9.2620, "road": "IC19"},
    {"name": "Segunda Circular", "lat": 38.7640, "lng": -9.1620, "road": "IC17"},
    {"name": "Eixo Norte-Sul", "lat": 38.7350, "lng": -9.1600, "road": "IC1"},
    # Porto metro
    {"name": "Ponte do Freixo", "lat": 41.1440, "lng": -8.5880, "road": "A20"},
    {"name": "Ponte da Arrábida", "lat": 41.1480, "lng": -8.6380, "road": "A1"},
    {"name": "VCI Porto", "lat": 41.1630, "lng": -8.6100, "road": "VCI"},
    {"name": "A3 Maia", "lat": 41.2350, "lng": -8.6200, "road": "A3"},
    {"name": "A1 Gaia", "lat": 41.0900, "lng": -8.5800, "road": "A1"},
    # Intercity corridors
    {"name": "A1 Santarém", "lat": 39.2369, "lng": -8.6850, "road": "A1"},
    {"name": "A1 Coimbra", "lat": 40.1800, "lng": -8.4500, "road": "A1"},
    {"name": "A1 Leiria", "lat": 39.7200, "lng": -8.7800, "road": "A1"},
    {"name": "A2 Setúbal", "lat": 38.5254, "lng": -8.8882, "road": "A2"},
    {"name": "A2 Albufeira", "lat": 37.0900, "lng": -8.2500, "road": "A2"},
    {"name": "A22 Via do Infante", "lat": 37.1100, "lng": -7.9300, "road": "A22"},
    {"name": "A23 Castelo Branco", "lat": 39.8222, "lng": -7.4914, "road": "A23"},
    {"name": "A25 Viseu", "lat": 40.6610, "lng": -7.9097, "road": "A25"},
    {"name": "A6 Évora", "lat": 38.5700, "lng": -7.9100, "road": "A6"},
    {"name": "A4 Vila Real", "lat": 41.2960, "lng": -7.7469, "road": "A4"},
    {"name": "EN125 Faro", "lat": 37.0194, "lng": -7.9322, "road": "EN125"},
]


class TrafficAdapter(BaseAdapter):
    """Fetches real traffic incidents and road conditions for Portugal."""

    def __init__(self):
        super().__init__("traffic")
        self.tomtom_api_key = getattr(settings, "tomtom_api_key", None)

    async def fetch(self) -> List[GeoEvent]:
        events: List[GeoEvent] = []

        if self.tomtom_api_key:
            # 1. TomTom real-time traffic flow (speed/congestion)
            flow = await self._fetch_tomtom_flow()
            events.extend(flow)

            # 2. TomTom real-time incidents (accidents, closures)
            incidents = await self._fetch_tomtom_incidents()
            events.extend(incidents)

        # 3. Overpass API — road construction zones (always available)
        osm = await self._fetch_osm_construction()
        events.extend(osm)

        if not self.tomtom_api_key:
            self.logger.warning(
                "No TOMTOM_API_KEY configured — traffic intensity data unavailable. "
                "Get a free key at https://developer.tomtom.com"
            )

        self.logger.info(f"Traffic adapter total: {len(events)} real events")
        return events

    # ------------------------------------------------------------------
    # TomTom Traffic Flow API — real-time speed & congestion
    # ------------------------------------------------------------------

    async def _fetch_tomtom_flow(self) -> List[GeoEvent]:
        """Query TomTom Flow Segment Data for key Portuguese road segments.

        Returns events only for segments with notable congestion
        (current speed significantly below free-flow speed).
        """
        events: List[GeoEvent] = []

        async def _query_point(point: dict) -> GeoEvent | None:
            """Query a single monitoring point."""
            try:
                url = (
                    f"https://api.tomtom.com/traffic/services/4"
                    f"/flowSegmentData/absolute/10/json"
                    f"?key={self.tomtom_api_key}"
                    f"&point={point['lat']},{point['lng']}"
                    f"&unit=KMPH"
                    f"&openLr=false"
                )
                resp = await self._client.get(url, timeout=10.0)
                if resp.status_code != 200:
                    return None

                data = resp.json()
                flow = data.get("flowSegmentData", {})

                current_speed = flow.get("currentSpeed", 0)
                free_flow = flow.get("freeFlowSpeed", 0)
                current_tt = flow.get("currentTravelTime", 0)
                free_flow_tt = flow.get("freeFlowTravelTime", 0)
                confidence = flow.get("confidence", 0)
                road_closure = flow.get("roadClosure", False)

                if free_flow == 0:
                    return None

                # Calculate congestion ratio
                speed_ratio = current_speed / free_flow if free_flow > 0 else 1.0

                # Determine severity based on speed ratio
                if road_closure:
                    severity = Severity.CRITICAL
                    category = "road_closed"
                    title = f"Estrada encerrada: {point['road']} — {point['name']}"
                    description = f"Road closure on {point['road']} near {point['name']}"
                elif speed_ratio < 0.3:
                    severity = Severity.CRITICAL
                    category = "traffic_jam"
                    title = f"Congestionamento severo: {point['road']} — {point['name']}"
                    description = (
                        f"Heavy congestion on {point['road']} near {point['name']}. "
                        f"Speed: {current_speed:.0f} km/h (normal: {free_flow:.0f} km/h)"
                    )
                elif speed_ratio < 0.5:
                    severity = Severity.HIGH
                    category = "traffic_jam"
                    title = f"Congestionamento: {point['road']} — {point['name']}"
                    description = (
                        f"Congestion on {point['road']} near {point['name']}. "
                        f"Speed: {current_speed:.0f} km/h (normal: {free_flow:.0f} km/h)"
                    )
                elif speed_ratio < 0.7:
                    severity = Severity.MEDIUM
                    category = "traffic_slow"
                    title = f"Trânsito lento: {point['road']} — {point['name']}"
                    description = (
                        f"Slow traffic on {point['road']} near {point['name']}. "
                        f"Speed: {current_speed:.0f} km/h (normal: {free_flow:.0f} km/h)"
                    )
                elif speed_ratio < 0.85:
                    severity = Severity.LOW
                    category = "traffic_moderate"
                    title = f"Trânsito moderado: {point['road']} — {point['name']}"
                    description = (
                        f"Moderate traffic on {point['road']} near {point['name']}. "
                        f"Speed: {current_speed:.0f} km/h (normal: {free_flow:.0f} km/h)"
                    )
                else:
                    # Free-flowing — still report it so the map shows intensity
                    severity = Severity.LOW
                    category = "traffic_free"
                    title = f"Trânsito livre: {point['road']} — {point['name']}"
                    description = (
                        f"Free-flowing traffic on {point['road']} near {point['name']}. "
                        f"Speed: {current_speed:.0f} km/h"
                    )

                delay_sec = max(0, current_tt - free_flow_tt)
                event_id = hashlib.md5(
                    f"flow_{point['lat']}_{point['lng']}".encode()
                ).hexdigest()

                return GeoEvent(
                    id=event_id,
                    type=EventType.TRAFFIC,
                    category=category,
                    title=title,
                    description=description,
                    location=Location(lat=point["lat"], lng=point["lng"]),
                    radius_km=2.0,
                    severity=severity,
                    source="traffic_flow",
                    start_time=datetime.utcnow(),
                    metadata={
                        "current_speed_kmh": current_speed,
                        "free_flow_speed_kmh": free_flow,
                        "speed_ratio": round(speed_ratio, 2),
                        "current_travel_time_sec": current_tt,
                        "free_flow_travel_time_sec": free_flow_tt,
                        "delay_sec": delay_sec,
                        "confidence": confidence,
                        "road_closure": road_closure,
                        "road": point["road"],
                        "monitoring_point": point["name"],
                        "provider": "tomtom.com",
                    },
                )
            except Exception as e:
                self.logger.debug(f"Flow query failed for {point['name']}: {e}")
                return None

        # Query all monitoring points concurrently (bounded)
        sem = asyncio.Semaphore(5)  # max 5 concurrent requests

        async def _bounded(pt):
            async with sem:
                return await _query_point(pt)

        results = await asyncio.gather(
            *[_bounded(pt) for pt in FLOW_MONITOR_POINTS],
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, GeoEvent):
                events.append(r)

        self.logger.info(f"TomTom Flow: {len(events)} monitoring points reported")
        return events

    # ------------------------------------------------------------------
    # Overpass API  — real OSM data (construction zones & road works)
    # ------------------------------------------------------------------

    async def _fetch_osm_construction(self) -> List[GeoEvent]:
        """Query Overpass API for real road construction works in Portugal."""
        events: List[GeoEvent] = []
        try:
            bbox = f"{settings.pt_lat_min},{settings.pt_lon_min},{settings.pt_lat_max},{settings.pt_lon_max}"

            # Query only real construction / road works (no toll booths or
            # other static infrastructure that is not a traffic event)
            query = (
                f'[out:json][timeout:25];'
                f'('
                f'way["highway"="construction"]({bbox});'
                f'node["highway"="construction"]({bbox});'
                f');'
                f'out body center qt 500;'
            )

            resp = await self._client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=30.0,
            )

            if resp.status_code != 200:
                self.logger.warning(f"Overpass API returned {resp.status_code}")
                return []

            data = resp.json()
            elements = data.get("elements", [])
            self.logger.info(f"Overpass returned {len(elements)} construction elements")

            for el in elements:
                tags = el.get("tags", {})

                # Nodes have lat/lon directly, ways use center
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lng = el.get("lon") or el.get("center", {}).get("lon")

                if not lat or not lng:
                    continue

                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    continue

                el_type = el.get("type", "")
                el_id = el.get("id", "")
                highway = tags.get("highway", "")
                construction = tags.get("construction", "")
                name = tags.get("name", "")
                ref = tags.get("ref", "")
                note = tags.get("note", "")
                opening_date = tags.get("opening_date", "")

                # Build a descriptive label from available tags
                road_label = ref or name or ""
                construction_type = construction or "road"

                # Severity based on road class being constructed
                # Roadworks are informational, not dangerous — keep severity low
                if construction in ("motorway", "trunk", "motorway_link"):
                    severity = Severity.MEDIUM
                    category = "road_works_major"
                elif construction in ("primary", "secondary"):
                    severity = Severity.LOW
                    category = "road_works"
                else:
                    severity = Severity.LOW
                    category = "road_works"

                # Title
                if road_label:
                    title = f"Obras: {road_label} ({construction_type})"
                else:
                    title = f"Obras: {construction_type}"

                # Description
                description = f"Road construction — {construction_type}"
                if road_label:
                    description += f" on {road_label}"
                if note:
                    description += f". {note}"
                if opening_date:
                    description += f". Expected completion: {opening_date}"

                event_id = hashlib.md5(
                    f"osm_{el_type}_{el_id}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.TRAFFIC,
                    category=category,
                    title=title,
                    description=description,
                    location=Location(lat=lat, lng=lng),
                    radius_km=1.0,
                    severity=severity,
                    source="traffic_osm",
                    start_time=datetime.utcnow(),
                    metadata={
                        "osm_type": el_type,
                        "osm_id": el_id,
                        "construction_type": construction,
                        "road_ref": ref,
                        "road_name": name,
                        "opening_date": opening_date,
                        "tags": {k: v for k, v in tags.items()
                                 if k in ("highway", "construction", "ref",
                                          "name", "note", "opening_date",
                                          "lanes", "maxspeed", "surface")},
                        "provider": "openstreetmap.org",
                    },
                ))

        except Exception as e:
            self.logger.error(f"Overpass fetch failed: {e}")

        # Deduplicate nearby construction events (within 0.5 km)
        # OSM often has multiple nodes/ways for the same construction zone
        if len(events) > 1:
            deduped: List[GeoEvent] = []
            for ev in events:
                is_dup = False
                for existing in deduped:
                    dlat = abs(ev.location.lat - existing.location.lat)
                    dlng = abs(ev.location.lng - existing.location.lng)
                    # ~0.005 deg ≈ 0.5 km
                    if dlat < 0.005 and dlng < 0.005:
                        is_dup = True
                        break
                if not is_dup:
                    deduped.append(ev)
            self.logger.info(
                f"Roadworks dedup: {len(events)} → {len(deduped)} "
                f"(removed {len(events) - len(deduped)} nearby duplicates)"
            )
            events = deduped

        return events

    # ------------------------------------------------------------------
    # TomTom Traffic Incidents API  (free tier — needs API key)
    # ------------------------------------------------------------------

    async def _fetch_tomtom_incidents(self) -> List[GeoEvent]:
        """Fetch from TomTom Traffic Incidents API (free tier: 2500 req/day)."""
        events: List[GeoEvent] = []
        try:
            url = (
                f"https://api.tomtom.com/traffic/services/5/incidentDetails"
                f"?key={self.tomtom_api_key}"
                f"&bbox={settings.pt_lon_min},{settings.pt_lat_min},"
                f"{settings.pt_lon_max},{settings.pt_lat_max}"
                f"&fields={{incidents{{type,geometry{{type,coordinates}},"
                f"properties{{iconCategory,magnitudeOfDelay,"
                f"events{{description,code}},startTime,endTime,from,to}}}}}}"
                f"&language=pt-PT"
                f"&timeValidityFilter=present"
            )

            resp = await self._client.get(url, timeout=15.0)
            if resp.status_code != 200:
                self.logger.warning(f"TomTom returned {resp.status_code}")
                return []

            data = resp.json()
            incidents = data.get("incidents", [])

            for inc in incidents:
                props = inc.get("properties", {})
                geom = inc.get("geometry", {})
                coords = geom.get("coordinates", [])

                if not coords:
                    continue

                if geom.get("type") == "Point":
                    lng, lat = coords[0], coords[1]
                elif isinstance(coords[0], list):
                    mid = coords[len(coords) // 2]
                    lng, lat = mid[0], mid[1]
                else:
                    lng, lat = coords[0], coords[1]

                icon_cat = props.get("iconCategory", 0)
                magnitude = props.get("magnitudeOfDelay", 0)
                from_road = props.get("from", "")
                to_road = props.get("to", "")
                tt_events_list = props.get("events", [])
                desc = (
                    tt_events_list[0].get("description", "")
                    if tt_events_list else ""
                )

                severity = Severity.LOW
                if magnitude >= 1:
                    severity = Severity.MEDIUM
                if magnitude >= 2:
                    severity = Severity.HIGH
                if magnitude >= 3:
                    severity = Severity.CRITICAL

                category = self._tomtom_category(icon_cat)

                event_id = hashlib.md5(
                    f"tt_{lat}_{lng}_{icon_cat}_{from_road}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.TRAFFIC,
                    category=category,
                    title=(
                        f"Traffic: {desc or category}"
                        + (f" ({from_road})" if from_road else "")
                    ),
                    description=(
                        f"{desc}. From: {from_road} To: {to_road}"
                        if from_road else desc
                    ),
                    location=Location(lat=lat, lng=lng),
                    radius_km=1.0,
                    severity=severity,
                    source="traffic_tomtom",
                    start_time=datetime.utcnow(),
                    metadata={
                        "icon_category": icon_cat,
                        "magnitude_of_delay": magnitude,
                        "from": from_road,
                        "to": to_road,
                        "description": desc,
                        "provider": "tomtom.com",
                    },
                ))

            self.logger.info(f"TomTom: {len(events)} incidents")

        except Exception as e:
            self.logger.error(f"TomTom fetch failed: {e}")

        return events

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tomtom_category(icon_cat: int) -> str:
        cats = {
            0: "traffic_incident", 1: "accident", 2: "road_hazard",
            3: "road_works", 4: "road_closed", 5: "traffic_jam",
            6: "lane_closed", 7: "road_works", 8: "traffic_incident",
            9: "accident", 10: "traffic_jam", 11: "road_hazard",
            14: "road_closed",
        }
        return cats.get(icon_cat, "traffic_incident")
