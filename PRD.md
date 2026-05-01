# Product Requirements Document (PRD): PulseBoard

## 1. Meta
- **Product Name:** PulseBoard
- **Target Audience:** Product Managers, non-technical founders, and growth teams at early-stage SaaS, eCommerce, and D2C startups (0–50 person teams).
- **Core Value Proposition:** Ask questions of your data in plain English. Get PM-grade analytics, deep EDA, and AI insights in seconds. Hybrid engine means maximum speed and privacy.
- **Status:** V3 (Universal Hybrid AI Platform) Complete

---

## 2. Problem Space
Early-stage founders and PMs possess rich product data but lack the technical skills or tools to extract insights without engineering help.
- **Pain Point 1:** Founders spend hours in spreadsheets manually calculating MRR and Churn instead of talking to customers or building product.
- **Pain Point 2:** PMs can't run funnel or cohort analysis without waiting for a data team.
- **Pain Point 3:** Datasets are often messy or ambiguous, rendering rigid rule-based systems useless.
- **Existing Solutions Fail:** Tools like Tableau, Looker, Mixpanel require data engineering pipelines, SDK instrumentation, or SQL proficiency. They are built for analysts, not PMs.
- **The Core Insight:** Users don't want a "Business Intelligence Dashboard." They want an *answer to a specific question* — and they want it now, regardless of how messy their data is.

---

## 3. Target Personas

### "The Hustling Founder"
- 25-40, Business/Marketing/Domain-expert background
- Can write Excel formulas but not `JOIN` statements
- Data Stack: CSV exports, Google Sheets, Airtable

### "The Early-Stage PM / Growth Marketer"
- Responsible for product analytics or campaign performance without a data team
- Needs funnel analysis, retention metrics, and correlation heatmaps
- Currently uses Mixpanel/Amplitude free tiers (limited) or does it manually in Sheets

---

## 4. Success Metrics (KPIs)

| Metric | Definition | Target |
|---|---|---|
| **North Star: Time-to-First-Insight** | Minutes from upload to first successful chart | **< 4 minutes** |
| **Activation Rate** | % users who run first query within 10 min | > 70% |
| **Query Resolution Rate** | % of queries successfully answered (Rules + LLM) | > 95% |
| **LLM Fallback Efficiency** | % of total queries routed to LLM (cost control) | < 20% |
| **Week-2 Return Rate** | % activated users who return in week 2 | > 40% |

---

## 5. Core Features & User Stories

### Feature 1: Frictionless Onboarding (Zero-ETL)
- **User Story:** As a PM, I want to drag and drop a CSV file so I can start analyzing immediately.
- **Requirement:** Auto-detect schema (Date, Numeric, Text) and compute null%, unique counts, and value ranges instantly.

### Feature 2: Hybrid NL Query Interface *(new in V3)*
- **User Story:** As a founder, I want to ask anything — even vague questions — and get an answer.
- **Requirement:** A smart router sends queries first to a deterministic rule-based engine (<100ms). If confidence is 0 or the schema is highly ambiguous, it falls back to Gemini 2.0 Flash to write SQL or provide a natural-language explanation.

### Feature 3: Local Exploratory Data Analysis (EDA) Suite *(new in V3)*
- **User Story:** As a marketer, I want to understand my dataset quality and correlations before asking specific questions.
- **Requirement:** A zero-API local engine that computes column profiles, missing values, outliers (Z-score), and Pearson correlation matrices on upload.

### Feature 4: Auto-Charting
- **User Story:** As a founder, I don't want to configure X and Y axes.
- **Requirement:** Auto-select chart type: Line (time-series), Pie, Bar, Funnel, Cohort, Table (fallback).

### Feature 5: Hybrid AI Insights *(new in V3)*
- **User Story:** As a founder, I want a quick summary of my business health every Monday morning.
- **Requirement:** Compute fast deterministic week-over-week deltas. Send a compact statistical summary (never raw data) to Gemini to generate deep, contextual insight bullets.

### Feature 6: PM Analytics Engine
- **User Story:** As a PM, I want to analyze funnels, cohorts, and retention from my event data.
- **Requirements:** Auto-detect dataset types, compute DAU/WAU/MAU, activation rates, step-wise funnels, and retention cohorts locally.

### Feature 7: Root Cause Analysis
- **User Story:** "Why did this happen?" — instant correlation-based explanation.
- **Requirement:** Pearson correlation of target metric vs all numeric columns. Rank top correlates and provide plain-English explanations.

---

## 6. Context-Aware Intelligence
The system automatically adapts to the uploaded dataset:

| Detected Type | Behavior |
|---|---|
| `product_analytics` | Enables funnels, cohorts, DAU/WAU/MAU, activation rate |
| `financial` | Prioritizes revenue/MRR insights, trend analysis |
| `marketing` | Surfaces CTR, conversions, ROAS queries |
| `ecommerce` | Focuses on order volume, products, average order value |
| `hr` | Focuses on headcount, attrition, salary by department |
| `generic` | Defaults to universal EDA patterns (correlations, missing values, summaries) |

---

## 7. Out of Scope (Non-Goals)
- We are **not** building a Data Warehouse. No persistent storage across sessions.
- We are **not** supporting real-time data streaming (e.g., Kafka).
- We are **not** sending raw data to LLMs. Privacy is paramount.

---

## 8. Monetization Strategy
- **Freemium Tier:** 5 free queries per day, local rule-engine only.
- **Pro Tier ($29/mo):** Unlimited queries, PM analytics features, hybrid Gemini LLM fallback (up to 50 LLM calls/session), and root-cause analysis.
- **Team Tier ($79/mo):** Direct integrations with Stripe/Shopify/Mixpanel APIs (Future).
