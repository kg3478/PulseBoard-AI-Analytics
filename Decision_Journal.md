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
### 🥊 The Contenders: OpenAI GPT-4 vs. Google Gemini 1.5 Flash vs. Groq + LLaMA 3.3

- **Option A (GPT-4o):** The most capable model for coding and SQL generation. High accuracy, but expensive and relatively slow.
- **Option B (Gemini 1.5 Flash):** Google's lightweight, high-speed model with a massive context window. Initially selected for its free tier and speed.
- **Option C (Groq API + LLaMA 3.3 70B):** Groq's proprietary LPU hardware delivers the fastest LLM inference available (~300 tokens/second). Open-weight model, no vendor lock-in, free tier available.

### 🏆 The Winner: Groq API + LLaMA 3.3 70B Versatile
**The PM Rationale:**
PulseBoard initially launched with Gemini 1.5 Flash. However, Google deprecated the `gemini-1.5-flash` and `gemini-1.5-pro` models from the v1beta API without backward compatibility, causing 404 errors in production and breaking the core Ask query feature entirely.

**This was a critical production incident that informed a key PM decision: avoid API vendor lock-in for mission-critical inference paths.**

The migration to Groq delivered three compounding benefits:
1. **Reliability:** Groq maintains stable model availability with clear deprecation timelines.
2. **Speed:** LLaMA 3.3 70B on Groq's LPU hardware produces SQL in ~0.8 seconds — faster than Gemini Flash.
3. **Cost:** Free tier covers all demo and portfolio traffic with generous rate limits.

The self-correction retry loop architecture (if SQL fails, feed error back to LLM) was preserved unchanged, proving the value of decoupling business logic from the AI provider — a key resilience pattern.

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

---

## Decision 5: Frontend Session State Management
### 🥊 The Contenders: URL State vs. React Context vs. useRef + sessionStorage

- **Option A (URL params):** Encode session_id in the URL. Simple but exposes implementation details and breaks on browser navigation.
- **Option B (React Context):** Global state provider. Elegant but requires re-renders and suffers the same race condition as useState.
- **Option C (useRef + sessionStorage):** Synchronous ref write before navigation, with sessionStorage for page reload recovery.

### 🏆 The Winner: useRef + sessionStorage
**The PM Rationale:**
React's `useState` updates are asynchronous — they batch and apply after the current render. When a user clicks "Start Analyzing" immediately after a successful upload, the router guard evaluates `session` state before the async update propagates, causing a redirect loop back to the upload page.

The fix: write the session to a `useRef` **synchronously** before calling `setSession`, then use that ref in the route guard. The ref is always current, regardless of render cycle. `sessionStorage` adds resilience for page refreshes. This pattern — synchronous ref + async state — is a production-grade React session management technique that demonstrates deep understanding of the React rendering lifecycle.
