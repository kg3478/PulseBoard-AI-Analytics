# Product Requirements Document (PRD): PulseBoard

## 1. Meta
- **Product Name:** PulseBoard
- **Target Audience:** Product Managers, non-technical founders, and growth teams at early-stage SaaS and D2C startups (0–50 person teams).
- **Core Value Proposition:** Ask questions of your data in plain English. Get PM-grade analytics — funnels, cohorts, retention — in seconds. No SQL. No API keys.
- **Status:** V2 (PM Analytics Layer) Complete

---

## 2. Problem Space
Early-stage founders and PMs possess rich product data but lack the technical skills or tools to extract insights without engineering help.
- **Pain Point 1:** Founders spend hours in spreadsheets manually calculating MRR and Churn instead of talking to customers or building product.
- **Pain Point 2:** PMs can't run funnel or cohort analysis without waiting for a data team — or paying $500+/mo for Mixpanel/Amplitude.
- **Existing Solutions Fail:** Tools like Tableau, Looker, Mixpanel require data engineering pipelines, SDK instrumentation, or SQL proficiency. They are built for analysts, not PMs.
- **The Core Insight:** PMs don't want a "Business Intelligence Dashboard." They want an *answer to a specific question* — and they want it now.

---

## 3. Target Personas

### "The Hustling Founder"
- 25-40, Business/Marketing/Domain-expert background
- Can write Excel formulas but not `JOIN` statements
- Data Stack: CSV exports, Google Sheets, Airtable

### "The Early-Stage PM"
- Responsible for product analytics without a data team
- Needs funnel analysis, retention metrics, activation tracking
- Currently uses Mixpanel/Amplitude free tiers (limited) or does it manually in Sheets

---

## 4. Success Metrics (KPIs)

| Metric | Definition | Target |
|---|---|---|
| **North Star: Time-to-First-Insight** | Minutes from upload to first successful chart | **< 4 minutes** |
| **Activation Rate** | % users who run first query within 10 min | > 70% |
| **NL Query Success Rate** | % of NL queries that return results | > 80% |
| **PM Query Success Rate** | % of funnel/cohort queries that execute | > 75% |
| **Week-2 Return Rate** | % activated users who return in week 2 | > 40% |

---

## 5. Core Features & User Stories

### Feature 1: Frictionless Onboarding (Zero-ETL)
- **User Story:** As a PM, I want to drag and drop a CSV file so I can start analyzing immediately.
- **Requirement:** Auto-detect schema (Date, Numeric, Text) and present 5 starter questions. Detect dataset type (product/financial/marketing) and surface relevant PM query suggestions.

### Feature 2: Local NL-to-SQL Query Interface
- **User Story:** As a founder, I want to type "Show me revenue by city" and get a chart instantly.
- **Requirement:** Rule-based NL parser with 8 SQL templates + 4 PM templates. Zero external API calls. Sub-100ms parse time. Graceful fallback with schema-aware suggestions on failure.

### Feature 3: Auto-Charting
- **User Story:** As a founder, I don't want to configure X and Y axes.
- **Requirement:** Auto-select chart type: Line (time-series), Pie (categorical <5 rows), Bar (categorical), Funnel (PM funnel queries), Cohort (retention heatmap), Table (fallback).

### Feature 4: Statistical Anomaly Alerts
- **User Story:** As a founder, I want to be alerted if my refund rate spikes unexpectedly.
- **Requirement:** 30-day rolling Z-score on all numeric columns. Critical alerts if `|z| > 3.0`, Warning if `|z| > 2.0`.

### Feature 5: Deterministic Weekly Insights
- **User Story:** As a founder, I want a quick summary of my business health every Monday morning.
- **Requirement:** Compute week-over-week deltas with pandas and generate 3-5 template-based insight bullets. Tiered logic: dramatic changes (>40%) → spike/crash label; moderate (>5%) → increase/decrease bullet; flat (<5%) → stable.

### Feature 6: PM Analytics Engine *(new in V2)*
- **User Story:** As a PM, I want to analyze funnels, cohorts, and retention from my event data without writing code or paying for Mixpanel.
- **Requirements:**
  - **Dataset Type Detection:** Auto-detect product_analytics / financial / marketing / generic from column names
  - **DAU / WAU / MAU:** Compute from user_id + timestamp columns
  - **Activation Rate:** % of users who reached a key event
  - **Funnel Analysis:** Step-wise conversion with drop-off % for ordered event sequences
  - **Cohort / Retention:** Group users by first activity date, track % retained per period
  - **Context-Aware Suggestions:** Surface PM-specific query suggestions when dataset supports it
  - **Graceful Fallback:** Friendly error messages when required columns are missing

### Feature 7: Root Cause Analysis
- **User Story:** "Why did this happen?" — instant correlation-based explanation.
- **Requirement:** Pearson correlation of target metric vs all numeric columns. Rank top 3 correlates with strength labels (very strong/strong/moderate/weak). Numbered, plain-English output.

---

## 6. Context-Aware Intelligence
The system automatically adapts to the uploaded dataset:

| Detected Type | Behavior |
|---|---|
| `product_analytics` | Enables funnels, cohorts, DAU/WAU/MAU, activation rate |
| `financial` | Prioritizes revenue/MRR insights, trend analysis |
| `marketing` | Surfaces CTR, conversions, ROAS queries |
| `generic` | Standard aggregation templates |

Detection is purely column-name based — no external API required.

---

## 7. Out of Scope (Non-Goals)
- We are **not** building a Data Warehouse. No persistent storage across sessions.
- We are **not** supporting real-time data streaming (e.g., Kafka).
- We are **not** building collaborative features (multiplayer dashboards).
- We are **not** adding ML models for anomaly detection — Z-score is sufficient.

---

## 8. Monetization Strategy
- **Freemium Tier:** 5 free queries per day, manual CSV upload only.
- **Pro Tier ($29/mo):** Unlimited queries, PM analytics features, root-cause analysis.
- **Team Tier ($79/mo):** Direct integrations with Stripe/Shopify/Mixpanel APIs (Future).
