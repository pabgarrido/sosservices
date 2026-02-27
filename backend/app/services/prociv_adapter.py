"""Proteção Civil Adapter — Portuguese Civil Protection occurrences."""

from typing import List
from datetime import datetime
import hashlib
import re

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


# Known municipality coordinates for geocoding fallback
MUNICIPALITY_COORDS = {
    "Lisboa": (38.7223, -9.1393),
    "Porto": (41.1579, -8.6291),
    "Coimbra": (40.2115, -8.4292),
    "Faro": (37.0194, -7.9322),
    "Braga": (41.5503, -8.4200),
    "Setúbal": (38.5254, -8.8882),
    "Leiria": (39.7437, -8.8071),
    "Viseu": (40.6610, -7.9097),
    "Évora": (38.5711, -7.9093),
    "Aveiro": (40.6405, -8.6538),
    "Santarém": (39.2369, -8.6850),
    "Beja": (38.0154, -7.8631),
    "Castelo Branco": (39.8222, -7.4914),
    "Guarda": (40.5373, -7.2676),
    "Vila Real": (41.2960, -7.7469),
    "Bragança": (41.8072, -6.7589),
    "Viana do Castelo": (41.6935, -8.8327),
    "Portalegre": (39.2967, -7.4310),
}

# ProCiv occurrence nature to severity mapping
NATURE_SEVERITY = {
    "Incêndio Florestal": Severity.HIGH,
    "Incêndio Urbano": Severity.HIGH,
    "Incêndio Rural": Severity.HIGH,
    "Inundação": Severity.HIGH,
    "Acidente Rodoviário": Severity.MEDIUM,
    "Acidente Ferroviário": Severity.HIGH,
    "Queda de Árvore": Severity.LOW,
    "Deslizamento": Severity.HIGH,
    "Busca e Salvamento": Severity.HIGH,
    "Assistência Técnica": Severity.LOW,
    "Pré-Hospitalar": Severity.MEDIUM,
}


class ProCivAdapter(BaseAdapter):
    """Fetches active occurrences from Proteção Civil."""

    def __init__(self):
        super().__init__("prociv")

    async def fetch(self) -> List[GeoEvent]:
        events = []

        # ProCiv provides occurrence data via their API
        # The JSON endpoint for active occurrences
        url = "https://www.prociv.pt/en-us/Pages/Occurrences/OccurrencesMap.aspx"

        # Alternative: use the GNR/ANPC ICNF API for fire-specific data
        # https://fogos.icnf.pt/localizador/webservicealimenalimenalimenalimenalimentacao.asp
        icnf_url = "https://fogos.icnf.pt/localizador/webservicealimenalimenalimenalimenalimentacao.asp"

        try:
            # Try ICNF fires API first (more reliable structured data)
            resp = await self._client.get(icnf_url)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    fires = data if isinstance(data, list) else data.get("data", data.get("fires", []))

                    for fire in fires:
                        if isinstance(fire, dict):
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
                            status = fire.get("status", fire.get("estado", "active"))
                            nature = fire.get("nature", fire.get("natureza", "Incêndio"))

                            event_id = hashlib.md5(
                                f"prociv_{lat}_{lng}_{fire.get('id', '')}".encode()
                            ).hexdigest()

                            events.append(GeoEvent(
                                id=event_id,
                                type=EventType.EMERGENCY,
                                category="wildfire",
                                title=f"Fire: {municipality}, {district}",
                                description=(
                                    f"{nature} in {municipality}, {district}. "
                                    f"Status: {status}"
                                ),
                                location=Location(lat=lat, lng=lng),
                                radius_km=2.0,
                                severity=Severity.HIGH,
                                source="prociv_icnf",
                                start_time=datetime.utcnow(),
                                metadata={
                                    "district": district,
                                    "municipality": municipality,
                                    "status": status,
                                    "nature": nature,
                                },
                            ))
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Failed to parse ICNF data: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to fetch ProCiv/ICNF data: {e}")
            raise

        return events
