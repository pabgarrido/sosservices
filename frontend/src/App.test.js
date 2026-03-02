import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import useWebSocket from './hooks/useWebSocket';
import {
  fetchEvents,
  fetchAlerts,
  fetchLayers,
  fetchStatus,
  fetchHazardScores,
  fetchRiskZones,
  fetchAnalyticsSummary,
  fetchTimeRange,
} from './services/api';

jest.mock('./hooks/useWebSocket');

jest.mock('./services/api', () => ({
  fetchEvents: jest.fn(),
  fetchAlerts: jest.fn(),
  fetchLayers: jest.fn(),
  fetchStatus: jest.fn(),
  fetchHazardScores: jest.fn(),
  fetchRiskZones: jest.fn(),
  fetchAnalyticsSummary: jest.fn(),
  fetchTimeRange: jest.fn(),
}));

jest.mock('./components/HazardMap', () => {
  const ReactLocal = require('react');
  return function MockHazardMap(props) {
    return ReactLocal.createElement('div', { 'data-testid': 'hazard-map' }, `map-events:${props.events.length}|map-alerts:${props.alerts.length}`);
  };
});

jest.mock('./components/LayerControl', () => {
  const ReactLocal = require('react');
  const MockLayerControl = function MockLayerControl(props) {
    return ReactLocal.createElement('div', { 'data-testid': 'layer-control' }, `layers:${props.layers.length}`);
  };
  MockLayerControl.TRAFFIC_SUBLAYERS = [];
  MockLayerControl.EVENT_SUBLAYERS = [];
  return {
    __esModule: true,
    default: MockLayerControl,
    TRAFFIC_SUBLAYERS: [],
    EVENT_SUBLAYERS: [],
  };
});

jest.mock('./components/AlertPanel', () => {
  const ReactLocal = require('react');
  return function MockAlertPanel(props) {
    return ReactLocal.createElement('div', { 'data-testid': 'alert-panel' }, `alerts:${props.alerts.length}`);
  };
});

jest.mock('./components/AnalyticsPanel', () => {
  const ReactLocal = require('react');
  return function MockAnalyticsPanel() {
    return ReactLocal.createElement('div', { 'data-testid': 'analytics-panel' }, 'analytics');
  };
});

jest.mock('./components/TimeSlider', () => {
  const ReactLocal = require('react');
  return function MockTimeSlider() {
    return ReactLocal.createElement('div', { 'data-testid': 'time-slider' }, 'time-slider');
  };
});

jest.mock('./components/StatusBar', () => {
  const ReactLocal = require('react');
  return function MockStatusBar(props) {
    return ReactLocal.createElement('div', { 'data-testid': 'status-bar' }, `status:${props.status.length}|events:${props.eventCount}|alerts:${props.alertCount}`);
  };
});

describe('App', () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    jest.clearAllMocks();
    useWebSocket.mockReturnValue({ connected: false, send: jest.fn() });

    fetchEvents.mockResolvedValue([
      { id: 'e1', type: 'weather', category: 'rain', source: 'weather_service', start_time: '2026-03-02T08:00:00Z' },
      { id: 'e2', type: 'traffic', category: 'traffic_free', source: 'traffic_flow', start_time: '2026-03-02T09:00:00Z' },
    ]);
    fetchAlerts.mockResolvedValue([{ id: 'a1', severity: 'high' }]);
    fetchLayers.mockResolvedValue([
      { id: 'weather', name: 'Weather', color: '#3498db', event_count: 1 },
      { id: 'traffic', name: 'Traffic', color: '#e67e22', event_count: 1 },
    ]);
    fetchStatus.mockResolvedValue([{ adapter: 'weather_adapter', healthy: true, event_count: 2 }]);
    fetchHazardScores.mockResolvedValue([{ event_id: 'e1', score: 72 }]);
    fetchRiskZones.mockResolvedValue([{ id: 'z1' }]);
    fetchAnalyticsSummary.mockResolvedValue({ overall_score: 72, overall_risk: 'moderate' });
    fetchTimeRange.mockResolvedValue({ start: '2026-03-02T00:00:00Z', end: '2026-03-02T23:59:59Z' });

    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  test('loads initial data and updates UI counters', async () => {
    await act(async () => {
      root.render(<App />);
    });

    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchEvents).toHaveBeenCalled();
    expect(fetchAlerts).toHaveBeenCalled();
    expect(fetchLayers).toHaveBeenCalled();
    expect(fetchStatus).toHaveBeenCalled();
    expect(fetchHazardScores).toHaveBeenCalled();
    expect(fetchRiskZones).toHaveBeenCalled();
    expect(fetchAnalyticsSummary).toHaveBeenCalled();
    expect(fetchTimeRange).toHaveBeenCalled();

    expect(container.textContent).toContain('2 events');
    expect(container.textContent).toContain('1 alerts');
    expect(container.textContent).toContain('Risk: 72');
    expect(container.textContent).toContain('layers:2');
    expect(container.textContent).toContain('alerts:1');
    expect(container.textContent).toContain('status:1|events:2|alerts:1');
    expect(container.textContent).toContain('map-events:2|map-alerts:1');
  });
});
