# Tasks

## Phase 1: Setup
- [ ] Initialize frontend (Next.js + TypeScript + Tailwind)
- [ ] Initialize backend (FastAPI project structure)
- [ ] Set up PostgreSQL and connection config
- [ ] Configure `.env` from `.env.example`
- [ ] Configure Git + initial commit

## Phase 2: Ingestion
- [ ] Define `Transaction` model + migration
- [ ] Build CSV/file parser for the provided transaction dataset
- [ ] Build `/ingest` API endpoint
- [ ] Build upload UI + raw transaction table view

## Phase 3: Categorization
- [ ] Define chart of accounts / category list
- [ ] Build categorization service (LLM call, structured output: category + confidence + rationale)
- [ ] Store category + confidence on each transaction
- [ ] Add category + confidence badges to the transaction table UI
- [ ] Build correction flow (edit category → persist → audit log entry)
- [ ] Test categorization against a golden set of transactions

## Phase 4: P&L Engine
- [ ] Build deterministic aggregation service (`services/pnl.py`)
- [ ] Build `/pnl` API endpoint (monthly Revenue, COGS, Gross Profit, Payroll, OpEx, Operating Profit)
- [ ] Build P&L statement UI view
- [ ] Unit tests for P&L math (no LLM in this path)

## Phase 5: Variance Engine
- [ ] Build month-over-month diff logic + materiality threshold config
- [ ] Build `/variance` API endpoint
- [ ] Build variance UI with drill-down to underlying transactions
- [ ] Build LLM explanation layer, grounded in computed deltas (no recomputation)
- [ ] Unit tests for variance detection logic

## Phase 6: Review Queue
- [ ] Build flagging logic (uncertain classification, judgment-required, unusual data)
- [ ] Build review queue UI
- [ ] Build resolve action (correct / confirm / dismiss)

## Phase 7: AI Analyst
- [ ] Define LangChain tools: `get_revenue`, `get_category_total`, `get_variance`, `get_transactions`, etc.
- [ ] Wire up agent with the fixed toolset
- [ ] Build chat UI with citation chips linking to source transactions
- [ ] Test against the required example questions (revenue by month, payroll spend, profit change drivers, flagged items, variance transactions)

## Phase 8: Polish & Submission
- [ ] Write README.md (setup, key decisions)
- [ ] Deploy frontend (Vercel) + backend/DB
- [ ] Smoke test the live deployed app end to end
- [ ] Record video walkthrough covering: ingestion, categorization, a correction, the generated P&L, a material variance and its drivers, ≥2 chat questions, and traceability to source data
- [ ] Final review against PRD.md / ARCHITECTURE.md / RULES.md
