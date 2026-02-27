import React, { useState, useEffect, useCallback } from 'react';
import HazardMap from './components/HazardMap';
import LayerControl from './components/LayerControl';
import AlertPanel from './components/AlertPanel';
import StatusBar from './components/StatusBar';
import useWebSocket from './hooks/useWebSocket';
import { fetchEvents, fetchAlerts, fetchLayers, fetchStatus } from './services/api';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

function App() {
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [layers, setLayers] = useState([]);
  const [status, setStatus] = useState([]);
  const [activeLayers, setActiveLayers] = useState(new Set(['weather', 'fire', 'emergency', 'traffic', 'event']));
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [isConnected, setIsConnected] = useState(false);

  // WebSocket for real-time updates
  const onMessage = useCallback((data) => {
    if (data.type === 'snapshot' || data.type === 'update') {
      if (data.events) setEvents(data.events);
      if (data.alerts) setAlerts(data.alerts);
    }
  }, []);

  const { connected } = useWebSocket(WS_URL, onMessage);

  useEffect(() => {
    setIsConnected(connected);
  }, [connected]);

  // Initial data fetch (fallback if WS not available)
  useEffect(() => {
    const loadData = async () => {
      try {
        const [evts, alrts, lyrs, sts] = await Promise.all([
          fetchEvents(API_URL),
          fetchAlerts(API_URL),
          fetchLayers(API_URL),
          fetchStatus(API_URL),
        ]);
        setEvents(evts);
        setAlerts(alrts);
        setLayers(lyrs);
        setStatus(sts);
      } catch (err) {
        console.error('Failed to load initial data:', err);
      }
    };
    loadData();

    // Refresh layers and status periodically
    const interval = setInterval(async () => {
      try {
        const [lyrs, sts] = await Promise.all([
          fetchLayers(API_URL),
          fetchStatus(API_URL),
        ]);
        setLayers(lyrs);
        setStatus(sts);
      } catch (err) {
        console.warn('Status refresh failed:', err);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const toggleLayer = (layerId) => {
    setActiveLayers((prev) => {
      const next = new Set(prev);
      if (next.has(layerId)) {
        next.delete(layerId);
      } else {
        next.add(layerId);
      }
      return next;
    });
  };

  // Filter events by active layers
  const visibleEvents = events.filter((e) => activeLayers.has(e.type));

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>🚨 SOS Services</h1>
          <span className="subtitle">Portugal Real-Time Hazard Monitor</span>
        </div>
        <div className="header-right">
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            {isConnected ? '● Live' : '○ Offline'}
          </span>
          <span className="event-count">{events.length} events</span>
          <span className="alert-count">{alerts.length} alerts</span>
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <LayerControl layers={layers} activeLayers={activeLayers} onToggle={toggleLayer} />
          <AlertPanel alerts={alerts} onSelect={setSelectedAlert} />
        </aside>

        <main className="map-container">
          <HazardMap
            events={visibleEvents}
            alerts={alerts}
            selectedAlert={selectedAlert}
          />
        </main>
      </div>

      <StatusBar status={status} eventCount={events.length} alertCount={alerts.length} />
    </div>
  );
}

export default App;
