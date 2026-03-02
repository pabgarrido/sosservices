import React, { useState, useMemo, useCallback } from 'react';

/**
 * TimeSlider — Day/Time picker for navigating current + forecast data.
 *
 * Props:
 *   timeRange  - { min_time, max_time, now, forecast_events, current_events }
 *   value      - current position as ISO string (or null for "live")
 *   onChange   - (isoString | null) => void   — null means "live / now"
 */

const DAY_LABELS = ['Today', 'Tomorrow', '+2d', '+3d', '+4d'];
const HOUR_LABELS = ['00', '03', '06', '09', '12', '15', '18', '21'];

function getDayStart(offset) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  d.setHours(0, 0, 0, 0);
  return d;
}

function formatDayLabel(offset) {
  if (offset < DAY_LABELS.length) return DAY_LABELS[offset];
  return `+${offset}d`;
}

function formatWeekday(offset) {
  const d = getDayStart(offset);
  return d.toLocaleDateString('pt-PT', { weekday: 'short', day: 'numeric', month: 'short' });
}

function TimeSlider({ timeRange, value, onChange }) {
  const now = useMemo(() => new Date(), []);
  const isLive = !value;

  // Derive selected day offset and hour from the current value
  const { selectedDay, selectedHour } = useMemo(() => {
    if (!value) {
      return { selectedDay: 0, selectedHour: now.getHours() };
    }
    const v = new Date(value);
    const todayStart = new Date(now);
    todayStart.setHours(0, 0, 0, 0);
    const dayOffset = Math.round((v.setHours(0, 0, 0, 0) - todayStart.getTime()) / 86400000);
    const hour = new Date(value).getHours();
    return { selectedDay: Math.max(0, dayOffset), selectedHour: hour };
  }, [value, now]);

  // Track hover for day buttons
  const [hoveredDay, setHoveredDay] = useState(null);

  // Number of forecast days available (based on timeRange)
  const maxDays = useMemo(() => {
    if (!timeRange?.max_time) return 5;
    const maxDate = new Date(timeRange.max_time);
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    return Math.min(Math.max(Math.ceil((maxDate - todayStart) / 86400000), 1), 5);
  }, [timeRange]);

  const forecastCount = timeRange?.forecast_events || 0;

  const handleDaySelect = useCallback((dayOffset) => {
    const now = new Date();
    if (dayOffset === 0) {
      // Today — default to current hour
      const d = new Date();
      d.setMinutes(0, 0, 0);
      // If it's basically "now", go live
      if (Math.abs(d.getTime() - now.getTime()) < 3600000) {
        onChange(null);
        return;
      }
      onChange(d.toISOString());
    } else {
      // Future day — default to 12:00
      const d = getDayStart(dayOffset);
      d.setHours(12, 0, 0, 0);
      onChange(d.toISOString());
    }
  }, [onChange]);

  const handleHourChange = useCallback((e) => {
    const hour = parseInt(e.target.value, 10);
    const now = new Date();
    const d = getDayStart(selectedDay);
    d.setHours(hour, 0, 0, 0);

    // If we're on today and within 1h of now, snap to live
    if (selectedDay === 0 && Math.abs(d.getTime() - now.getTime()) < 3600000) {
      onChange(null);
      return;
    }
    onChange(d.toISOString());
  }, [selectedDay, onChange]);

  const handleGoLive = useCallback(() => onChange(null), [onChange]);

  // Hours from now for the info bar
  const hoursFromNow = useMemo(() => {
    if (!value) return 0;
    return Math.round((new Date(value).getTime() - Date.now()) / 3600000);
  }, [value]);

  const isFuture = hoursFromNow > 0;

  // Selected date/time display
  const selectedDateTime = useMemo(() => {
    if (isLive) return 'Real-time';
    const d = new Date(value);
    return d.toLocaleString('pt-PT', {
      weekday: 'long',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  }, [value, isLive]);

  // Current hour marker position (only when viewing today)
  const nowHourPct = useMemo(() => {
    return (now.getHours() / 23) * 100;
  }, [now]);

  return (
    <div className="time-slider">
      {/* Top bar: mode + live button */}
      <div className="time-slider-header">
        <div className="time-slider-label">
          <span className="time-slider-icon">📅</span>
          <span className="time-slider-title">Day / Time</span>
          {forecastCount > 0 && (
            <span className="time-slider-forecast-badge">
              {forecastCount} forecast
            </span>
          )}
        </div>
        <div className="time-slider-position">
          <span className={`time-slider-mode ${isLive ? 'live' : isFuture ? 'future' : 'past'}`}>
            {isLive ? 'LIVE' : selectedDateTime}
          </span>
          {!isLive && (
            <button className="time-slider-reset" onClick={handleGoLive} title="Return to live">
              ● LIVE
            </button>
          )}
        </div>
      </div>

      {/* Day selector row */}
      <div className="time-slider-days">
        {Array.from({ length: maxDays }, (_, i) => {
          const isSelected = !isLive && selectedDay === i;
          const isToday = i === 0;
          return (
            <button
              key={i}
              className={`time-slider-day-btn ${isSelected ? 'selected' : ''} ${isLive && isToday ? 'live-today' : ''}`}
              onClick={() => handleDaySelect(i)}
              onMouseEnter={() => setHoveredDay(i)}
              onMouseLeave={() => setHoveredDay(null)}
              title={formatWeekday(i)}
            >
              <span className="day-name">{formatDayLabel(i)}</span>
              <span className="day-date">
                {hoveredDay === i ? formatWeekday(i) : getDayStart(i).getDate()}
              </span>
              {i > 0 && <span className="day-forecast-dot" title="Forecast" />}
            </button>
          );
        })}
      </div>

      {/* Hour slider (only when not live) */}
      {!isLive && (
        <div className="time-slider-hour-section">
          <div className="time-slider-hour-track">
            <input
              type="range"
              className="time-slider-range"
              min={0}
              max={23}
              step={1}
              value={selectedHour}
              onChange={handleHourChange}
            />
            {/* Now marker — only if viewing today */}
            {selectedDay === 0 && (
              <div
                className="time-slider-now-marker"
                style={{ left: `${Math.min(Math.max(nowHourPct, 2), 98)}%` }}
                title={`Now: ${now.getHours()}:00`}
              >
                ▼
              </div>
            )}
          </div>
          <div className="time-slider-hour-labels">
            {HOUR_LABELS.map((h) => (
              <span key={h} className="hour-label">{h}:00</span>
            ))}
          </div>
        </div>
      )}

      {/* Info bar */}
      {isFuture && (
        <div className="time-slider-forecast-info">
          📊 Forecast +{hoursFromNow}h — confidence-adjusted scores
        </div>
      )}
    </div>
  );
}

export default TimeSlider;
