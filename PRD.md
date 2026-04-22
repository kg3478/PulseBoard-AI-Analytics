# Product Requirements Document (PRD): PulseBoard

## 1. Meta
- **Product Name:** PulseBoard
- **Target Audience:** Non-technical founders at early-stage SaaS and D2C startups (0–20 person teams).
- **Core Value Proposition:** Ask questions of your data in plain English. Get charts in under 4 minutes. No SQL required.
- **Status:** V1 (MVP) Complete

## 2. Problem Space
Early-stage founders possess rich data (Stripe, Shopify, Google Analytics) but lack the technical skills (SQL) or bandwidth to extract insights.
- **Pain Point:** Founders spend Sunday nights in spreadsheets manually calculating MRR and Churn instead of talking to customers or building product.
- **Existing Solutions Fail:** Tools like Tableau, Looker, or Metabase require data engineering pipelines, data warehouse setup, and SQL proficiency. They are built for analysts, not founders.
- **The Core Insight:** Founders don't want a "Business Intelligence Dashboard." They want an *answer to a specific question*. The question is the product.

## 3. Target Persona
**"The Hustling Founder"**
- **Demographics:** 25-40, Business/Marketing/Domain-expert background.
- **Tech Fluency:** Can write complex Excel formulas but cannot write `JOIN` statements in SQL.
- **Data Stack:** CSV exports, Google Sheets, Airtable.
- **Willingness to Pay:** $29–$49/mo if it saves them >2 hours of manual reporting per week.

## 4. Success Metrics (KPIs)
| Metric | Definition | Target for Success |
|---|---|---|
| **North Star: Time-to-First-Insight** | Minutes from data upload to first successful chart render. | **< 4 minutes** |
| **Activation Rate** | % users who run their first query within 10 min of upload. | > 70% |
| **NL Query Success Rate** | % of natural language queries that execute without SQL error. | > 80% |
| **Week-2 Return Rate** | % of activated users who return in week 2. | > 40% |

## 5. Core Features & User Stories

### Feature 1: Frictionless Onboarding (Zero-ETL)
- **User Story:** As a founder, I want to drag and drop a CSV file so I can start analyzing immediately without connecting databases.
- **Requirement:** System must auto-detect schema (Date, Numeric, Text) and present 5 AI-generated starter questions to overcome the "blank canvas" problem.

### Feature 2: NL-to-SQL Query Interface
- **User Story:** As a founder, I want to type "Show me revenue by city" and get a chart instantly.
- **Requirement:** Use Groq API (LLaMA 3.3 70B) to translate English to SQL. Must handle simple aggregations, grouping, and time-series filtering. Must include a self-healing retry loop if the SQL fails.

### Feature 3: Auto-Charting
- **User Story:** As a founder, I don't want to configure X and Y axes. I just want the data visualized perfectly.
- **Requirement:** System inspects the SQL output rows and auto-selects:
  - Line Chart (if time-series data exists)
  - Pie Chart (if categorical + numeric and < 8 rows)
  - Bar Chart (if categorical + numeric)
  - Table (fallback)

### Feature 4: Statistical Anomaly Alerts
- **User Story:** As a founder, I want to be alerted if my refund rate spikes unexpectedly so I can pause ads or investigate fraud.
- **Requirement:** Implement a 30-day rolling Z-score algorithm on all numeric columns. Trigger Critical alerts if `|z| > 3.0` and Warning alerts if `|z| > 2.0`.

### Feature 5: AI Narrative Insights
- **User Story:** As a founder, I want a quick summary of my business health every Monday morning.
- **Requirement:** Compute week-over-week deltas and feed them to Groq (LLaMA 3.3) to generate 3-5 actionable, plain-English bullet points.

## 6. Out of Scope (Non-Goals)
- We are **not** building a Data Warehouse. No persistent storage of data across sessions in V1.
- We are **not** supporting real-time data streaming (e.g., Kafka).
- We are **not** building collaborative features (multiplayer dashboards). V1 is a single-player tool.

## 7. Monetization Strategy
- **Freemium Tier:** 5 free queries per day, manual CSV upload only.
- **Pro Tier ($29/mo):** Unlimited queries, PDF export, root-cause analysis.
- **Team Tier ($79/mo):** Direct integrations with Stripe/Shopify APIs (Future feature).
