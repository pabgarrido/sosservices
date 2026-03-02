"""Proteção Civil Adapter — Portuguese Civil Protection occurrences."""

from typing import List
from datetime import datetime
import hashlib

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


# ProCiv occurrence nature to severity mapping
NATURE_SEVERITY = {
    "Incêndio Florestal": Severity.HIGH,
    "Incêndio Urbano": Severity.HIGH,
    "Incêndio Rural": Severity.HIGH,
    "Incêndios Rurais": Severity.HIGH,
    "Inundação": Severity.HIGH,
    "Inundações": Severity.HIGH,
    "Acidente Rodoviário": Severity.MEDIUM,
    "Acidente Ferroviário": Severity.HIGH,
    "Queda de Árvore": Severity.LOW,
    "Queda de Árvores": Severity.LOW,
    "Deslizamento": Severity.HIGH,
    "Deslizamentos": Severity.HIGH,
    "Busca e Salvamento": Severity.HIGH,
    "Assistência Técnica": Severity.LOW,
    "Pré-Hospitalar": Severity.MEDIUM,
    "Incêndio em Equipamento": Severity.MEDIUM,
    "Incêndio em Detritos": Severity.LOW,
}

# Nature to event type mapping — fires merged under emergencies
NATURE_TYPE = {
    "Incêndio Florestal": EventType.EMERGENCY,
    "Incêndio Rural": EventType.EMERGENCY,
    "Incêndios Rurais": EventType.EMERGENCY,
    "Incêndio Urbano": EventType.EMERGENCY,
    "Incêndio em Equipamento": EventType.EMERGENCY,
    "Incêndio em Detritos": EventType.EMERGENCY,
}


