import React from 'react';

function StatusBar({ status, eventCount, alertCount }) {
  const healthyCount = status.filter((s) => s.healthy).length;
  const totalCount = status.length;

  return (
    <footer className="status-bar">
      <div className="status-left">
        <span className="status-adapters">
          Adapters: {healthyCount}/{totalCount} healthy
        </span>
        {status.map((s) => (
          <span
            key={s.adapter}
            className={`status-dot ${s.healthy ? 'healthy' : 'unhealthy'}`}
            title={`${s.adapter}: ${s.healthy ? 'OK' : s.error || 'Error'} (${s.event_count} events)`}
          >
            {s.adapter.replace('_', ' ')}
          </span>
        ))}
      </div>
      <div className="status-right">
        <span>{eventCount} events tracked</span>
        <span>{alertCount} active alerts</span>
        <span>{new Date().toLocaleTimeString('pt-PT')}</span>
      </div>
    </footer>
  );
}

export default StatusBar;
