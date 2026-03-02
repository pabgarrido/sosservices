import React, { useState, useMemo } from 'react';

const LEVEL_COLORS = {
  none: '#95a5a6',
  watch: '#f1c40f',
  warning: '#e67e22',
  danger: '#e74c3c',
  extreme: '#8e44ad',
};

const LEVEL_LABELS = {
  none: 'NONE',
  watch: 'WATCH',
  warning: 'WARNING',
  danger: 'DANGER',
  extreme: 'EXTREME',
};

const TYPE_ICONS = {
  weather: '🌦',
  emergency: '🚨',
  traffic: '🚗',
  event: '📅',
};

function ScoreBar({ score, size = 'normal' }) {
  const color =
    score >= 80 ? '#8e44ad' :
    score >= 60 ? '#e74c3c' :
    score >= 40 ? '#e67e22' :
    score >= 20 ? '#f1c40f' : '#2ecc71';

  const height = size === 'large' ? 10 : 6;

  return (
    <div className="score-bar-container" style={{ height }}>
      <div
        className="score-bar-fill"
        style={{
          width: `${Math.min(score, 100)}%`,
          backgroundColor: color,
          height: '100%',
        }}
      />
    </div>
  );
}

function formatLocation(loc) {
  if (!loc) return '';
  return `${loc.lat.toFixed(2)}°N, ${Math.abs(loc.lng).toFixed(2)}°W`;
}

