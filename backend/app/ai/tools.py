import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, extract, or_

from app.models.transaction import Transaction
from app.services.pnl import generate_monthly_pnl
from app.services.variance import calculate_monthly_variances

logger = logging.getLogger("app.ai.tools")

ALLOWED_TOOLS = {
    "get_monthly_pnl",
    "compare_months",
    "get_variances",
    "get_transactions",
    "get_transaction",
    "get_category_breakdown",
    "get_review_items",
    "get_variance_drivers",
    "search_financial_evidence",
}


# ==============================================================================
# DETERMINISTIC FINANCIAL TOOLS (POSTGRESQL SINGLE SOURCE OF TRUTH)
# ==============================================================================

def get_monthly_pnl(
    db: Session,
    month: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieves authoritative monthly P&L statement figures calculated from database."""
    pnl = generate_monthly_pnl(db, tenant_id=tenant_id)
    months = pnl.get("months", [])
    summary = pnl.get("summary", {})

    if month and month in summary:
        m_sum = summary[month]
        # Fetch top transactions for that month to supply concrete evidence
        q = db.query(Transaction)
        if tenant_id is not None:
            q = q.filter(Transaction.tenant_id == tenant_id)
        try:
            parts = month.split("-")
            if len(parts) == 2:
                q = q.filter(
                    extract("year", Transaction.date) == int(parts[0]),
                    extract("month", Transaction.date) == int(parts[1]),
                )
        except Exception:
            pass
        top_txns = q.order_by(desc(Transaction.amount)).limit(5).all()

        return {
            "month": month,
            "revenue": m_sum["revenue"],
            "cogs": m_sum["cogs"],
            "gross_profit": m_sum["gross_profit"],
            "gross_margin_pct": m_sum["gross_margin_pct"],
            "payroll": m_sum["payroll"],
            "operating_expenses": m_sum["opex"],
            "total_operating_expenses": m_sum["total_operating_expenses"],
            "operating_profit": m_sum["operating_profit"],
            "operating_margin_pct": m_sum["operating_margin_pct"],
            "available_months": months,
            "transactions": [
                {
                    "id": t.id,
                    "transaction_code": t.transaction_code or f"TX-{t.id}",
                    "date": str(t.date),
                    "description": t.description,
                    "counterparty": t.counterparty or "Unknown",
                    "amount": t.amount,
                    "category": t.category,
                    "pnl_bucket": t.pnl_bucket,
                }
                for t in top_txns
            ],
        }

    # If no month or month not in summary, return all available months summary and multi-month total
    total = summary.get("total", {})
    return {
        "reporting_months": months,
        "monthly_summaries": {m: summary[m] for m in months if m in summary},
        "cumulative_totals": total,
    }


def compare_months(
    db: Session,
    month_a: str,
    month_b: str,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Compares financial metrics between two reporting months, identifying variances."""
    res = calculate_monthly_variances(
        db=db,
        baseline_month=month_a,
        current_month=month_b,
        only_material=False,
        tenant_id=tenant_id,
    )
    return {
        "baseline_month": res["baseline_month"],
        "current_month": res["current_month"],
        "summary_variances": res["summary_variances"],
        "category_variances": res["category_variances"],
    }


def get_variances(
    db: Session,
    month_a: Optional[str] = None,
    month_b: Optional[str] = None,
    only_material: bool = True,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieves material variances between months with thresholds applied."""
    return calculate_monthly_variances(
        db=db,
        baseline_month=month_a,
        current_month=month_b,
        only_material=only_material,
        tenant_id=tenant_id,
    )


def get_transactions(
    db: Session,
    month: Optional[str] = None,
    category: Optional[str] = None,
    pnl_bucket: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 10,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Queries underlying transactions with deterministic filters."""
    query = db.query(Transaction)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)

    if month:
        try:
            parts = month.split("-")
            if len(parts) == 2:
                y, m = int(parts[0]), int(parts[1])
                query = query.filter(
                    extract("year", Transaction.date) == y,
                    extract("month", Transaction.date) == m,
                )
        except Exception:
            pass

    if category:
        query = query.filter(Transaction.category.ilike(f"%{category}%"))

    if pnl_bucket:
        query = query.filter(Transaction.pnl_bucket.ilike(pnl_bucket))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Transaction.description.ilike(pattern),
                Transaction.counterparty.ilike(pattern),
                Transaction.category.ilike(pattern),
            )
        )

    safe_limit = min(max(1, limit), 25)
    txns = query.order_by(desc(Transaction.date), desc(Transaction.id)).limit(safe_limit).all()

    return {
        "count": len(txns),
        "transactions": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty or "Unknown",
                "amount": t.amount,
                "category": t.category,
                "pnl_bucket": t.pnl_bucket,
            }
            for t in txns
        ],
    }


