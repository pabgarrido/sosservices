import React, { useState, useMemo } from 'react';

// Traffic sub-layers configuration
const TRAFFIC_SUBLAYERS = [
  {
    id: 'traffic_flow_free',
    name: 'Free Flow',
    color: '#2ecc71',
    categories: ['traffic_free'],
    sources: ['traffic_flow'],
  },
  {
    id: 'traffic_flow_moderate',
    name: 'Moderate Traffic',
    color: '#f39c12',
    categories: ['traffic_moderate'],
    sources: ['traffic_flow'],
  },
  {
    id: 'traffic_flow_slow',
    name: 'Slow Traffic',
    color: '#e67e22',
    categories: ['traffic_slow'],
    sources: ['traffic_flow'],
  },
  {
    id: 'traffic_flow_jam',
    name: 'Traffic Jam',
    color: '#e74c3c',
    categories: ['traffic_jam'],
    sources: ['traffic_flow'],
  },
  {
    id: 'traffic_incidents',
    name: 'Incidents & Closures',
    color: '#c0392b',
    categories: ['accident', 'road_hazard', 'road_closed', 'lane_closed', 'traffic_incident'],
    sources: ['traffic_tomtom'],
  },
  {
    id: 'traffic_works',
    name: 'Road Works',
    color: '#8e44ad',
    categories: ['road_works', 'road_works_major'],
    sources: ['traffic_osm'],
  },
];

// Event sub-layers configuration
const EVENT_SUBLAYERS = [
  {
    id: 'events_concerts',
    name: 'Concerts',
    color: '#1abc9c',
    categories: ['concert'],
  },
  {
    id: 'events_festivals',
    name: 'Festivals',
    color: '#e74c3c',
    categories: ['festival'],
  },
  {
    id: 'events_sports',
    name: 'Sports',
    color: '#3498db',
    categories: ['sports'],
  },
  {
    id: 'events_arts',
    name: 'Arts & Theatre',
    color: '#9b59b6',
    categories: ['arts_theatre'],
  },
  {
    id: 'events_conferences',
    name: 'Conferences',
    color: '#f39c12',
    categories: ['conference'],
  },
  {
    id: 'events_public',
    name: 'Public Events & Holidays',
    color: '#2ecc71',
    categories: ['public_event', 'public_holiday'],
  },
];

function LayerControl({ layers, activeLayers, onToggle, trafficSublayers, onToggleTrafficSublayer, eventSublayers, onToggleEventSublayer }) {
  const [trafficExpanded, setTrafficExpanded] = useState(false);
  const [eventsExpanded, setEventsExpanded] = useState(false);

  // Count events per traffic sublayer
  const sublayerCounts = useMemo(() => {
    if (!trafficSublayers) return {};
    return trafficSublayers.counts || {};
  }, [trafficSublayers]);

  const eventSublayerCounts = useMemo(() => {
    if (!eventSublayers) return {};
    return eventSublayers.counts || {};
  }, [eventSublayers]);

  const isTrafficActive = activeLayers.has('traffic');
  const isEventsActive = activeLayers.has('event');

  return (
    <div className="layer-control">
      <h2>Layers</h2>
      <p className="control-help">Choose what appears on the map and expand groups for detailed filters.</p>
      <div className="layer-list">
        {layers.map((layer) => {
          if (layer.id === 'traffic') {
            // Traffic layer with expandable sub-layers
            return (
              <div key={layer.id} className="layer-group">
                <div className="layer-item-row">
                  <label className="layer-item layer-item-main">
                    <input
                      type="checkbox"
                      checked={activeLayers.has(layer.id)}
                      onChange={() => onToggle(layer.id)}
                    />
                    <span className="layer-color" style={{ backgroundColor: layer.color }} />
                    <span className="layer-name">{layer.name}</span>
                    <span className="layer-count">{layer.event_count}</span>
                  </label>
                  <button
                    className={`sublayer-toggle ${trafficExpanded ? 'expanded' : ''}`}
                    onClick={() => setTrafficExpanded(!trafficExpanded)}
                    title="Show traffic sub-layers"
                    aria-expanded={trafficExpanded}
                    aria-controls="traffic-sublayer-list"
                    aria-label={trafficExpanded ? 'Collapse traffic sub-layers' : 'Expand traffic sub-layers'}
                  >
                    ▸
                  </button>
                </div>

                {trafficExpanded && isTrafficActive && (
                  <div className="sublayer-list" id="traffic-sublayer-list">
                    {TRAFFIC_SUBLAYERS.map((sub) => {
                      const count = sublayerCounts[sub.id] || 0;
                      const isActive = trafficSublayers?.active?.has(sub.id) ?? true;
                      return (
                        <label key={sub.id} className="layer-item sublayer-item">
                          <input
                            type="checkbox"
                            checked={isActive}
                            onChange={() => onToggleTrafficSublayer(sub.id)}
                          />
                          <span className="layer-color sublayer-color" style={{ backgroundColor: sub.color }} />
                          <span className="layer-name">{sub.name}</span>
                          <span className="layer-count">{count}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          if (layer.id === 'event') {
            // Events layer with expandable sub-layers
            return (
              <div key={layer.id} className="layer-group">
                <div className="layer-item-row">
                  <label className="layer-item layer-item-main">
                    <input
                      type="checkbox"
                      checked={activeLayers.has(layer.id)}
                      onChange={() => onToggle(layer.id)}
                    />
                    <span className="layer-color" style={{ backgroundColor: layer.color }} />
                    <span className="layer-name">{layer.name}</span>
                    <span className="layer-count">{layer.event_count}</span>
                  </label>
                  <button
                    className={`sublayer-toggle ${eventsExpanded ? 'expanded' : ''}`}
                    onClick={() => setEventsExpanded(!eventsExpanded)}
                    title="Show event sub-layers"
                    aria-expanded={eventsExpanded}
                    aria-controls="event-sublayer-list"
                    aria-label={eventsExpanded ? 'Collapse event sub-layers' : 'Expand event sub-layers'}
                  >
                    ▸
                  </button>
                </div>

                {eventsExpanded && isEventsActive && (
                  <div className="sublayer-list" id="event-sublayer-list">
                    {EVENT_SUBLAYERS.map((sub) => {
                      const count = eventSublayerCounts[sub.id] || 0;
                      const isActive = eventSublayers?.active?.has(sub.id) ?? true;
                      return (
                        <label key={sub.id} className="layer-item sublayer-item">
                          <input
                            type="checkbox"
                            checked={isActive}
                            onChange={() => onToggleEventSublayer(sub.id)}
                          />
                          <span className="layer-color sublayer-color" style={{ backgroundColor: sub.color }} />
                          <span className="layer-name">{sub.name}</span>
                          <span className="layer-count">{count}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }

          return (
            <label key={layer.id} className="layer-item">
              <input
                type="checkbox"
                checked={activeLayers.has(layer.id)}
                onChange={() => onToggle(layer.id)}
              />
              <span className="layer-color" style={{ backgroundColor: layer.color }} />
              <span className="layer-name">{layer.name}</span>
              <span className="layer-count">{layer.event_count}</span>
            </label>
          );
        })}
        {layers.length === 0 && (
          <p className="no-data">Loading layers...</p>
        )}
      </div>
    </div>
  );
}

export { TRAFFIC_SUBLAYERS, EVENT_SUBLAYERS };
export default LayerControl;
