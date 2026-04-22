/**
 * api.js — Centralized API client for PulseBoard backend.
 * All fetch calls go through here. Backend URL is configured via VITE_API_URL env var.
 * Includes a timeout to handle Render free-tier cold starts (up to 50s).
 */

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

// Render free tier can take up to 50s to cold-start — we allow 60s
async function fetchWithTimeout(url, options = {}, timeoutMs = 60000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return res;
  } catch (err) {
    clearTimeout(id);
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. The backend may be cold-starting — please try again in 30 seconds.');
    }
    throw new Error(`Cannot reach backend at ${BASE_URL}. Make sure VITE_API_URL is set correctly on Vercel.`);
  }
}

async function handleResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return data;
}

/**
 * Upload a CSV file to the backend.
 */
export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetchWithTimeout(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse(res);
}

/**
 * Run a natural language query against the uploaded data.
 */
export async function runQuery(sessionId, question) {
  const res = await fetchWithTimeout(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
  return handleResponse(res);
}

/**
 * Fetch anomaly alerts for the session.
 */
export async function getAnomalies(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/anomalies/${sessionId}`);
  return handleResponse(res);
}

/**
 * Fetch LLM-generated weekly insight bullets.
 */
export async function getInsights(sessionId) {
  const res = await fetchWithTimeout(`${BASE_URL}/insights/${sessionId}`);
  return handleResponse(res);
}

/**
 * Run root cause analysis for a specific metric.
 */
export async function getRootCause(sessionId, column, chartContext = '') {
  const res = await fetchWithTimeout(`${BASE_URL}/root-cause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, column, chart_context: chartContext }),
  });
  return handleResponse(res);
}