def get_transaction(
    db: Session,
    transaction_id: int,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieves full details for a specific transaction by ID."""
    query = db.query(Transaction).filter(Transaction.id == transaction_id)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)
    t = query.first()
    if not t:
        return {"error": f"Transaction with ID {transaction_id} not found."}

    return {
        "id": t.id,
        "transaction_code": t.transaction_code or f"TX-{t.id}",
        "date": str(t.date),
        "description": t.description,
        "counterparty": t.counterparty,
        "amount": t.amount,
        "category": t.category,
        "pnl_bucket": t.pnl_bucket,
        "method": t.method,
        "confidence": t.confidence,
        "rationale": t.rationale,
        "is_flagged_for_review": t.is_flagged_for_review,
        "review_status": t.review_status,
    }


def get_category_breakdown(
    db: Session,
    month: Optional[str] = None,
    category: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Returns lines and monthly distribution for a category or P&L section."""
    pnl = generate_monthly_pnl(db, tenant_id=tenant_id)
    sections = pnl.get("sections", {})

    matching_lines = []
    for sec_name, sec_data in sections.items():
        for line in sec_data.get("lines", []):
            if not category or category.lower() in line["category"].lower():
                matching_lines.append({
                    "category": line["category"],
                    "bucket": sec_name,
                    "monthly_totals": line["by_month"],
                    "total": line["total"],
                })

    return {
        "matching_lines": matching_lines,
        "months": pnl.get("months", []),
    }


def get_review_items(
    db: Session,
    limit: int = 10,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieves transactions flagged for human audit or review."""
    safe_limit = min(max(1, limit), 25)
    query = db.query(Transaction).filter(Transaction.is_flagged_for_review == True)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)

    flagged = (
        query
        .order_by(desc(Transaction.id))
        .limit(safe_limit)
        .all()
    )

    return {
        "count": len(flagged),
        "review_items": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty or "Unknown",
                "amount": t.amount,
                "category": t.category,
                "pnl_bucket": t.pnl_bucket,
                "confidence": t.confidence,
                "rationale": t.rationale,
            }
            for t in flagged
        ],
    }


def get_variance_drivers(
    db: Session,
    month_a: str,
    month_b: str,
    category: str,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieves specific transaction drivers causing a variance in a category."""
    res = calculate_monthly_variances(
        db=db,
        baseline_month=month_a,
        current_month=month_b,
        only_material=False,
        tenant_id=tenant_id,
    )
    cat_lower = category.lower()
    match = next(
        (cv for cv in res["category_variances"] if cat_lower in cv["category"].lower()),
        None,
    )

    if not match:
        return {
            "category": category,
            "found": False,
            "message": f"No variance record found for category '{category}' between {month_a} and {month_b}.",
        }

    return {
        "category": match["category"],
        "pnl_bucket": match["pnl_bucket"],
        "baseline_amount": match["baseline_amount"],
        "current_amount": match["current_amount"],
        "delta_amount": match["delta_amount"],
        "delta_pct": match["delta_pct"],
        "is_favorable": match["is_favorable"],
        "explanation": match["explanation"],
        "drivers": match.get("drivers", []),
    }


def search_financial_evidence(
    db: Session,
    query: str,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Searches transaction database for supporting evidence matching text queries."""
    clean_q = query.strip()
    if not clean_q:
        return {"count": 0, "evidence": []}

    pattern = f"%{clean_q}%"
    q = (
        db.query(Transaction)
        .filter(
            or_(
                Transaction.description.ilike(pattern),
                Transaction.counterparty.ilike(pattern),
                Transaction.category.ilike(pattern),
                Transaction.rationale.ilike(pattern),
            )
        )
    )
    if tenant_id is not None:
        q = q.filter(Transaction.tenant_id == tenant_id)

    txns = q.order_by(desc(Transaction.date)).limit(10).all()

    return {
        "query": clean_q,
        "count": len(txns),
        "evidence": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty or "Unknown",
                "amount": t.amount,
                "category": t.category,
                "pnl_bucket": t.pnl_bucket,
            }
            for t in txns
        ],
    }


# ==============================================================================
# TOOL DISPATCHER & VALIDATION
# ==============================================================================

def execute_tool(
    db: Session,
    tool_name: str,
    arguments: Dict[str, Any],
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Safely dispatches and executes an approved financial tool against PostgreSQL.
    Rejects unauthorized or unknown tool invocations.
    Strictly asserts authenticated tenant_id, discarding any LLM-attempted tenant spoofing.
    """
    if tool_name not in ALLOWED_TOOLS:
        logger.warning("Rejected execution of unapproved tool: %s", tool_name)
        return {"error": f"Tool '{tool_name}' is not an authorized financial tool."}

    # Defense: Never allow the LLM to control tenant_id
    safe_args = {k: v for k, v in arguments.items() if k != "tenant_id"}

    logger.info("Executing financial tool: %s with args=%s (tenant_id=%s)", tool_name, safe_args, tenant_id)

    try:
        if tool_name == "get_monthly_pnl":
            return get_monthly_pnl(db, month=safe_args.get("month"), tenant_id=tenant_id)
        elif tool_name == "compare_months":
            return compare_months(db, month_a=safe_args["month_a"], month_b=safe_args["month_b"], tenant_id=tenant_id)
        elif tool_name == "get_variances":
            return get_variances(
                db,
                month_a=safe_args.get("month_a"),
                month_b=safe_args.get("month_b"),
                only_material=safe_args.get("only_material", True),
                tenant_id=tenant_id,
            )
        elif tool_name == "get_transactions":
            return get_transactions(
                db,
                month=safe_args.get("month"),
                category=safe_args.get("category"),
                pnl_bucket=safe_args.get("pnl_bucket"),
                search=safe_args.get("search"),
                limit=safe_args.get("limit", 10),
                tenant_id=tenant_id,
            )
        elif tool_name == "get_transaction":
            return get_transaction(db, transaction_id=int(safe_args["transaction_id"]), tenant_id=tenant_id)
        elif tool_name == "get_category_breakdown":
            return get_category_breakdown(
                db,
                month=safe_args.get("month"),
                category=safe_args.get("category"),
                tenant_id=tenant_id,
            )
        elif tool_name == "get_review_items":
            return get_review_items(db, limit=safe_args.get("limit", 10), tenant_id=tenant_id)
        elif tool_name == "get_variance_drivers":
            return get_variance_drivers(
                db,
                month_a=safe_args["month_a"],
                month_b=safe_args["month_b"],
                category=safe_args["category"],
                tenant_id=tenant_id,
            )
        elif tool_name == "search_financial_evidence":
            return search_financial_evidence(db, query=safe_args["query"], tenant_id=tenant_id)
        else:
            return {"error": f"Unhandled tool: {tool_name}"}

    except Exception as e:
        logger.error("Error executing tool %s: %s", tool_name, type(e).__name__)
        return {"error": f"Failed to execute {tool_name}: {type(e).__name__}"}


# ==============================================================================
# OPENAI-COMPATIBLE FUNCTION SCHEMAS FOR DEEPSEEK
# ==============================================================================

FINANCIAL_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_monthly_pnl",
            "description": "Retrieves authoritative monthly P&L financial statement figures (revenue, COGS, gross profit, payroll, opex, operating profit). Use this for any revenue or profit inquiry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {
                        "type": "string",
                        "description": "Optional reporting month format YYYY-MM (e.g. '2026-01', '2026-02', '2026-03'). If omitted, returns all months and multi-month cumulative totals.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_months",
            "description": "Compares performance metrics between two months and identifies deltas across revenue, operating expenses, and operating profit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {
                        "type": "string",
                        "description": "Baseline month in YYYY-MM format (e.g. '2026-01')",
                    },
                    "month_b": {
                        "type": "string",
                        "description": "Comparison month in YYYY-MM format (e.g. '2026-02')",
                    },
                },
                "required": ["month_a", "month_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_variances",
            "description": "Retrieves month-over-month variances meeting materiality thresholds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "description": "Baseline month (YYYY-MM)"},
                    "month_b": {"type": "string", "description": "Current month (YYYY-MM)"},
                    "only_material": {
                        "type": "boolean",
                        "description": "Whether to return only material variances (default true)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transactions",
            "description": "Queries individual bank transactions from PostgreSQL with optional filtering by month, category, P&L bucket, or search terms.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "YYYY-MM filtering (e.g. '2026-03')"},
                    "category": {"type": "string", "description": "Category name filter (e.g. 'Food Inventory', 'Salaries')"},
                    "pnl_bucket": {"type": "string", "description": "P&L Bucket: 'Revenue', 'COGS', 'Payroll', 'OpEx', 'Non-P&L'"},
                    "search": {"type": "string", "description": "Search keyword in description or payee"},
                    "limit": {"type": "integer", "description": "Maximum records to return (1-25)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction",
            "description": "Fetches complete record for a single transaction by primary key ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transaction_id": {"type": "integer", "description": "Database ID of transaction"},
                },
                "required": ["transaction_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_breakdown",
            "description": "Retrieves detailed breakdown of expenses or revenue for a specific category across months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category name (e.g. 'Payroll Taxes', 'Utilities')"},
                    "month": {"type": "string", "description": "Optional month (YYYY-MM)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_review_items",
            "description": "Retrieves transactions flagged for review (low confidence or CapEx/balance sheet treatment) needing human audit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum items to retrieve (default 10)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_variance_drivers",
            "description": "Retrieves specific transactions responsible for a category variance between two months.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month_a": {"type": "string", "description": "Baseline month (YYYY-MM)"},
                    "month_b": {"type": "string", "description": "Current month (YYYY-MM)"},
                    "category": {"type": "string", "description": "Category name to inspect"},
                },
                "required": ["month_a", "month_b", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_financial_evidence",
            "description": "Searches transaction descriptions, payees, and notes to find evidence supporting financial claims.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keyword or payee name to search"},
                },
                "required": ["query"],
            },
        },
    },
]
