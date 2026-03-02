"""Fire Detection Adapter — NASA FIRMS satellite fire data."""

from typing import List
from datetime import datetime
import hashlib
import csv
import io

from app.services.base_adapter import BaseAdapter
from app.models import GeoEvent, EventType, Severity, Location
from app.config import settings


class NASAFIRMSAdapter(BaseAdapter):
    """Fetches active fire detections from NASA FIRMS for Portugal."""

    def __init__(self):
        super().__init__("nasa_firms")
        self.api_key = settings.nasa_firms_api_key

    async def fetch(self) -> List[GeoEvent]:
        if not self.api_key:
            self.logger.info(
                "NASA FIRMS API key not set (NASA_FIRMS_API_KEY env var). "
                "Register free at https://firms.modaps.eosdis.nasa.gov/api/. "
                "Satellite fire data will be unavailable until configured. "
                "Fire data is still available via ProCiv/fogos.pt adapter."
            )
            return []

        events = []

        # FIRMS VIIRS data for Portugal (country code PRT)
        # Fetch last 24h of fire detections within Portugal bounding box
        url = (
            f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
            f"{self.api_key}/VIIRS_SNPP_NRT/"
            f"{settings.pt_lon_min},{settings.pt_lat_min},"
            f"{settings.pt_lon_max},{settings.pt_lat_max}/1"
        )

        try:
            resp = await self._client.get(url)
            resp.raise_for_status()

            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                try:
                    lat = float(row.get("latitude", 0))
                    lng = float(row.get("longitude", 0))
                    confidence = row.get("confidence", "nominal")
                    bright = float(row.get("bright_ti4", 0))
                    frp = float(row.get("frp", 0))
                    acq_date = row.get("acq_date", "")
                    acq_time = row.get("acq_time", "")

                    # Skip low-confidence detections
                    if confidence == "low":
                        continue

                    # Determine severity from fire radiative power
                    severity = Severity.LOW
                    if frp > 10:
                        severity = Severity.MEDIUM
                    if frp > 50:
                        severity = Severity.HIGH
                    if frp > 100:
                        severity = Severity.CRITICAL

                    event_id = hashlib.md5(
                        f"firms_{lat}_{lng}_{acq_date}_{acq_time}".encode()
                    ).hexdigest()

                    # Parse acquisition datetime
                    try:
                        acq_dt = datetime.strptime(
                            f"{acq_date} {acq_time}", "%Y-%m-%d %H%M"
                        )
                    except ValueError:
                        acq_dt = datetime.utcnow()

                    events.append(GeoEvent(
                        id=event_id,
                        type=EventType.EMERGENCY,
                        category="wildfire_detection",
                        title=f"Fire detected (FRP: {frp:.1f} MW)",
                        description=(
                            f"Satellite fire detection at ({lat:.4f}, {lng:.4f}). "
                            f"Fire Radiative Power: {frp:.1f} MW, "
                            f"Brightness Temperature: {bright:.1f} K, "
                            f"Confidence: {confidence}"
                        ),
                        location=Location(lat=lat, lng=lng),
                        radius_km=1.0,
                        severity=severity,
                        source="nasa_firms",
                        start_time=acq_dt,
                        metadata={
                            "confidence": confidence,
                            "brightness": bright,
                            "frp": frp,
                            "satellite": "VIIRS_SNPP",
                            "acq_date": acq_date,
                            "acq_time": acq_time,
                        },
                    ))
                except (ValueError, KeyError) as e:
                    self.logger.debug(f"Skipping fire row: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to fetch FIRMS data: {e}")
            raise

        return events
