import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import LayerControl from './LayerControl';

describe('LayerControl', () => {
  let container;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
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

  test('calls toggle handlers for main layers and sublayers', () => {
    const onToggle = jest.fn();
    const onToggleTrafficSublayer = jest.fn();
    const onToggleEventSublayer = jest.fn();

    const layers = [
      { id: 'weather', name: 'Weather', color: '#3498db', event_count: 10 },
      { id: 'traffic', name: 'Traffic', color: '#e67e22', event_count: 6 },
      { id: 'event', name: 'Events', color: '#9b59b6', event_count: 4 },
    ];

    const trafficSublayers = {
      active: new Set(['traffic_flow_free']),
      counts: { traffic_flow_free: 3 },
    };

    const eventSublayers = {
      active: new Set(['events_concerts']),
      counts: { events_concerts: 2 },
    };

    act(() => {
      root.render(
        <LayerControl
          layers={layers}
          activeLayers={new Set(['weather', 'traffic', 'event'])}
          onToggle={onToggle}
          trafficSublayers={trafficSublayers}
          onToggleTrafficSublayer={onToggleTrafficSublayer}
          eventSublayers={eventSublayers}
          onToggleEventSublayer={onToggleEventSublayer}
        />
      );
    });

    const weatherCheckbox = Array.from(container.querySelectorAll('label.layer-item input[type="checkbox"]')).find(
      (input) => input.closest('label')?.textContent?.includes('Weather')
    );

    act(() => {
      weatherCheckbox.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onToggle).toHaveBeenCalledWith('weather');

    const trafficExpandButton = container.querySelector('button[title="Show traffic sub-layers"]');
    act(() => {
      trafficExpandButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    const freeFlowCheckbox = Array.from(container.querySelectorAll('label.sublayer-item input[type="checkbox"]')).find(
      (input) => input.closest('label')?.textContent?.includes('Free Flow')
    );

    act(() => {
      freeFlowCheckbox.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onToggleTrafficSublayer).toHaveBeenCalledWith('traffic_flow_free');

    const eventsExpandButton = container.querySelector('button[title="Show event sub-layers"]');
    act(() => {
      eventsExpandButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    const concertsCheckbox = Array.from(container.querySelectorAll('label.sublayer-item input[type="checkbox"]')).find(
      (input) => input.closest('label')?.textContent?.includes('Concerts')
    );

    act(() => {
      concertsCheckbox.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(onToggleEventSublayer).toHaveBeenCalledWith('events_concerts');
  });
});
