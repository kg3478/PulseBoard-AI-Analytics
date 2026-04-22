# Product Decision Journal: PulseBoard

This journal documents the critical technical and product decisions made during the development of PulseBoard. As an AI Product Manager, every technical choice was evaluated through the lens of user value, time-to-market, and the North Star Metric (**Time-to-First-Insight**).

---

## Decision 1: Query Execution Engine
### 🥊 The Contenders: PostgreSQL vs. DuckDB

- **Option A (PostgreSQL):** The industry standard for relational databases. We would need to parse the user's CSV, dynamically create tables in a hosted Postgres instance, write the data, and then query it.
- **Option B (DuckDB):** An in-process analytical SQL engine designed specifically for fast queries on local files (CSV/Parquet).

### 🏆 The Winner: DuckDB
**The PM Rationale:**
Our North Star Metric is *Time-to-First-Insight*. Forcing a non-technical founder to wait for a backend ETL process to load their 50MB Stripe export into a Postgres database introduces friction, latency, and massive backend infrastructure costs. 

DuckDB allows us to execute SQL *directly* against the uploaded CSV in memory with zero setup. It is blazing fast and completely stateless, which drastically simplifies our MVP architecture and keeps cloud costs near zero. It perfectly aligns with our goal of "under 4 minutes to insight."

---

## Decision 2: LLM Selection for NL-to-SQL
### 🥊 The Contenders: OpenAI GPT-4 vs. Google Gemini 1.5 Flash

- **Option A (GPT-4o):** The most capable model on the market for coding and SQL generation. High accuracy, but expensive and relatively slow.
- **Option B (Gemini 1.5 Flash):** Google's lightweight, high-speed model with a massive context window. Highly cost-effective (free tier available).

### 🏆 The Winner: Gemini 1.5 Flash
**The PM Rationale:**
While GPT-4 might offer slightly higher out-of-the-box accuracy on complex JOINs, PulseBoard's target persona (startup founders) is asking relatively simple aggregation questions on single-table CSVs ("What is MRR by city?"). 

In analytics products, **latency is UX**. Users will not wait 15 seconds for a chart to load. Gemini 1.5 Flash returns the SQL in under 2 seconds. Furthermore, its massive context window allows us to inject the *entire dataset schema* and numerous few-shot examples into the prompt without blowing up the API budget. To mitigate any accuracy drop-off vs GPT-4, I designed a **Self-Correction Retry Loop**: if DuckDB throws a SQL syntax error, the backend feeds the error back to Gemini to fix it before the user ever sees it. This architectural choice gave us GPT-4 level reliability at Flash level speed and cost.

---

## Decision 3: Anomaly Detection Methodology
### 🥊 The Contenders: Machine Learning (Isolation Forest) vs. Statistical (Z-Score)

- **Option A (Isolation Forest / Autoencoders):** Advanced ML models that can detect non-linear, multi-dimensional anomalies. Requires training data and compute overhead.
- **Option B (Z-Score):** A simple statistical formula measuring how many standard deviations a data point is from the historical mean.

### 🏆 The Winner: Statistical Z-Score
**The PM Rationale:**
"Don't use ML when Math will do." 
Founders don't trust black-box AI models that flag anomalies without explanation. Z-score is mathematically deterministic and highly explainable. We can explicitly tell the user: *"Your refund rate is 2.4 standard deviations above your 30-day average."* 

Furthermore, training an ML model on a user's uploaded 90-day CSV is computationally expensive and overkill. Z-score requires zero training time, executes in milliseconds via NumPy, and immediately solves the user's pain point of "tell me if something breaks."

---

## Decision 4: User Interface Paradigm
### 🥊 The Contenders: Dashboard Builder (Tableau-lite) vs. Pure NL Search (Google-style)

- **Option A (Dashboard Builder):** A UI where users drag and drop X and Y axes, select chart types from dropdowns, and build persistent dashboard views.
- **Option B (Pure NL Search):** A single prominent search bar where users type questions and the system auto-renders the optimal chart.

### 🏆 The Winner: Pure NL Search
**The PM Rationale:**
We are explicitly building an "Anti-BI Tool." If we provide a drag-and-drop dashboard builder, we are forcing the founder to act as an analyst. They don't want to choose between a Bar chart and a Scatter plot—they just want to know why CAC is up.

By restricting the UI to a search bar and 10 pre-built metric templates, we remove cognitive load. The system takes on the burden of choosing the visualization (via the `Chart.jsx` auto-selection logic). This deliberate constraint ensures the product remains simple enough for our target persona, differentiating us entirely from traditional BI competitors.
