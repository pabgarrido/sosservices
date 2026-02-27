import React from 'react';

const LEVEL_COLORS = {
  none: '#95a5a6',
  watch: '#f1c40f',
  warning: '#e67e22',
  danger: '#e74c3c',
  extreme: '#8e44ad',
};

const LEVEL_ICONS = {
  none: '○',
  watch: '◐',
  warning: '⚠',
  danger: '⛔',
  extreme: '🔴',
};

function AlertPanel({ alerts, onSelect }) {
  const sortedAlerts = [...alerts].sort((a, b) => {
    const order = { extreme: 4, danger: 3, warning: 2, watch: 1, none: 0 };
    return (order[b.level] || 0) - (order[a.level] || 0);
  });

  return (
    <div className="alert-panel">
      <h2>Hazard Alerts ({alerts.length})</h2>
      <div className="alert-list">
        {sortedAlerts.map((alert) => (
          <div
            key={alert.id}
            className={`alert-item alert-${alert.level}`}
            onClick={() => onSelect(alert)}
            style={{ borderLeftColor: LEVEL_COLORS[alert.level] || '#95a5a6' }}
          >
            <div className="alert-header">
              <span className="alert-icon">{LEVEL_ICONS[alert.level] || '○'}</span>
              <span className="alert-level" style={{ color: LEVEL_COLORS[alert.level] }}>
                {alert.level.toUpperCase()}
              </span>
            </div>
            <h3 className="alert-title">{alert.title}</h3>
            <p className="alert-desc">{alert.description.substring(0, 120)}...</p>
            <div className="alert-footer">
              <span>{alert.contributing_events.length} events</span>
              <span>{alert.radius_km.toFixed(0)} km radius</span>
            </div>
          </div>
        ))}
        {alerts.length === 0 && (
          <div className="no-alerts">
            <p>✅ No hazard alerts active</p>
            <small>The correlation engine is monitoring for compound risks.</small>
          </div>
        )}
      </div>
    </div>
  );
}

export default AlertPanel;
