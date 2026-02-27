"""Base adapter interface for all data sources."""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
import httpx
import logging

from app.models import GeoEvent, SystemStatus


class BaseAdapter(ABC):
    """All data source adapters inherit from this."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"adapter.{name}")
        self.last_fetch: Optional[datetime] = None
        self.event_count: int = 0
        self.healthy: bool = True
        self.last_error: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    @abstractmethod
    async def fetch(self) -> List[GeoEvent]:
        """Fetch and return normalized events from this source."""
        ...

    async def safe_fetch(self) -> List[GeoEvent]:
        """Fetch with error handling."""
        try:
            events = await self.fetch()
            self.last_fetch = datetime.utcnow()
            self.event_count = len(events)
            self.healthy = True
            self.last_error = None
            self.logger.info(f"Fetched {len(events)} events")
            return events
        except Exception as e:
            self.healthy = False
            self.last_error = str(e)
            self.logger.error(f"Fetch failed: {e}")
            return []

    def status(self) -> SystemStatus:
        return SystemStatus(
            adapter=self.name,
            healthy=self.healthy,
            last_fetch=self.last_fetch,
            event_count=self.event_count,
            error=self.last_error,
        )

    async def close(self):
        await self._client.aclose()
