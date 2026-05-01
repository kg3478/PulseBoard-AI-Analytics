# Product Decision Journal: PulseBoard

This journal documents the critical technical and product decisions made during the development of PulseBoard. As an AI Product Manager, every technical choice was evaluated through the lens of user value, time-to-market, and the North Star Metric (**Time-to-First-Insight**).

---

## Decision 1: Query Execution Engine
### 🥊 The Contenders: PostgreSQL vs. DuckDB

- **Option A (PostgreSQL):** Industry standard. Requires dynamic table creation, ETL, and a hosted Postgres instance.
- **Option B (DuckDB):** In-process analytical SQL engine designed for fast queries on local files (CSV/Parquet).

### 🏆 The Winner: DuckDB
**The PM Rationale:**
Our North Star Metric is *Time-to-First-Insight*. DuckDB executes SQL *directly* against the uploaded CSV in memory with zero setup. It is stateless, blazing fast, and perfectly aligns with our goal of "under 4 minutes to insight." No cloud infrastructure cost.

---

## Decision 2: LLM Selection for NL-to-SQL
### 🥊 The Contenders: OpenAI GPT-4 vs. Gemini 1.5 Flash vs. Groq + LLaMA 3.3

- **Option A (GPT-4o):** Most capable, but expensive and slow.
- **Option B (Gemini 1.5 Flash):** Initially selected. Deprecated without backward compatibility — caused production 404s.
- **Option C (Groq + LLaMA 3.3 70B):** Fast, free tier. Chosen post-Gemini incident.

### 🏆 The Winner: Groq API + LLaMA 3.3 70B Versatile
**The PM Rationale:**
After the Gemini deprecation incident, Groq was adopted for its stability and speed (~0.8s SQL generation). The self-correction retry loop architecture proved resilient. Groq served as the production NL-to-SQL engine for V1.

---

## Decision 3: Remove All LLM APIs → Fully Local Deterministic Engine *(V2 Decision)*
### 🥊 The Contenders: Keep Groq vs. Local Rule-Based Engine

- **Option A (Keep Groq):** Continue using LLM. Reliable but has rate limits, API costs, latency variability, and deployment fragility.
- **Option B (Local Rule-Based Engine):** Build a deterministic NL→SQL parser using keyword scoring + SQL templates. Zero API calls.

### 🏆 The Winner: Local Deterministic Engine
**The PM Rationale:**
The core issue with LLM-based NL-to-SQL is **reliability at scale**: rate limits hit unexpectedly, free tiers run out, and latency is non-deterministic. For a deployment on Render free-tier (which cold-starts), every millisecond matters.

The local engine delivers:
1. **Reliability:** Deterministic — same input always produces same output
2. **Speed:** <100ms parse time vs ~800ms for LLM inference
3. **Cost:** Zero API costs — fully deployable on free-tier (Vercel + Render)
4. **Privacy:** User data never leaves the server

**Trade-off accepted:** The local engine handles ~80% of real-world analytics queries well. For the remaining 20% (highly complex joins, multi-hop reasoning), it falls back gracefully with schema-aware suggestions rather than silently producing wrong SQL.

---

## Decision 4: Anomaly Detection Methodology
### 🥊 The Contenders: ML (Isolation Forest) vs. Statistical (Z-Score)

**The Winner: Statistical Z-Score**
"Don't use ML when Math will do." Z-score is deterministic, explainable, and executes in milliseconds via NumPy. Zero training time. Founders trust explicit thresholds ("2.4 standard deviations above average") far more than black-box ML flags.

---

## Decision 5: User Interface Paradigm
### 🥊 The Contenders: Dashboard Builder vs. NL Search Bar

**The Winner: Pure NL Search**
Restricting the UI to a search bar removes analyst-mode thinking. The system takes on visualization selection burden. This differentiates PulseBoard from every traditional BI tool.

---

## Decision 6: Frontend Session State Management

**The Winner: useRef + sessionStorage**
React's `useState` updates are asynchronous. Writing session to a `useRef` synchronously before `setSession` prevents the redirect race condition on "Start Analyzing." `sessionStorage` adds reload resilience.

---

## Decision 7: Minimal File Structure for PM Analytics Layer *(V2 Decision)*
### 🥊 The Contenders: Sub-Package vs. Single File

- **Option A (Sub-Package):** Create `backend/pm_engine/` with `funnel.py`, `cohort.py`, `metrics.py`, `detector.py` etc.
- **Option B (Single File):** Consolidate all PM analytics into `backend/services/pm_analytics.py`.

### 🏆 The Winner: Single File (`pm_analytics.py`)
**The PM Rationale:**
The PM analytics functions share state (column detection helpers, hint sets) and are always used together. Splitting them into a sub-package would add import overhead, navigation complexity, and create temptation to over-engineer.

**Rule applied:** "Don't create structure for structure's sake." 250 lines in one well-organized file is better than 5 files of 50 lines that require cross-file navigation to understand a single workflow.

---

## Decision 8: PM Template Routing via Sentinel Pattern *(V2 Decision)*
### 🥊 The Contenders: Separate Parser vs. Sentinel in Existing Templates

- **Option A (Separate Parser):** Build a parallel PM intent parser that runs before the SQL parser.
- **Option B (Sentinel in Templates):** Add PM templates to the existing `TEMPLATES` list with `sql_pattern='__PM_ENGINE__'`. Parser detects the sentinel and returns a `pm_query=True` flag.

### 🏆 The Winner: Sentinel Pattern
**The PM Rationale:**
The sentinel approach reuses the existing template scoring system — PM and SQL templates compete on the same scoring function. This means PM templates naturally win when the user asks a PM question ("funnel", "retention") and SQL templates win for SQL questions ("revenue by city"). Zero code duplication.

The alternative (separate parser) would require maintaining two independent keyword-scoring systems that could drift out of sync.

---

## Decision 9: Context-Aware Intelligence Without ML *(V2 Decision)*

The system detects dataset type (product_analytics / financial / marketing / generic) using **column name intersection** with curated hint sets — no ML models, no embeddings, no API calls. This is:
- **Instant:** Pure set intersection, O(n) where n = number of columns
- **Transparent:** Developers can read and extend the hint sets directly
- **Reliable:** No model drift, no retraining required

Trade-off: Cannot detect dataset type from *data values* (e.g., a financial dataset where all columns are named `col_1`, `col_2`). This edge case is handled by defaulting to `generic` with standard query suggestions.
