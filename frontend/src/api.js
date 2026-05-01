/**
 * api.js — PulseBoard API client.
 * v3.0: Added getEDA() and getLLMInsights() for hybrid intelligence features.
 */
const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function fetchWithTimeout(url, options = {}, ms = 55000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal });
    clearTimeout(id);
    return res;
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') throw new Error('Backend is warming up (Render free tier). Please wait 30s and try again.');
    throw new Error('Cannot connect to backend. Make sure VITE_API_URL is set and the backend is running.');
  }
}

async function handleResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  return data;
}

export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetchWithTimeout(`${BASE_URL}/upload`, { method: 'POST', body: formData });
  return handleResponse(res);
}

export async function runQuery(sessionId, question) {
  const res = await fetchWithTimeout(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
  return handleResponse(res);
}

export async function getAnomalies(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/anomalies/${sessionId}`);
  return handleResponse(res);
}

export async function getInsights(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/insights/${sessionId}`);
  return handleResponse(res);
}

export async function getRootCause(sessionId, column, chartContext = '') {
  const res = await fetchWithTimeout(`${BASE_URL}/root-cause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, column, chart_context: chartContext }),
  });
  return handleResponse(res);
}

/** Full EDA profile: column stats, correlations, distributions, missing, outliers. */
export async function getEDA(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/eda/${sessionId}`);
  return handleResponse(res);
}

/** On-demand LLM insight bullets from a statistical data summary (no raw data sent). */
export async function getLLMInsights(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/llm-insights`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return handleResponse(res);
}
