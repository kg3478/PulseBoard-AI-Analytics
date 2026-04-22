# PulseBoard — AI Product Manager Portfolio Project

> **"Founders don't need a BI tool. They need answers."**  
> PulseBoard is an AI-powered analytics product that allows non-technical startup founders to query their business data in plain English and receive instant charts, insights, and anomaly alerts. 

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React+Vite-61DAFB?style=flat-square&logo=react)](https://react.dev/)
[![DuckDB](https://img.shields.io/badge/Query-DuckDB-FFF000?style=flat-square)](https://duckdb.org/)
[![Gemini](https://img.shields.io/badge/AI-Gemini%20API-4285F4?style=flat-square&logo=google)](https://aistudio.google.com/)

---

## 🧠 The AI Product Manager's Lens

This project was built to demonstrate end-to-end product execution—from zero-to-one user research to full-stack deployment. It highlights the intersection of **strategic product management** and **technical AI engineering**.

### The Problem
Early-stage founders spend 3+ hours per week manually pulling data from Stripe, GA, and spreadsheets to answer basic business questions. Existing BI tools (Tableau, Looker) require data engineering and SQL knowledge—a massive barrier for a 5-person startup. 

### The Solution
PulseBoard reduces the **Time-to-First-Insight from 45 minutes to under 4 minutes**. By leveraging LLM-based NL-to-SQL translation and zero-setup local execution (DuckDB), a non-technical founder can drag-and-drop a CSV and ask questions in plain English instantly.

### Core Product KPIs
- **North Star Metric:** Time-to-First-Insight (< 4 mins)
- **AI Quality Metric:** NL Query Success Rate (> 80%)
- **Activation Rate:** First successful query within 10 minutes of upload.

*See the full [Product Requirements Document (PRD)](PRD.md) and the [Product Decision Journal](Decision_Journal.md) for deeper PM insights.*

---

## 💻 The Full-Stack Engineer's Lens

Built as a lightweight, highly-performant web application showcasing clean architecture, modern React patterns, and robust Python API design.

### Tech Stack & Rationale
| Layer | Technology | Engineering Rationale |
|---|---|---|
| **Frontend** | React + Vite + TailwindCSS | Fast iteration, strict component separation, minimal bundle size. |
| **Data Viz** | Recharts | Composable React components with robust auto-scaling. |
| **Backend** | FastAPI (Python) | Async-first, automatic OpenAPI docs, optimal for LLM/data pipelines. |
| **NL Engine** | Gemini 1.5 Flash | High speed, massive context window (for schema injection), cost-effective. |
| **Execution** | DuckDB | In-process analytical SQL engine. Eliminates the need for a dedicated PostgreSQL server for CSV queries. |
| **Math** | NumPy | Used for Z-score anomaly detection. Chosen over SciPy for better cross-platform wheel compatibility. |

### Architecture
```text
PulseBoard/
├── backend/                          # FastAPI API
│   ├── main.py                       # Routing & Session Management
│   ├── services/
│   │   ├── nl_to_sql.py              # LLM Translation & Self-Correction Retry Loop
│   │   ├── query_engine.py           # DuckDB In-Memory Execution
│   │   ├── anomaly.py                # NumPy Z-Score Detection
│   │   └── insights.py              # LLM Weekly Narrative Generation
│
├── frontend/                         # React UI
│   └── src/
│       ├── App.jsx                   # React Router
│       ├── api.js                    # API Client
│       ├── pages/                    # Upload, Dashboard, Insights
│       └── components/               # Chart, AnomalyCard, TemplateBar
```

---

## ⚡ Features

1. **Zero-Setup Data Ingestion:** Drag-and-drop CSV upload with auto-schema detection (identifies dates, metrics, and categories).
2. **NL-to-SQL Engine:** Ask "Show me revenue by city last month". The LLM writes DuckDB-flavored SQL and executes it securely.
3. **Self-Healing Queries:** If the LLM hallucinates bad SQL, the backend catches the DuckDB error and feeds it back to the LLM for an automatic 2nd-attempt correction.
4. **Auto-Charting:** The system infers the best chart type (Bar, Line, Pie, or Table) based on the SQL output dimensions.
5. **Statistical Anomaly Alerts:** A 30-day rolling Z-score algorithm detects critical spikes and drops without requiring expensive ML model training.
6. **AI Narrative Insights:** Translates week-over-week metric deltas into 3-5 actionable bullet points for the founder.

---

## 🚀 Quick Start Guide

### 1. Setup Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Add your API Key:** Get a free key from [Google AI Studio](https://aistudio.google.com/).
```bash
# In backend/.env
GEMINI_API_KEY=your_key_here
```

**Run API:**
```bash
uvicorn main:app --reload --port 8000
```

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```

App runs at: `http://localhost:5173`

---

## 📊 Demo Data

Use the included `sample_startup_data.csv` to demo PulseBoard. It contains **90 days** of realistic startup metrics with injected anomalies (e.g., a massive revenue spike on day 65) specifically designed to test the Z-score detection system.
