import React, { useState, useEffect, useCallback, useMemo } from 'react';
import HazardMap from './components/HazardMap';
import LayerControl, { TRAFFIC_SUBLAYERS, EVENT_SUBLAYERS } from './components/LayerControl';
import AlertPanel from './components/AlertPanel';
import AnalyticsPanel from './components/AnalyticsPanel';
import TimeSlider from './components/TimeSlider';
import StatusBar from './components/StatusBar';
import useWebSocket from './hooks/useWebSocket';
import { fetchEvents, fetchAlerts, fetchLayers, fetchStatus, fetchHazardScores, fetchRiskZones, fetchAnalyticsSummary, fetchTimeRange } from './services/api';

const API_URL = process.env.REACT_APP_API_URL || '';
const WS_PROTOCOL = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_HOST = typeof window !== 'undefined' ? window.location.host : 'localhost';
const WS_URL = process.env.REACT_APP_WS_URL || `${WS_PROTOCOL}//${WS_HOST}/ws`;

function App() {
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [layers, setLayers] = useState([]);
  const [status, setStatus] = useState([]);
  const [activeLayers, setActiveLayers] = useState(new Set(['weather', 'emergency', 'traffic', 'event']));
  const [activeTrafficSublayers, setActiveTrafficSublayers] = useState(
    new Set(TRAFFIC_SUBLAYERS.map((s) => s.id))
  );
  const [activeEventSublayers, setActiveEventSublayers] = useState(
    new Set(EVENT_SUBLAYERS.map((s) => s.id))
  );
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [analyticsSummary, setAnalyticsSummary] = useState({});
  const [hazardScores, setHazardScores] = useState([]);
  const [riskZones, setRiskZones] = useState([]);
  const [showRiskZones, setShowRiskZones] = useState(true);
  const [sidebarTab, setSidebarTab] = useState('layers'); // 'layers' | 'analytics'
  const [timeRange, setTimeRange] = useState(null);
  const [timePosition, setTimePosition] = useState(null); // null = "live"
  const [flyToLocation, setFlyToLocation] = useState(null);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [mapDetailMode, setMapDetailMode] = useState('high'); // 'standard' | 'high'
  const [mapLegendVisible, setMapLegendVisible] = useState(() => {
    try {
      return localStorage.getItem('mapLegendVisible') !== 'false';
    } catch {
      return true;
    }
  });

  // Handler for analytics "Locate on Map" — fly to event location
  const handleLocateEvent = useCallback((location, eventId) => {
    setFlyToLocation({ lat: location.lat, lng: location.lng });
    // Clear after a moment so it can be re-triggered for same location
    setTimeout(() => setFlyToLocation(null), 2000);
  }, []);

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

  useEffect(() => {
    try {
      localStorage.setItem('mapLegendVisible', String(mapLegendVisible));
    } catch {
      // ignore storage unavailability
    }
  }, [mapLegendVisible]);

  // Compute time window params for API calls based on slider position
  const timeWindowParams = useMemo(() => {
    if (!timePosition) return {};
    const sliderTs = new Date(timePosition).getTime();
    const windowMs = 3 * 3600000; // ±3 hours
    return {
      timeStart: new Date(sliderTs - windowMs).toISOString(),
      timeEnd: new Date(sliderTs + windowMs).toISOString(),
    };
  }, [timePosition]);

  // Initial data fetch (fallback if WS not available)
  useEffect(() => {
    const loadData = async () => {
      const [evtsResult, alrtsResult, lyrsResult, stsResult] = await Promise.allSettled([
        fetchEvents(API_URL),
        fetchAlerts(API_URL),
        fetchLayers(API_URL),
        fetchStatus(API_URL),
      ]);
      if (evtsResult.status === 'fulfilled') setEvents(evtsResult.value);
      if (alrtsResult.status === 'fulfilled') setAlerts(alrtsResult.value);
      if (lyrsResult.status === 'fulfilled') setLayers(lyrsResult.value);
      if (stsResult.status === 'fulfilled') setStatus(stsResult.value);
      if ([evtsResult, alrtsResult, lyrsResult, stsResult].some((r) => r.status === 'rejected')) {
        console.warn('Some initial data failed to load');
      }
      setIsInitialLoading(false);

      // Load analytics + time range data (non-blocking)
      try {
        const [scores, zones, summary, tRange] = await Promise.all([
          fetchHazardScores(API_URL, { limit: 500 }),
          fetchRiskZones(API_URL),
          fetchAnalyticsSummary(API_URL),
          fetchTimeRange(API_URL),
        ]);
        setHazardScores(scores);
        setRiskZones(zones);
        setAnalyticsSummary(summary);
        setTimeRange(tRange);
      } catch (err) {
        console.warn('Analytics data not available yet:', err);
      }
    };
    loadData();

    // Refresh layers, status, and analytics periodically
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

      // Refresh analytics + time range (only if live / no slider override)
      if (!timePosition) {
        try {
          const [scores, zones, summary, tRange] = await Promise.all([
            fetchHazardScores(API_URL, { limit: 500 }),
            fetchRiskZones(API_URL),
            fetchAnalyticsSummary(API_URL),
            fetchTimeRange(API_URL),
          ]);
          setHazardScores(scores);
          setRiskZones(zones);
          setAnalyticsSummary(summary);
          setTimeRange(tRange);
        } catch (err) {
          // Analytics may not be ready yet
        }
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [timePosition]);

  // Re-fetch analytics when time slider moves (debounced)
  useEffect(() => {
    // Skip on initial render — handled by the main fetch above
    if (timePosition === null) return;

    const timer = setTimeout(async () => {
      try {
        const { timeStart, timeEnd } = timeWindowParams;
        const [scores, zones, summary] = await Promise.all([
          fetchHazardScores(API_URL, { limit: 500, timeStart, timeEnd }),
          fetchRiskZones(API_URL, { timeStart, timeEnd }),
          fetchAnalyticsSummary(API_URL, { timeStart, timeEnd }),
        ]);
        setHazardScores(scores);
        setRiskZones(zones);
        setAnalyticsSummary(summary);
      } catch (err) {
        console.warn('Time-windowed analytics fetch failed:', err);
      }
    }, 400); // 400ms debounce

    return () => clearTimeout(timer);
  }, [timeWindowParams]);

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

  const toggleTrafficSublayer = (sublayerId) => {
    setActiveTrafficSublayers((prev) => {
      const next = new Set(prev);
      if (next.has(sublayerId)) {
        next.delete(sublayerId);
      } else {
        next.add(sublayerId);
      }
      return next;
    });
  };

  const toggleEventSublayer = (sublayerId) => {
    setActiveEventSublayers((prev) => {
      const next = new Set(prev);
      if (next.has(sublayerId)) {
        next.delete(sublayerId);
      } else {
        next.add(sublayerId);
      }
      return next;
    });
  };

  // Build a lookup: category+source → sublayer id
  const trafficSublayerLookup = useMemo(() => {
    const lookup = {};
    TRAFFIC_SUBLAYERS.forEach((sub) => {
      sub.categories.forEach((cat) => {
        sub.sources.forEach((src) => {
          lookup[`${cat}__${src}`] = sub.id;
        });
        // Also match by category alone (fallback)
        lookup[`${cat}__*`] = sub.id;
      });
    });
    return lookup;
  }, []);

  // Build a lookup: category → event sublayer id
  const eventSublayerLookup = useMemo(() => {
    const lookup = {};
    EVENT_SUBLAYERS.forEach((sub) => {
      sub.categories.forEach((cat) => {
        lookup[cat] = sub.id;
      });
    });
    return lookup;
  }, []);

  // Compute sublayer event counts for the sidebar
  const trafficSublayerInfo = useMemo(() => {
    const counts = {};
    TRAFFIC_SUBLAYERS.forEach((s) => { counts[s.id] = 0; });

    events.forEach((e) => {
      if (e.type !== 'traffic') return;
      const key1 = `${e.category}__${e.source}`;
      const key2 = `${e.category}__*`;
      const subId = trafficSublayerLookup[key1] || trafficSublayerLookup[key2];
      if (subId) counts[subId]++;
    });

    return { active: activeTrafficSublayers, counts };
  }, [events, activeTrafficSublayers, trafficSublayerLookup]);

  // Compute event sublayer counts
  const eventSublayerInfo = useMemo(() => {
    const counts = {};
    EVENT_SUBLAYERS.forEach((s) => { counts[s.id] = 0; });

    events.forEach((e) => {
      if (e.type !== 'event') return;
      const subId = eventSublayerLookup[e.category];
      if (subId) counts[subId]++;
    });

    return { active: activeEventSublayers, counts };
  }, [events, activeEventSublayers, eventSublayerLookup]);

  // Filter events by active layers + traffic sublayers + time window
  const visibleEvents = useMemo(() => {
    return events.filter((e) => {
      if (!activeLayers.has(e.type)) return false;

      // Apply traffic sublayer filtering
      if (e.type === 'traffic') {
        const key1 = `${e.category}__${e.source}`;
        const key2 = `${e.category}__*`;
        const subId = trafficSublayerLookup[key1] || trafficSublayerLookup[key2];
        if (subId && !activeTrafficSublayers.has(subId)) return false;
      }

      // Apply event sublayer filtering
      if (e.type === 'event') {
        const subId = eventSublayerLookup[e.category];
        if (subId && !activeEventSublayers.has(subId)) return false;
      }

      // Time window filtering (client-side)
      if (timePosition) {
        const windowMs = 3 * 3600000; // ±3 hours window
        const sliderTs = new Date(timePosition).getTime();
        const windowStart = sliderTs - windowMs;
        const windowEnd = sliderTs + windowMs;
        const evStart = new Date(e.start_time).getTime();
        const evEnd = e.end_time ? new Date(e.end_time).getTime() : evStart;
        // Event must overlap the window
        if (evStart > windowEnd || evEnd < windowStart) return false;
      }

      return true;
    });
  }, [events, activeLayers, activeTrafficSublayers, trafficSublayerLookup, activeEventSublayers, eventSublayerLookup, timePosition]);

  // Build event_id → score lookup map for the map markers
  const hazardScoreMap = useMemo(() => {
    const map = {};
    if (hazardScores && hazardScores.length > 0) {
      hazardScores.forEach((s) => {
        map[s.event_id] = s.score;
      });
    }
    return map;
  }, [hazardScores]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>🚨 SOS Services</h1>
          <span className="subtitle">Portugal Real-Time Hazard Monitor</span>
        </div>
        <div className="header-right">
          <span className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`} aria-live="polite">
            {isConnected ? '● Live' : '○ Offline'}
          </span>
          <span className="event-count">{events.length} events</span>
          <span className="alert-count">{alerts.length} alerts</span>
          {analyticsSummary?.overall_score != null && (
            <span
              className="risk-score-badge"
              data-level={analyticsSummary.overall_risk || 'none'}
            >
              Risk: {analyticsSummary.overall_score.toFixed(0)}
            </span>
          )}
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          {/* Sidebar tab switcher */}
          <div className="sidebar-tabs" role="tablist" aria-label="Sidebar views">
            <button
              className={`sidebar-tab ${sidebarTab === 'layers' ? 'active' : ''}`}
              onClick={() => setSidebarTab('layers')}
              role="tab"
              aria-selected={sidebarTab === 'layers'}
              aria-controls="sidebar-layers"
            >
              Layers & Alerts
            </button>
            <button
              className={`sidebar-tab ${sidebarTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setSidebarTab('analytics')}
              role="tab"
              aria-selected={sidebarTab === 'analytics'}
              aria-controls="sidebar-analytics"
            >
              Analytics
            </button>
          </div>

          {sidebarTab === 'layers' && (
            <div id="sidebar-layers" role="tabpanel">
              {isInitialLoading ? (
                <div className="sidebar-loading" aria-live="polite">
                  <div className="loading-block loading-title" />
                  <div className="loading-block" />
                  <div className="loading-block" />
                  <div className="loading-block" />
                  <div className="loading-separator" />
                  <div className="loading-block loading-title" />
                  <div className="loading-card" />
                  <div className="loading-card" />
                </div>
              ) : (
                <>
                  <LayerControl
                    layers={layers}
                    activeLayers={activeLayers}
                    onToggle={toggleLayer}
                    trafficSublayers={trafficSublayerInfo}
                    onToggleTrafficSublayer={toggleTrafficSublayer}
                    eventSublayers={eventSublayerInfo}
                    onToggleEventSublayer={toggleEventSublayer}
                  />
                  {/* Risk Zones toggle */}
                  <div className="risk-zone-toggle">
                    <label className="layer-item">
                      <input
                        type="checkbox"
                        checked={showRiskZones}
                        onChange={() => setShowRiskZones(!showRiskZones)}
                      />
                      <span className="layer-color" style={{ backgroundColor: '#e74c3c' }} />
                      <span className="layer-name">Risk Zones</span>
                      <span className="layer-count">{riskZones.length}</span>
                    </label>
                  </div>
                  <div className="map-detail-toggle" role="group" aria-label="Map detail mode">
                    <span className="map-detail-label">Map detail</span>
                    <div className="map-detail-buttons">
                      <button
                        className={`map-detail-btn ${mapDetailMode === 'standard' ? 'active' : ''}`}
                        onClick={() => setMapDetailMode('standard')}
                        aria-pressed={mapDetailMode === 'standard'}
                      >
                        Standard
                      </button>
                      <button
                        className={`map-detail-btn ${mapDetailMode === 'high' ? 'active' : ''}`}
                        onClick={() => setMapDetailMode('high')}
                        aria-pressed={mapDetailMode === 'high'}
                      >
                        High Detail
                      </button>
                    </div>
                  </div>
                  <AlertPanel alerts={alerts} onSelect={setSelectedAlert} />
                </>
              )}
            </div>
          )}

          {sidebarTab === 'analytics' && (
            <div id="sidebar-analytics" role="tabpanel">
              {isInitialLoading ? (
                <div className="sidebar-loading" aria-live="polite">
                  <div className="loading-block loading-title" />
                  <div className="loading-gauge" />
                  <div className="loading-tabs" />
                  <div className="loading-card" />
                  <div className="loading-card" />
                </div>
              ) : (
                <AnalyticsPanel
                  summary={analyticsSummary}
                  hazardScores={hazardScores}
                  onLocateEvent={handleLocateEvent}
                />
              )}
            </div>
          )}
        </aside>

        <main className="map-container">
          <HazardMap
            events={visibleEvents}
            alerts={alerts}
            selectedAlert={selectedAlert}
            riskZones={riskZones}
            showRiskZones={showRiskZones}
            hazardScoreMap={hazardScoreMap}
            timePosition={timePosition}
            flyToLocation={flyToLocation}
            mapDetailMode={mapDetailMode}
          />
          {mapLegendVisible && (
            <div className="map-detail-legend" aria-live="polite">
              <div className="map-detail-legend-header">
                <strong>{mapDetailMode === 'high' ? 'High Detail Map' : 'Standard Map'}</strong>
                <button
                  className="map-detail-legend-close"
                  onClick={() => setMapLegendVisible(false)}
                  aria-label="Dismiss map detail help"
                  title="Hide help"
                >
                  ×
                </button>
              </div>
              <span>
                {mapDetailMode === 'high'
                  ? 'Road labels + rail lines enabled for precision analysis.'
                  : 'Base map only for lighter rendering performance.'}
              </span>
            </div>
          )}
          <div className="time-slider-overlay">
            <TimeSlider
              timeRange={timeRange}
              value={timePosition}
              onChange={setTimePosition}
            />
          </div>
        </main>
      </div>

      <StatusBar status={status} eventCount={events.length} alertCount={alerts.length} />
    </div>
  );
}

export default App;
