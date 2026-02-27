import React from 'react';

function LayerControl({ layers, activeLayers, onToggle }) {
  return (
    <div className="layer-control">
      <h2>Layers</h2>
      <div className="layer-list">
        {layers.map((layer) => (
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
        ))}
        {layers.length === 0 && (
          <p className="no-data">Loading layers...</p>
        )}
      </div>
    </div>
  );
}

export default LayerControl;
