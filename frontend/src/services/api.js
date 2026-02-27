/**
 * API client for the SOS Services backend.
 */

export async function fetchEvents(apiUrl) {
  const res = await fetch(`${apiUrl}/api/events`);
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

export async function forceRefresh(apiUrl) {
  const res = await fetch(`${apiUrl}/api/refresh`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to refresh: ${res.status}`);
  return res.json();
}
