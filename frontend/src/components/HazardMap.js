import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, Rectangle, Popup, Tooltip, useMap } from 'react-leaflet';

// Portugal center coordinates
const PORTUGAL_CENTER = [39.5, -8.0];
const PORTUGAL_ZOOM = 7;

const MAP_LAYERS = {
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  darkLabels: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png',
    attribution: '', // Attribution already included via dark base layer
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
  },
};

// Color mapping for event types
const EVENT_COLORS = {
  weather: '#3498db',
  emergency: '#e67e22',
  traffic: '#9b59b6',
  event: '#2ecc71',
};

// Traffic sub-category colors (overrides the generic traffic purple)
const TRAFFIC_CATEGORY_COLORS = {
  traffic_free: '#2ecc71',
  traffic_moderate: '#f39c12',
  traffic_slow: '#e67e22',
  traffic_jam: '#e74c3c',
  road_closed: '#c0392b',
  accident: '#c0392b',
  road_hazard: '#c0392b',
  lane_closed: '#c0392b',
  traffic_incident: '#c0392b',
  road_works: '#8e44ad',
  road_works_major: '#6c3483',
};

// Event sub-category colors
const EVENT_CATEGORY_COLORS = {
  concert: '#1abc9c',
  festival: '#e74c3c',
  sports: '#3498db',
  arts_theatre: '#9b59b6',
  conference: '#f39c12',
  public_event: '#2ecc71',
  public_holiday: '#2ecc71',
};

// Color for hazard alert levels
const ALERT_COLORS = {
  none: '#95a5a6',
  watch: '#f1c40f',
  warning: '#e67e22',
  danger: '#e74c3c',
  extreme: '#8e44ad',
};

// Risk zone colors by hazard level
const ZONE_COLORS = {
  none: '#2ecc71',
  watch: '#f1c40f',
  warning: '#e67e22',
  danger: '#e74c3c',
  extreme: '#8e44ad',
};

const SEVERITY_RADIUS = {
  low: 6,
  medium: 9,
  high: 12,
  critical: 16,
};

// Grid cell size in degrees (must match backend GRID_CELL_DEG)
const GRID_CELL_DEG = 0.25;

function FlyToAlert({ alert }) {
  const map = useMap();
  const lastAlertId = useRef(null);

  useEffect(() => {
    if (!alert?.id || !alert?.location) return;
    if (lastAlertId.current === alert.id) return;

    map.flyTo([alert.location.lat, alert.location.lng], 10, { duration: 1.5 });
    lastAlertId.current = alert.id;
  }, [alert, map]);

  return null;
}

function FlyToLocation({ location }) {
  const map = useMap();
  const lastLocationKey = useRef('');

  useEffect(() => {
    if (!location) return;
    const key = `${location.lat},${location.lng}`;
    if (lastLocationKey.current === key) return;

    map.flyTo([location.lat, location.lng], 12, { duration: 1.2 });
    lastLocationKey.current = key;
  }, [location, map]);

  return null;
}

function scoreToColor(score) {
  if (score >= 80) return '#8e44ad';
  if (score >= 60) return '#e74c3c';
  if (score >= 40) return '#e67e22';
  if (score >= 20) return '#f1c40f';
  return '#2ecc71';
}

