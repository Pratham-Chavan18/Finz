# Development Rules

## General
- TypeScript on the frontend, typed Python (type hints) on the backend.
- Reuse existing components and services — do not duplicate logic, especially P&L logic.
- Keep functions small and single-purpose.
- Do not modify unrelated files.

## Before Coding
- Read PRD.md, ARCHITECTURE.md, and DESIGN.md before implementing anything.
- Inspect existing implementation before adding new code.
- Reuse existing functionality where possible.
- Make a short plan before any large or multi-file change.

## Financial Logic (non-negotiable)
- The LLM must never produce a P&L total, subtotal, or numeric aggregate directly. All totals are computed in `services/pnl.py` from stored transaction data.
- Every AI-generated explanation (variance, chat answer) must cite the specific transactions or categories it is based on.
- No AI output presented as fact may be unverifiable against the underlying data.
- Variance materiality thresholds and the chart of accounts live in one place (config), not scattered across the codebase.

## UI
- Follow DESIGN.md.
- Maintain responsive layout, especially for dense tables.
- Include loading, error, and empty states for every view that touches the LLM or the database.

## Security
- Never expose API keys or secrets client-side.
- Validate all uploaded file input (type, size, malformed rows) before parsing.
- Validate and sanitize all request bodies server-side.
- Verify authorization server-side wherever data access is scoped to a user/session.

## Testing
- Add tests for P&L calculation and variance detection — these are deterministic and must be exactly right.
- Test categorization against a fixed "golden set" of transactions to catch regressions.
- Run tests after every implementation step; fix failures before moving on.

## Git
- Small, focused commits.
- Descriptive commit messages using conventional prefixes (`feat:`, `fix:`, `docs:`, `test:`).