function AnalyticsPanel({ summary, hazardScores, onLocateEvent }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [expandedHazard, setExpandedHazard] = useState(null);

  // Top hazards from summary
  const topHazards = summary?.top_hazards || [];
  const crossDomain = summary?.cross_domain_alerts || [];
  const byLevel = summary?.by_level || {};
  const byType = summary?.by_type || {};
  const overallScore = summary?.overall_score || 0;
  const overallRisk = summary?.overall_risk || 'none';
  const totalEvents = summary?.total_events || 0;

  // Level distribution for mini chart
  const levelDistribution = useMemo(() => {
    const levels = ['extreme', 'danger', 'warning', 'watch', 'none'];
    return levels.map((l) => ({
      level: l,
      count: byLevel[l] || 0,
      color: LEVEL_COLORS[l],
      label: LEVEL_LABELS[l],
    }));
  }, [byLevel]);

  const handleLocate = (hazard) => {
    if (onLocateEvent && hazard.location) {
      onLocateEvent(hazard.location, hazard.event_id);
    }
  };

  const handleCardKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  return (
    <div className="analytics-panel">
      <h2>Predictive Analytics</h2>

      {/* Overall Risk Gauge */}
      <div className="analytics-gauge">
        <div className="gauge-score" style={{ color: LEVEL_COLORS[overallRisk] }}>
          {overallScore.toFixed(0)}
        </div>
        <div className="gauge-label">
          <span
            className="gauge-level"
            style={{
              color: LEVEL_COLORS[overallRisk],
              borderColor: LEVEL_COLORS[overallRisk],
            }}
          >
            {LEVEL_LABELS[overallRisk]}
          </span>
          <span className="gauge-sub">{totalEvents} events analyzed</span>
        </div>
        <ScoreBar score={overallScore} size="large" />
      </div>

      {/* Tab navigation */}
      <div className="analytics-tabs" role="tablist" aria-label="Analytics views">
        <button
          className={`analytics-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
          role="tab"
          aria-selected={activeTab === 'overview'}
          aria-controls="analytics-overview"
        >
          Overview
        </button>
        <button
          className={`analytics-tab ${activeTab === 'hazards' ? 'active' : ''}`}
          onClick={() => setActiveTab('hazards')}
          role="tab"
          aria-selected={activeTab === 'hazards'}
          aria-controls="analytics-hazards"
        >
          Top Hazards
        </button>
        <button
          className={`analytics-tab ${activeTab === 'cross' ? 'active' : ''}`}
          onClick={() => setActiveTab('cross')}
          role="tab"
          aria-selected={activeTab === 'cross'}
          aria-controls="analytics-cross"
        >
          Cross-Domain
        </button>
      </div>

      {/* Tab content */}
      <div className="analytics-content">
        {activeTab === 'overview' && (
          <div className="analytics-overview" id="analytics-overview" role="tabpanel">
            {totalEvents === 0 && (
              <p className="no-data">No analytics yet. Keep the app live for a moment while events are collected.</p>
            )}
            {/* Level distribution */}
            <div className="level-distribution">
              <h4>Risk Distribution</h4>
              {levelDistribution.map((l) => (
                <div key={l.level} className="level-row">
                  <span
                    className="level-dot"
                    style={{ backgroundColor: l.color }}
                  />
                  <span className="level-name">{l.label}</span>
                  <span className="level-count">{l.count}</span>
                  <div className="level-bar-bg">
                    <div
                      className="level-bar-fill"
                      style={{
                        width: `${totalEvents > 0 ? (l.count / totalEvents) * 100 : 0}%`,
                        backgroundColor: l.color,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* By type summary */}
            <div className="type-summary">
              <h4>By Category</h4>
              {Object.entries(byType).map(([tp, info]) => (
                <div key={tp} className="type-row">
                  <span className="type-icon">{TYPE_ICONS[tp] || '📌'}</span>
                  <span className="type-name">{tp}</span>
                  <span className="type-count">{info.count}</span>
                  <span className="type-avg">avg {info.avg_score}</span>
                  <span
                    className="type-max"
                    style={{ color: LEVEL_COLORS[info.max_score >= 60 ? 'danger' : info.max_score >= 40 ? 'warning' : 'watch'] }}
                  >
                    max {info.max_score}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'hazards' && (
          <div className="hazards-list" id="analytics-hazards" role="tabpanel">
            {topHazards.length === 0 && (
              <p className="no-data">No top hazards yet. Enable more layers or wait for new events to be scored.</p>
            )}
            {topHazards.map((h, i) => {
              const isExpanded = expandedHazard === h.event_id;
              return (
                <div
                  key={h.event_id}
                  className={`hazard-item ${isExpanded ? 'expanded' : ''}`}
                  style={{ borderLeftColor: LEVEL_COLORS[h.level] }}
                  onClick={() => setExpandedHazard(isExpanded ? null : h.event_id)}
                  onKeyDown={(event) => handleCardKeyDown(event, () => setExpandedHazard(isExpanded ? null : h.event_id))}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isExpanded}
                  aria-label={`Hazard ${h.title} with score ${h.score.toFixed(0)}`}
                >
                  <div className="hazard-header">
                    <span className="hazard-rank">#{i + 1}</span>
                    <span className="hazard-score" style={{ color: LEVEL_COLORS[h.level] }}>
                      {h.score.toFixed(0)}
                    </span>
                    <span className="hazard-level-badge" style={{ backgroundColor: LEVEL_COLORS[h.level] }}>
                      {LEVEL_LABELS[h.level]}
                    </span>
                  </div>
                  <div className="hazard-title">
                    {TYPE_ICONS[h.type] || ''} {h.title}
                  </div>

                  {/* Location + category row — always visible */}
                  <div className="hazard-meta-row">
                    {h.location && (
                      <span className="hazard-location" title={formatLocation(h.location)}>
                        📍 {formatLocation(h.location)}
                      </span>
                    )}
                    {h.category && (
                      <span className="hazard-category">{h.category}</span>
                    )}
                  </div>

                  <ScoreBar score={h.score} />

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="hazard-details">
                      <div className="hazard-detail-grid">
                        {h.source && (
                          <div className="hazard-detail">
                            <span className="detail-label">Source</span>
                            <span className="detail-value">{h.source}</span>
                          </div>
                        )}
                        {h.severity && (
                          <div className="hazard-detail">
                            <span className="detail-label">Severity</span>
                            <span className="detail-value">{h.severity.toUpperCase()}</span>
                          </div>
                        )}
                        {h.type && (
                          <div className="hazard-detail">
                            <span className="detail-label">Type</span>
                            <span className="detail-value">{h.type}</span>
                          </div>
                        )}
                      </div>

                      <div className="hazard-factors">
                        {h.factors.map((f, j) => (
                          <span key={j} className="factor-tag">{f}</span>
                        ))}
                      </div>

                      {h.location && (
                        <button
                          className="hazard-locate-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleLocate(h);
                          }}
                        >
                          🔍 Locate on Map
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {activeTab === 'cross' && (
          <div className="cross-domain-list" id="analytics-cross" role="tabpanel">
            {crossDomain.length === 0 && (
              <p className="no-data">No cross-domain correlations yet. Correlations appear when risks overlap across categories.</p>
            )}
            {crossDomain.map((cd, i) => (
              <div
                key={(cd.event_id || '') + i}
                className="cross-item"
                onClick={() => cd.location && handleLocate(cd)}
                onKeyDown={(event) => cd.location && handleCardKeyDown(event, () => handleLocate(cd))}
                style={{ cursor: cd.location ? 'pointer' : 'default' }}
                role={cd.location ? 'button' : undefined}
                tabIndex={cd.location ? 0 : undefined}
                aria-label={cd.location ? `Locate correlation ${cd.title} on map` : undefined}
              >
                <div className="cross-header">
                  <span className="cross-score" style={{
                    color: cd.score >= 60 ? LEVEL_COLORS.danger : cd.score >= 40 ? LEVEL_COLORS.warning : LEVEL_COLORS.watch
                  }}>
                    {cd.score.toFixed(0)}
                  </span>
                  <span className="cross-amp">+{(cd.amplification * 100).toFixed(0)}% amplified</span>
                  {cd.location && <span className="cross-locate-hint">📍</span>}
                </div>
                <div className="cross-title">{cd.title}</div>
                {cd.category && (
                  <div className="cross-meta">
                    <span className="hazard-category">{cd.category}</span>
                    {cd.location && (
                      <span className="hazard-location">{formatLocation(cd.location)}</span>
                    )}
                  </div>
                )}
                <div className="cross-factors">
                  {cd.factors.map((f, j) => (
                    <span key={j} className="factor-tag cross-factor">{f}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default AnalyticsPanel;
