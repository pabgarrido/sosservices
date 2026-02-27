"""WebSocket endpoint — pushes real-time events and alerts to connected clients."""

import asyncio
import json
import logging
from typing import Set
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ingestion.scheduler import data_store
from app.models import GeoEvent, HazardAlert

logger = logging.getLogger("api.websocket")
router = APIRouter()

# Connected clients
clients: Set[WebSocket] = set()


async def broadcast(message: dict):
    """Send a message to all connected WebSocket clients."""
    disconnected = set()
    text = json.dumps(message, default=str)
    for ws in clients:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.add(ws)
    clients.difference_update(disconnected)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection for real-time updates.

    On connect: sends current snapshot of events + alerts.
    Then: sends periodic updates every 30 seconds with new/changed data.
    """
    await websocket.accept()
    clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(clients)} total)")

    try:
        # Send initial data snapshot
        events = await data_store.get_all_events()
        alerts = await data_store.get_all_alerts()

        await websocket.send_text(json.dumps({
            "type": "snapshot",
            "events": [e.model_dump() for e in events],
            "alerts": [a.model_dump() for a in alerts],
            "timestamp": datetime.utcnow().isoformat(),
        }, default=str))

        # Keep connection alive and send updates
        last_event_count = len(events)
        last_alert_count = len(alerts)

        while True:
            # Wait for client messages or timeout for periodic push
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle client commands
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    elif msg.get("type") == "refresh":
                        events = await data_store.get_all_events()
                        alerts = await data_store.get_all_alerts()
                        await websocket.send_text(json.dumps({
                            "type": "snapshot",
                            "events": [e.model_dump() for e in events],
                            "alerts": [a.model_dump() for a in alerts],
                            "timestamp": datetime.utcnow().isoformat(),
                        }, default=str))
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send update if data has changed
                events = await data_store.get_all_events()
                alerts = await data_store.get_all_alerts()

                current_event_count = len(events)
                current_alert_count = len(alerts)

                if current_event_count != last_event_count or current_alert_count != last_alert_count:
                    await websocket.send_text(json.dumps({
                        "type": "update",
                        "events": [e.model_dump() for e in events],
                        "alerts": [a.model_dump() for a in alerts],
                        "timestamp": datetime.utcnow().isoformat(),
                    }, default=str))
                    last_event_count = current_event_count
                    last_alert_count = current_alert_count
                else:
                    # Send heartbeat
                    await websocket.send_text(json.dumps({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat(),
                    }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(clients)} remaining)")
