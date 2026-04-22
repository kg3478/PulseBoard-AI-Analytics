/**
 * api.js — Stateless API client. Backend runs as Vercel serverless functions
 * at /api/* on the same domain — no CORS, no Render, no env vars needed.
 * CSV content is sent with every request instead of using server-side sessions.
 */

async function handleResponse(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.error || `HTTP ${res.status}`);
  return data;
}

/** Upload CSV — returns schema, starter questions, and csv_content for client storage */
export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/upload', { method: 'POST', body: formData });
  return handleResponse(res);
}

/** Run NL query — sends csv_content + schema with every request (stateless) */
export async function runQuery(sessionId, question, csvContent, schema) {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, csv_content: csvContent, schema }),
  });
  return handleResponse(res);
}

/** Get anomaly alerts — sends csv_content */
export async function getAnomalies(sessionId, csvContent) {
  const res = await fetch('/api/anomalies', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_content: csvContent }),
  });
  return handleResponse(res);
}

/** Get AI weekly insight bullets — sends csv_content */
export async function getInsights(sessionId, csvContent) {
  const res = await fetch('/api/insights', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ csv_content: csvContent }),
  });
  return handleResponse(res);
}

/** Root cause analysis for a specific metric */
export async function getRootCause(sessionId, column, csvContent) {
  const res = await fetch('/api/root-cause', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ column, csv_content: csvContent }),
  });
  return handleResponse(res);
}
