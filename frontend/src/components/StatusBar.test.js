import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import StatusBar from './StatusBar';

describe('StatusBar', () => {
  test('renders adapter health summary, adapter labels, and counters', () => {
    const status = [
      { adapter: 'weather_adapter', healthy: true, event_count: 12 },
      { adapter: 'traffic_adapter', healthy: false, error: 'Timeout', event_count: 3 },
    ];

    const timeSpy = jest
      .spyOn(Date.prototype, 'toLocaleTimeString')
      .mockReturnValue('10:30:00');

    const html = renderToStaticMarkup(
      <StatusBar status={status} eventCount={15} alertCount={2} />
    );

    expect(html).toContain('Adapters: 1/2 healthy');
    expect(html).toContain('weather adapter');
    expect(html).toContain('traffic adapter');
    expect(html).toContain('15 events tracked');
    expect(html).toContain('2 active alerts');
    expect(html).toContain('10:30:00');
    expect(html).toContain('weather_adapter: OK (12 events)');
    expect(html).toContain('traffic_adapter: Timeout (3 events)');

    timeSpy.mockRestore();
  });
});
