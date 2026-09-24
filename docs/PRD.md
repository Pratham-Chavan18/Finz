# Product Requirements Document

## Product
FinReview — AI-Native Financial Review App
*(working name — rename freely)*

## Context
Take-home technical challenge for the FINZ Software Engineering Internship. Submission is evaluated on reliability, explainability, and engineering judgment, not feature count. Shortlisted candidates are invited to an in-person build session and interview in Koramangala, Bangalore.

## Problem
Raw bank transactions give no immediate financial picture. Someone reviewing a business's finances has to manually categorize transactions, build a P&L, spot what changed month to month, and figure out which items need judgment — all before they can actually ask questions about the numbers.

## Target Users
Whoever is reviewing the business's finances (in this challenge, the FINZ evaluators standing in for that user) — someone who needs a trustworthy monthly P&L, a fast way to spot what changed and why, and a way to interrogate the numbers in plain language.

## Goal
Build a working, explainable financial review application that turns a raw bank transaction file into a categorized monthly P&L, surfaces material variances and their drivers, flags items needing human review, and lets the user investigate all of it conversationally — with every AI answer traceable back to underlying transactions.

## Core Workflow
Ingest → Categorize → Review → Calculate → Explain → Investigate

## Core Features

1. **Ingest financial data** — accept the provided bank transaction file, parse it, and produce a structured representation used across the app.
2. **Categorize and label transactions** — auto-classify each transaction into a sensible accounting category.
3. **Build the P&L** — generate monthly P&Ls (Revenue, COGS, Gross Profit, Payroll, Operating Expenses, Operating Profit) from the classified transactions.
4. **Find and explain variances** — compare monthly P&Ls, flag material changes, and show the transactions/categories driving each one.
5. **Identify items requiring review** — surface transactions with uncertain classification, judgment-requiring treatment, or unusual/inconsistent data.
6. **AI financial analyst** — conversational interface that answers questions using the underlying structured data, with traceable evidence.

## MVP

- File upload / ingestion of the provided transaction dataset
- Transaction categorization with a visible category per transaction
- Confidence flag on uncertain classifications
- User can correct a classification and have it persist
- Distinction between P&L transactions and items needing different accounting treatment
- Monthly P&L: Revenue, COGS, Gross Profit, Payroll, Operating Expenses, Operating Profit — computed deterministically from transaction data (not LLM-generated totals)
- Month-over-month variance detection with drill-down to underlying transactions
- Review queue for flagged/uncertain items, resolvable by the user
- Conversational analyst that answers at minimum:
  - "What was our revenue in [month]?"
  - "How much did we spend on payroll each month?"
  - "Why did operating profit change between [month] and [month]?"
  - "Which transactions need my attention?"
  - "Show me the transactions behind that variance."

## Out of Scope (v1)

- Multi-company / multi-entity support
- Multi-currency
- Payments or billing
- Mobile application
- Authentication beyond what's needed to run a single-user demo
- Exports/reporting beyond what's needed to demonstrate the workflow

## AI-Native Engineering Principles

- Use AI where reasoning, interpretation, or understanding adds value (categorization, variance explanation, conversational Q&A).
- Use deterministic computation wherever financial accuracy is required — **the LLM must never generate P&L totals.**
- Every AI-driven answer or explanation must be traceable to the underlying transaction data.
- Design must make explicit: where AI is used, where deterministic logic is used, how incorrect/unsupported financial answers are prevented, and how output is verified.

## Open Technical Decisions
*(to be resolved in ARCHITECTURE.md)*

| Area | Decisions needed |
|---|---|
| Application | Frontend, backend, database, deployment |
| AI system | Model, agent architecture, tools, categorization approach, retrieval |
| Financial logic | Chart of accounts, variance methodology, review rules |

## Success Criteria

The submitted app and its walkthrough should demonstrate:

1. File ingestion
2. Transaction categorization
3. A classification correction
4. A generated P&L
5. A material variance and its drivers
6. At least two questions answered through the AI interface
7. How an answer or variance can be traced back to its underlying data

## Submission Requirements

- GitHub repository
- Live deployed application
- Video walkthrough (covering the success criteria above)
- README with setup instructions and key technical decisions
