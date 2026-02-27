"""
Data Ingestion Scheduler — Polls all adapters at configured intervals
and runs the correlation engine on the aggregated data.
"""

import asyncio
import logging
from typing import List, Dict
from datetime import datetime

from app.services import (
    IPMAWeatherAdapter,
    NASAFIRMSAdapter,
    ProCivAdapter,
    OpenWeatherAdapter,
)
from app.analytics.correlation_engine import CorrelationEngine
from app.models import GeoEvent, HazardAlert, SystemStatus
from app.config import settings

logger = logging.getLogger("ingestion.scheduler")


class DataStore:
    """
    In-memory store for current events and alerts.
    In production, this would be backed by PostgreSQL + PostGIS.
    For the MVP, we keep everything in memory for simplicity.
    """

    def __init__(self):
        self.events: Dict[str, GeoEvent] = {}
        self.alerts: Dict[str, HazardAlert] = {}
        self._lock = asyncio.Lock()
        self.last_correlation_run: datetime | None = None

    async def upsert_events(self, events: List[GeoEvent]):
        async with self._lock:
            for event in events:
                self.events[event.id] = event

    async def get_all_events(self) -> List[GeoEvent]:
        async with self._lock:
            return list(self.events.values())

    async def get_events_by_type(self, event_type: str) -> List[GeoEvent]:
        async with self._lock:
            return [e for e in self.events.values() if e.type == event_type]

    async def set_alerts(self, alerts: List[HazardAlert]):
        async with self._lock:
            self.alerts = {a.id: a for a in alerts}

    async def get_all_alerts(self) -> List[HazardAlert]:
        async with self._lock:
            return list(self.alerts.values())

    async def clear_stale(self, max_age_hours: int = 24):
        """Remove events older than max_age_hours."""
        async with self._lock:
            cutoff = datetime.utcnow()
            to_remove = []
            for eid, event in self.events.items():
                age = (cutoff - event.start_time).total_seconds() / 3600
                if age > max_age_hours:
                    to_remove.append(eid)
            for eid in to_remove:
                del self.events[eid]
            if to_remove:
                logger.info(f"Cleaned {len(to_remove)} stale events")


# Global singleton
data_store = DataStore()


class IngestionScheduler:
    """Manages periodic polling of all data source adapters."""

    def __init__(self):
        self.adapters = {
            "ipma_weather": IPMAWeatherAdapter(),
            "nasa_firms": NASAFIRMSAdapter(),
            "prociv": ProCivAdapter(),
            "openweather": OpenWeatherAdapter(),
        }
        self.correlation_engine = CorrelationEngine()
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Start all polling loops."""
        if self._running:
            return
        self._running = True
        logger.info("Starting ingestion scheduler")

        # Schedule each adapter with its own interval
        self._tasks.append(
            asyncio.create_task(self._poll_loop("ipma_weather", settings.weather_poll_interval))
        )
        self._tasks.append(
            asyncio.create_task(self._poll_loop("nasa_firms", settings.fire_poll_interval))
        )
        self._tasks.append(
            asyncio.create_task(self._poll_loop("prociv", settings.prociv_poll_interval))
        )
        self._tasks.append(
            asyncio.create_task(self._poll_loop("openweather", settings.weather_poll_interval))
        )

        # Correlation engine loop
        self._tasks.append(
            asyncio.create_task(self._correlation_loop())
        )

        # Cleanup loop
        self._tasks.append(
            asyncio.create_task(self._cleanup_loop())
        )

        # Initial fetch of all data
        await self._fetch_all()

    async def stop(self):
        """Stop all polling loops."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        for adapter in self.adapters.values():
            await adapter.close()
        logger.info("Ingestion scheduler stopped")

    async def _fetch_all(self):
        """Fetch from all adapters immediately."""
        for name, adapter in self.adapters.items():
            try:
                events = await adapter.safe_fetch()
                await data_store.upsert_events(events)
            except Exception as e:
                logger.error(f"Initial fetch for {name} failed: {e}")

        # Run correlation after initial fetch
        await self._run_correlation()

    async def _poll_loop(self, adapter_name: str, interval: int):
        """Polling loop for a single adapter."""
        while self._running:
            try:
                await asyncio.sleep(interval)
                adapter = self.adapters[adapter_name]
                events = await adapter.safe_fetch()
                await data_store.upsert_events(events)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll loop for {adapter_name} error: {e}")
                await asyncio.sleep(30)  # Back off on error

    async def _correlation_loop(self):
        """Periodically run the correlation engine."""
        while self._running:
            try:
                await asyncio.sleep(settings.correlation_interval)
                await self._run_correlation()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Correlation loop error: {e}")
                await asyncio.sleep(30)

    async def _run_correlation(self):
        """Run correlation engine on current events."""
        events = await data_store.get_all_events()
        alerts = self.correlation_engine.analyze(events)
        await data_store.set_alerts(alerts)
        data_store.last_correlation_run = datetime.utcnow()
        logger.info(f"Correlation: {len(events)} events → {len(alerts)} alerts")

    async def _cleanup_loop(self):
        """Periodically remove stale events."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                await data_store.clear_stale(max_age_hours=24)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")

    def get_status(self) -> List[SystemStatus]:
        """Get health status of all adapters."""
        return [adapter.status() for adapter in self.adapters.values()]


# Global scheduler singleton
scheduler = IngestionScheduler()
