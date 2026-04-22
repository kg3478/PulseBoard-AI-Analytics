/**
 * api.js — Centralized API client for PulseBoard backend.
 * All fetch calls go through here. Backend URL is configured via env var.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function handleResponse(res) {
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  }
  return data;
}

/**
 * Upload a CSV file to the backend.
 * @param {File} file
 * @returns {Promise<{session_id, schema, starter_questions, row_count, filename}>}
 */
export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse(res);
}

/**
 * Run a natural language query against the uploaded data.
 * @param {string} sessionId
 * @param {string} question
 * @returns {Promise<{success, sql, result, attempts, question}>}
 */
export async function runQuery(sessionId, question) {
  const res = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
  return handleResponse(res);
}

/**
 * Fetch anomaly alerts for the session.
 * @param {string} sessionId
 * @returns {Promise<{alerts: Array, total: number}>}
 */
export async function getAnomalies(sessionId) {
  const res = await fetch(`${BASE_URL}/anomalies/${sessionId}`);
  return handleResponse(res);
}

/**
 * Fetch LLM-generated weekly insight bullets.
 * @param {string} sessionId
 * @returns {Promise<{bullets: string[], deltas: object}>}
 */
export async function getInsights(sessionId) {
  const res = await fetch(`${BASE_URL}/insights/${sessionId}`);
  return handleResponse(res);
}

/**
 * Run root cause analysis for a specific metric.
 * @param {string} sessionId
 * @param {string} column
 * @param {string} chartContext
 * @returns {Promise<{analysis: string}>}
 */
export async function getRootCause(sessionId, column, chartContext = '') {
  const res = await fetch(`${BASE_URL}/root-cause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, column, chart_context: chartContext }),
  });
  return handleResponse(res);
}