class ProCivAdapter(BaseAdapter):
    """Fetches active occurrences from Proteção Civil via multiple sources."""

    def __init__(self):
        super().__init__("prociv")

    async def fetch(self) -> List[GeoEvent]:
        events = []

        # Try multiple sources in order of reliability
        # 1. fogos.pt API — community-run, aggregates ICNF/ProCiv data
        fogos_events = await self._fetch_fogos_pt()
        if fogos_events:
            events.extend(fogos_events)
            return events

        # 2. ICNF direct API fallback
        icnf_events = await self._fetch_icnf()
        if icnf_events:
            events.extend(icnf_events)
            return events

        # 3. ProCiv / ANEPC occurrences
        prociv_events = await self._fetch_prociv_anepc()
        events.extend(prociv_events)

        return events

    async def _fetch_fogos_pt(self) -> List[GeoEvent]:
        """Fetch from fogos.pt — community API aggregating Portuguese fire data."""
        events = []
        try:
            resp = await self._client.get("https://api.fogos.pt/v2/incidents/active")
            if resp.status_code != 200:
                self.logger.debug(f"fogos.pt returned status {resp.status_code}")
                return []

            data = resp.json()
            incidents = data if isinstance(data, list) else data.get("data", data.get("success", data.get("result", [])))

            if not isinstance(incidents, list):
                self.logger.debug("fogos.pt: unexpected response format")
                return []

            for inc in incidents:
                if not isinstance(inc, dict):
                    continue

                lat = inc.get("lat", 0)
                lng = inc.get("lng", inc.get("lon", 0))

                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    continue

                if lat == 0 or lng == 0:
                    continue

                district = inc.get("district", inc.get("distrito", ""))
                municipality = inc.get("concelho", inc.get("municipality", ""))
                parish = inc.get("freguesia", inc.get("parish", ""))
                nature = inc.get("natureza", inc.get("nature", "Ocorrência"))
                status = inc.get("statusCode", inc.get("status", inc.get("estado", "active")))
                inc_id = inc.get("id", inc.get("shapiId", ""))

                # Determine severity based on nature
                severity = Severity.MEDIUM
                for key, sev in NATURE_SEVERITY.items():
                    if key.lower() in nature.lower():
                        severity = sev
                        break

                # Determine event type
                event_type = EventType.EMERGENCY
                for key, etype in NATURE_TYPE.items():
                    if key.lower() in nature.lower():
                        event_type = etype
                        break

                # Build location description
                location_parts = [p for p in [parish, municipality, district] if p]
                location_str = ", ".join(location_parts) or "Portugal"

                event_id = hashlib.md5(
                    f"fogos_{inc_id}_{lat}_{lng}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=event_type,
                    category="wildfire" if "incêndio" in nature.lower() or "fogo" in nature.lower() else "civil_protection",
                    title=f"{nature}: {location_str}",
                    description=(
                        f"{nature} em {location_str}. "
                        f"Estado: {status}"
                    ),
                    location=Location(lat=lat, lng=lng),
                    radius_km=2.0,
                    severity=severity,
                    source="prociv_fogos",
                    start_time=datetime.utcnow(),
                    metadata={
                        "district": district,
                        "municipality": municipality,
                        "parish": parish,
                        "nature": nature,
                        "status": str(status),
                        "incident_id": str(inc_id),
                        "provider": "fogos.pt",
                    },
                ))

            self.logger.info(f"fogos.pt: fetched {len(events)} active incidents")

        except Exception as e:
            self.logger.warning(f"fogos.pt fetch failed: {e}")

        return events

    async def _fetch_icnf(self) -> List[GeoEvent]:
        """Fetch from ICNF direct API (fallback)."""
        events = []
        try:
            # The real ICNF API endpoint
            resp = await self._client.get(
                "https://fogos.icnf.pt/localizador/webservicealimentacao.asp"
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            fires = data if isinstance(data, list) else data.get("data", data.get("fires", []))

            for fire in fires:
                if not isinstance(fire, dict):
                    continue

                lat = fire.get("lat", fire.get("latitude", 0))
                lng = fire.get("lng", fire.get("longitude", fire.get("lon", 0)))

                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    continue

                if lat == 0 or lng == 0:
                    continue

                district = fire.get("district", fire.get("distrito", "Unknown"))
                municipality = fire.get("municipality", fire.get("concelho", "Unknown"))
                nature = fire.get("nature", fire.get("natureza", "Incêndio"))

                event_id = hashlib.md5(
                    f"icnf_{lat}_{lng}_{fire.get('id', '')}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.EMERGENCY,
                    category="wildfire",
                    title=f"Fire: {municipality}, {district}",
                    description=f"{nature} em {municipality}, {district}",
                    location=Location(lat=lat, lng=lng),
                    radius_km=2.0,
                    severity=Severity.HIGH,
                    source="prociv_icnf",
                    start_time=datetime.utcnow(),
                    metadata={
                        "district": district,
                        "municipality": municipality,
                        "nature": nature,
                        "provider": "icnf.pt",
                    },
                ))

        except Exception as e:
            self.logger.debug(f"ICNF fetch failed: {e}")

        return events

    async def _fetch_prociv_anepc(self) -> List[GeoEvent]:
        """Fetch from ANEPC (ProCiv) occurrences — last resort fallback."""
        events = []
        try:
            # ANEPC provides an occurrence feed
            resp = await self._client.get(
                "https://prociv.gov.pt/pt/situacao_operacional/ocorrencias/ocorrencias.json",
                follow_redirects=True,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            occs = data if isinstance(data, list) else data.get("data", [])

            for occ in occs:
                if not isinstance(occ, dict):
                    continue

                lat = occ.get("lat", occ.get("latitude", 0))
                lng = occ.get("lng", occ.get("longitude", occ.get("lon", 0)))

                try:
                    lat = float(lat)
                    lng = float(lng)
                except (ValueError, TypeError):
                    continue

                if lat == 0 or lng == 0:
                    continue

                nature = occ.get("natureza", occ.get("nature", "Ocorrência"))
                district = occ.get("distrito", occ.get("district", ""))
                municipality = occ.get("concelho", "")

                severity = Severity.MEDIUM
                for key, sev in NATURE_SEVERITY.items():
                    if key.lower() in nature.lower():
                        severity = sev
                        break

                event_id = hashlib.md5(
                    f"anepc_{lat}_{lng}_{occ.get('id', '')}".encode()
                ).hexdigest()

                events.append(GeoEvent(
                    id=event_id,
                    type=EventType.EMERGENCY,
                    category="civil_protection",
                    title=f"{nature}: {municipality}, {district}",
                    description=f"{nature} em {municipality}, {district}",
                    location=Location(lat=lat, lng=lng),
                    radius_km=2.0,
                    severity=severity,
                    source="prociv_anepc",
                    start_time=datetime.utcnow(),
                    metadata={
                        "district": district,
                        "municipality": municipality,
                        "nature": nature,
                        "provider": "prociv.gov.pt",
                    },
                ))

        except Exception as e:
            self.logger.debug(f"ANEPC fetch failed: {e}")

        return events
