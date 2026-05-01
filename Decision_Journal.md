# Product Decision Journal: PulseBoard

This journal documents the critical technical and product decisions made during the development of PulseBoard. As an AI Product Manager, every technical choice was evaluated through the lens of user value, time-to-market, and the North Star Metric (**Time-to-First-Insight**).

---

## Decision 1: Query Execution Engine
### 🥊 The Contenders: PostgreSQL vs. DuckDB

**🏆 The Winner: DuckDB**
**The PM Rationale:**
Our North Star Metric is *Time-to-First-Insight*. DuckDB executes SQL *directly* against the uploaded CSV in memory with zero setup. It is stateless, blazing fast, and perfectly aligns with our goal of "under 4 minutes to insight." No cloud infrastructure cost.

---

## Decision 2: LLM Selection for NL-to-SQL
### 🥊 The Contenders: OpenAI GPT-4 vs. Gemini 1.5 Flash vs. Groq + LLaMA 3.3

**🏆 The Winner: Groq API + LLaMA 3.3 70B Versatile** (Initially)
**The PM Rationale:**
After a Gemini deprecation incident early on, Groq was adopted for its stability and speed (~0.8s SQL generation). Groq served as the production NL-to-SQL engine for V1.

---

## Decision 3: The Evolution to Hybrid Intelligence *(V2 & V3 Decisions)*
### 🥊 The Contenders: Pure LLM vs. Pure Local Rules vs. Hybrid (Rules + LLM)

**🏆 The Winner: Hybrid Architecture (V3)**
**The PM Rationale:**
In V2, we removed the LLM entirely because rate limits and latency variability were blocking reliable usage on free-tier hosting (Render). We built a 100% deterministic local rule engine that was blazing fast (<100ms) but struggled with ambiguous "messy" datasets and open-ended queries (e.g., "summarize this data").

In V3, we introduced **Hybrid Intelligence**. 
1. **Rule Engine First:** The local deterministic engine handles 80% of standard analytical queries instantly and for free.
2. **Gemini LLM Fallback:** If the rule engine's confidence hits 0, or an Exploratory Data Analysis (EDA) intent is detected, the query routes to Gemini 2.0 Flash.
This perfectly balances speed, cost, privacy, and universal dataset coverage.

---

## Decision 4: Anomaly Detection Methodology
### 🥊 The Contenders: ML (Isolation Forest) vs. Statistical (Z-Score)

**🏆 The Winner: Statistical Z-Score**
"Don't use ML when Math will do." Z-score is deterministic, explainable, and executes in milliseconds via NumPy. Zero training time. Founders trust explicit thresholds ("2.4 standard deviations above average") far more than black-box ML flags.

---

## Decision 5: Local EDA Engine vs LLM Analysis *(V3 Decision)*
### 🥊 The Contenders: Local Pandas Engine vs. LLM Data Passing

**🏆 The Winner: Local Pandas EDA Engine**
**The PM Rationale:**
Passing raw dataset rows to an LLM for exploratory data analysis (correlations, missing values, profiling) is slow, expensive, and a massive privacy risk. We built a local EDA engine in `eda.py` that computes exact Pearson correlations, histograms, and null percentages locally in under a second. The LLM is only fed the aggregated statistical *summary* to generate high-level insight bullets, ensuring raw data never leaves the server.

---

## Decision 6: Frontend Session State Management

**🏆 The Winner: useRef + sessionStorage**
React's `useState` updates are asynchronous. Writing session to a `useRef` synchronously before `setSession` prevents the redirect race condition on "Start Analyzing." `sessionStorage` adds reload resilience.

---

## Decision 7: Minimal File Structure for Analytics Layer
### 🥊 The Contenders: Sub-Package vs. Single File

**🏆 The Winner: Single File (`pm_analytics.py`, `eda.py`)**
**The PM Rationale:**
Analytics functions share state and are used together. Splitting them into deep sub-packages adds import overhead and navigation complexity. "Don't create structure for structure's sake."

---

## Decision 8: Context-Aware Intelligence Without ML *(V2 & V3)*

The system detects dataset type (product, financial, marketing, **ecommerce, hr**, generic) using **column name intersection** with curated hint sets — no ML embeddings needed.
- **Instant:** Pure set intersection.
- **Transparent:** Easy to extend.
- **Universal Adaptation:** If the data is generic or messy, the system automatically pivots from suggesting structured PM metrics to suggesting open-ended EDA queries (e.g., "What are the correlations?").

---

## Decision 9: LLM SDK Upgrade *(V3 Decision)*
### 🥊 The Contenders: google.generativeai vs google.genai

**🏆 The Winner: google.genai**
**The PM Rationale:**
Google deprecated the old `google.generativeai` package. To ensure future compatibility, prompt-caching readiness, and support for the latest Gemini 2.0 Flash models, we migrated to the official `google-genai` SDK during the V3 Hybrid AI transformation.