function HazardMap({ events, alerts, selectedAlert, riskZones, showRiskZones, hazardScoreMap, timePosition, flyToLocation, mapDetailMode = 'high' }) {
  // Memoize event markers
  const eventMarkers = useMemo(() => {
    return events.map((event) => {
      // Use traffic sub-category colors when applicable
      let color = EVENT_COLORS[event.type] || '#95a5a6';
      if (event.type === 'traffic' && TRAFFIC_CATEGORY_COLORS[event.category]) {
        color = TRAFFIC_CATEGORY_COLORS[event.category];
      }
      if (event.type === 'event' && EVENT_CATEGORY_COLORS[event.category]) {
        color = EVENT_CATEGORY_COLORS[event.category];
      }

      // Check if this is a forecast event
      const isForecast = event.metadata?.is_forecast === true ||
        (event.category && event.category.startsWith('forecast'));

      // If hazard score map available, use score-based color for the ring
      const eventScore = hazardScoreMap?.[event.id];
      const ringColor = eventScore != null ? scoreToColor(eventScore) : color;
      const radius = SEVERITY_RADIUS[event.severity] || 6;

      return (
        <CircleMarker
          key={event.id}
          center={[event.location.lat, event.location.lng]}
          radius={radius}
          pathOptions={{
            color: ringColor,
            fillColor: color,
            fillOpacity: isForecast ? 0.4 : 0.7,
            weight: eventScore != null && eventScore >= 40 ? 3 : 2,
            dashArray: isForecast ? '4, 4' : undefined,
          }}
        >
          <Tooltip direction="top" offset={[0, -10]}>
            <strong>{event.title}</strong>
            {isForecast && (
              <>
                <br />
                <small style={{ color: '#3498db', fontWeight: 600 }}>📊 FORECAST</small>
              </>
            )}
            <br />
            <small>{event.source} — {event.severity}</small>
            {eventScore != null && (
              <>
                <br />
                <small style={{ color: scoreToColor(eventScore), fontWeight: 700 }}>
                  Hazard Score: {eventScore.toFixed(0)}
                </small>
              </>
            )}
          </Tooltip>
          <Popup>
            <div className="event-popup">
              <h3>{event.title}</h3>
              <p className="event-type-badge" style={{ backgroundColor: color }}>
                {event.type.toUpperCase()} — {event.severity.toUpperCase()}
                {isForecast && ' — FORECAST'}
              </p>
              {eventScore != null && (
                <p
                  className="event-score-badge"
                  style={{ backgroundColor: scoreToColor(eventScore) }}
                >
                  HAZARD SCORE: {eventScore.toFixed(0)}/100
                </p>
              )}
              <p>{event.description}</p>
              <p className="event-meta">
                <strong>Source:</strong> {event.source}<br />
                <strong>Category:</strong> {event.category}<br />
                <strong>Time:</strong> {new Date(event.start_time).toLocaleString('pt-PT')}
              </p>
            </div>
          </Popup>
        </CircleMarker>
      );
    });
  }, [events, hazardScoreMap]);

  // Memoize alert circles
  const alertCircles = useMemo(() => {
    return alerts.map((alert) => {
      const color = ALERT_COLORS[alert.level] || '#95a5a6';

      return (
        <Circle
          key={alert.id}
          center={[alert.location.lat, alert.location.lng]}
          radius={alert.radius_km * 1000}
          pathOptions={{
            color: color,
            fillColor: color,
            fillOpacity: 0.15,
            weight: 3,
            dashArray: '10, 5',
          }}
        >
          <Popup>
            <div className="alert-popup">
              <h3 style={{ color: color }}>⚠ {alert.title}</h3>
              <p className="alert-level-badge" style={{ backgroundColor: color }}>
                {alert.level.toUpperCase()}
              </p>
              <p>{alert.description}</p>
              <p className="alert-action">
                <strong>Recommended Action:</strong><br />
                {alert.recommended_action}
              </p>
              <p className="alert-meta">
                <strong>Contributing events:</strong> {alert.contributing_events.length}<br />
                <strong>Radius:</strong> {alert.radius_km.toFixed(1)} km<br />
                <strong>Expires:</strong> {alert.expires_at ? new Date(alert.expires_at).toLocaleString('pt-PT') : 'N/A'}
              </p>
            </div>
          </Popup>
        </Circle>
      );
    });
  }, [alerts]);

  // Memoize risk zone rectangles
  const zoneRects = useMemo(() => {
    if (!showRiskZones || !riskZones || riskZones.length === 0) return null;
    return riskZones.map((zone) => {
      const halfCell = GRID_CELL_DEG / 2;
      const bounds = [
        [zone.lat - halfCell, zone.lng - halfCell],
        [zone.lat + halfCell, zone.lng + halfCell],
      ];
      const color = ZONE_COLORS[zone.hazard_level] || '#95a5a6';
      const opacity = Math.min(0.15 + (zone.score / 100) * 0.45, 0.65);

      return (
        <Rectangle
          key={zone.cell_id}
          bounds={bounds}
          pathOptions={{
            color: color,
            fillColor: color,
            fillOpacity: opacity,
            weight: 1,
            opacity: 0.7,
          }}
        >
          <Tooltip direction="center" permanent={false}>
            <strong>Risk Zone</strong><br />
            Score: {zone.score.toFixed(0)}/100<br />
            {zone.event_count} events<br />
            Main cause: {zone.dominant_type}<br />
            {zone.top_factors && zone.top_factors.slice(0, 3).map((f, i) => (
              <span key={i}>{f}<br /></span>
            ))}
          </Tooltip>
        </Rectangle>
      );
    });
  }, [riskZones, showRiskZones]);

  return (
    <MapContainer
      center={PORTUGAL_CENTER}
      zoom={PORTUGAL_ZOOM}
      style={{ height: '100%', width: '100%' }}
      zoomControl={true}
      minZoom={5}
      maxZoom={18}
    >
      <TileLayer
        attribution={mapDetailMode === 'satellite'
          ? MAP_LAYERS.satellite.attribution
          : MAP_LAYERS.dark.attribution}
        url={mapDetailMode === 'satellite'
          ? MAP_LAYERS.satellite.url
          : MAP_LAYERS.dark.url}
      />

      {mapDetailMode !== 'satellite' && (
        <TileLayer
          attribution={MAP_LAYERS.darkLabels.attribution}
          url={MAP_LAYERS.darkLabels.url}
          opacity={0.9}
        />
      )}

      {zoneRects}
      {alertCircles}
      {eventMarkers}

      {selectedAlert && <FlyToAlert alert={selectedAlert} />}
      {flyToLocation && <FlyToLocation location={flyToLocation} />}
    </MapContainer>
  );
}

export default HazardMap;
