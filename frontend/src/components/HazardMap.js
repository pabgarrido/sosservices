import React, { useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Circle, Popup, Tooltip, useMap } from 'react-leaflet';

// Portugal center coordinates
const PORTUGAL_CENTER = [39.5, -8.0];
const PORTUGAL_ZOOM = 7;

// Color mapping for event types
const EVENT_COLORS = {
  weather: '#3498db',
  fire: '#e74c3c',
  emergency: '#e67e22',
  traffic: '#9b59b6',
  event: '#2ecc71',
};

// Color for hazard alert levels
const ALERT_COLORS = {
  none: '#95a5a6',
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

function FlyToAlert({ alert }) {
  const map = useMap();
  if (alert) {
    map.flyTo([alert.location.lat, alert.location.lng], 10, { duration: 1.5 });
  }
  return null;
}

function HazardMap({ events, alerts, selectedAlert }) {
  // Memoize event markers
  const eventMarkers = useMemo(() => {
    return events.map((event) => {
      const color = EVENT_COLORS[event.type] || '#95a5a6';
      const radius = SEVERITY_RADIUS[event.severity] || 6;

      return (
        <CircleMarker
          key={event.id}
          center={[event.location.lat, event.location.lng]}
          radius={radius}
          pathOptions={{
            color: color,
            fillColor: color,
            fillOpacity: 0.7,
            weight: 2,
          }}
        >
          <Tooltip direction="top" offset={[0, -10]}>
            <strong>{event.title}</strong>
            <br />
            <small>{event.source} — {event.severity}</small>
          </Tooltip>
          <Popup>
            <div className="event-popup">
              <h3>{event.title}</h3>
              <p className="event-type-badge" style={{ backgroundColor: color }}>
                {event.type.toUpperCase()} — {event.severity.toUpperCase()}
              </p>
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
  }, [events]);

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
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {alertCircles}
      {eventMarkers}

      {selectedAlert && <FlyToAlert alert={selectedAlert} />}
    </MapContainer>
  );
}

export default HazardMap;
