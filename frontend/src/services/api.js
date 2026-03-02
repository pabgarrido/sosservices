/**
 * API client for the SOS Services backend.
 */

export async function fetchEvents(apiUrl, { timeStart, timeEnd } = {}) {
  const params = new URLSearchParams();
  if (timeStart) params.set('time_start', timeStart);
  if (timeEnd) params.set('time_end', timeEnd);
  const qs = params.toString();
  const res = await fetch(`${apiUrl}/api/events${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`);
  return res.json();
}

export async function fetchAlerts(apiUrl) {
  const res = await fetch(`${apiUrl}/api/alerts`);
  if (!res.ok) throw new Error(`Failed to fetch alerts: ${res.status}`);
  return res.json();
}

export async function fetchLayers(apiUrl) {
  const res = await fetch(`${apiUrl}/api/layers`);
  if (!res.ok) throw new Error(`Failed to fetch layers: ${res.status}`);
  return res.json();
}

export async function fetchStatus(apiUrl) {
  const res = await fetch(`${apiUrl}/api/status`);
  if (!res.ok) throw new Error(`Failed to fetch status: ${res.status}`);
  return res.json();
}

export async function fetchHazardScores(apiUrl, { minScore, type, level, limit, timeStart, timeEnd } = {}) {
  const params = new URLSearchParams();
  if (minScore != null) params.set('min_score', minScore);
  if (type) params.set('type', type);
  if (level) params.set('level', level);
  if (limit) params.set('limit', limit);
  if (timeStart) params.set('time_start', timeStart);
  if (timeEnd) params.set('time_end', timeEnd);
  const qs = params.toString();
  const res = await fetch(`${apiUrl}/api/hazard-scores${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error(`Failed to fetch hazard scores: ${res.status}`);
  return res.json();
}

export async function fetchRiskZones(apiUrl, { minScore, timeStart, timeEnd } = {}) {
  const params = new URLSearchParams();
  if (minScore != null) params.set('min_score', minScore);
  if (timeStart) params.set('time_start', timeStart);
  if (timeEnd) params.set('time_end', timeEnd);
  const qs = params.toString();
  const res = await fetch(`${apiUrl}/api/risk-zones${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error(`Failed to fetch risk zones: ${res.status}`);
  return res.json();
}

export async function fetchAnalyticsSummary(apiUrl, { timeStart, timeEnd } = {}) {
  const params = new URLSearchParams();
  if (timeStart) params.set('time_start', timeStart);
  if (timeEnd) params.set('time_end', timeEnd);
  const qs = params.toString();
  const res = await fetch(`${apiUrl}/api/analytics/summary${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error(`Failed to fetch analytics summary: ${res.status}`);
  return res.json();
}

export async function fetchTimeRange(apiUrl) {
  const res = await fetch(`${apiUrl}/api/time-range`);
  if (!res.ok) throw new Error(`Failed to fetch time range: ${res.status}`);
  return res.json();
}

export async function forceRefresh(apiUrl) {
  const res = await fetch(`${apiUrl}/api/refresh`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to refresh: ${res.status}`);
  return res.json();
}
