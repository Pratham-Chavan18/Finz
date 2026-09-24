import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, extract
from app.models.transaction import Transaction
from app.services.pnl import generate_monthly_pnl
from app.services.variance import calculate_monthly_variances


# ==============================================================================
# DETERMINISTIC AGENT TOOLS
# ==============================================================================

def tool_get_monthly_revenue(db: Session, target_month: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves deterministic revenue aggregates and top sales transactions."""
    pnl = generate_monthly_pnl(db)
    rev_sec = pnl["sections"]["revenue"]
    monthly_totals = rev_sec["monthly_totals"]
    lines = rev_sec["lines"]

    # Top revenue transactions
    query = (
        db.query(Transaction)
        .filter(Transaction.pnl_bucket == "Revenue")
        .order_by(desc(Transaction.amount))
    )
    if target_month:
        try:
            y, m = [int(x) for x in target_month.split("-")]
            query = query.filter(
                extract("year", Transaction.date) == y,
                extract("month", Transaction.date) == m,
            )
        except Exception:
            pass

    top_txns = query.limit(5).all()

    return {
        "monthly_totals": monthly_totals,
        "grand_total": rev_sec["grand_total"],
        "lines": lines,
        "top_transactions": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty or "Toast POS",
                "amount": t.amount,
                "category": t.category,
            }
            for t in top_txns
        ],
    }


def tool_get_payroll_spend(db: Session, target_month: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves deterministic payroll expenses broken down by category and month."""
    pnl = generate_monthly_pnl(db)
    payroll_sec = pnl["sections"]["payroll"]

    query = (
        db.query(Transaction)
        .filter(Transaction.pnl_bucket == "Payroll")
        .order_by(Transaction.amount.asc())  # largest outflow
    )
    if target_month:
        try:
            y, m = [int(x) for x in target_month.split("-")]
            query = query.filter(
                extract("year", Transaction.date) == y,
                extract("month", Transaction.date) == m,
            )
        except Exception:
            pass

    txns = query.limit(6).all()

    return {
        "monthly_totals": payroll_sec["monthly_totals"],
        "grand_total": payroll_sec["grand_total"],
        "lines": payroll_sec["lines"],
        "transactions": [
            {
                "id": t.id,
                "transaction_code": t.transaction_code or f"TX-{t.id}",
                "date": str(t.date),
                "description": t.description,
                "counterparty": t.counterparty or "Gusto",
                "amount": t.amount,
                "category": t.category,
            }
            for t in txns
        ],
    }


def tool_get_operating_profit_variance(
    db: Session,
    baseline_month: Optional[str] = None,
    current_month: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves MoM operating profit deltas and primary driver categories."""
    variance_res = calculate_monthly_variances(
        db=db,
        baseline_month=baseline_month,
        current_month=current_month,
        only_material=False,
    )
    return variance_res


def tool_get_attention_items(db: Session, limit: int = 8) -> List[Dict[str, Any]]:
    """Retrieves all transactions currently flagged for human review."""
    flagged = (
        db.query(Transaction)
        .filter(Transaction.is_flagged_for_review == True)
        .order_by(desc(Transaction.id))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "transaction_code": t.transaction_code or f"TX-{t.id}",
            "date": str(t.date),
            "description": t.description,
            "counterparty": t.counterparty,
            "amount": t.amount,
            "category": t.category,
            "pnl_bucket": t.pnl_bucket,
            "confidence": t.confidence,
            "rationale": t.rationale,
        }
        for t in flagged
    ]


def tool_get_transactions_by_category(
    db: Session,
    category_pattern: str,
    target_month: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """Retrieves specific transaction rows matching a category."""
    query = db.query(Transaction).filter(Transaction.category.ilike(f"%{category_pattern}%"))
    if target_month:
        try:
            y, m = [int(x) for x in target_month.split("-")]
            query = query.filter(
                extract("year", Transaction.date) == y,
                extract("month", Transaction.date) == m,
            )
        except Exception:
            pass

    txns = query.order_by(desc(Transaction.date)).limit(limit).all()
    return [
        {
            "id": t.id,
            "transaction_code": t.transaction_code or f"TX-{t.id}",
            "date": str(t.date),
            "description": t.description,
            "counterparty": t.counterparty,
            "amount": t.amount,
            "category": t.category,
            "pnl_bucket": t.pnl_bucket,
        }
        for t in txns
    ]


# ==============================================================================
# INTENT ROUTER & NATURAL LANGUAGE GENERATOR
# ==============================================================================

def process_financial_query(
    db: Session,
    message: str,
    history: Optional[List[Dict[str, Any]]] = None,
    tenant_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint for AI Financial Analyst queries.
    Routes queries to Ollama/ModelRouter with deterministic tool-calling and tenant isolation.
    """
    from app.ai.analyst import FinancialAIAnalyst
    analyst = FinancialAIAnalyst()
    return analyst.process_query(
        db=db,
        message=message,
        history=history,
        tenant_id=tenant_id,
        user_id=user_id,
    )


def fallback_deterministic_query(
    db: Session,
    message: str,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Deterministic query handler that executes database aggregations when external
    LLM provider is unreachable. Zero hallucination in financial numbers.
    """
    msg = message.strip().lower()
    citations = []
    tools_used = []

    # 1. REVENUE QUERY
    # "What was our revenue in [month]?" / "How much revenue did we make?"
    if any(k in msg for k in ["revenue", "sales", "inflow", "top line"]):
        tools_used.append("get_monthly_revenue")
        # Check if user mentioned a month (e.g. jan, feb, march, 2026-01)
        month_match = None
        if "jan" in msg or "01" in msg:
            month_match = "2026-01"
        elif "feb" in msg or "02" in msg:
            month_match = "2026-02"
        elif "mar" in msg or "03" in msg:
            month_match = "2026-03"

        data = tool_get_monthly_revenue(db, target_month=month_match)
        totals = data["monthly_totals"]
        grand_total = data["grand_total"]

        if month_match and month_match in totals:
            amt = totals[month_match]
            reply = (
                f"### Revenue for {month_match}\n\n"
                f"Our total recorded revenue in **{month_match}** was **${amt:,.2f}**.\n\n"
                f"**Breakdown by Revenue Stream:**\n"
            )
            for line in data["lines"]:
                cat_amt = line["by_month"].get(month_match, 0.0)
                if cat_amt > 0:
                    reply += f"- **{line['category']}**: ${cat_amt:,.2f}\n"
                    citations.append({
                        "id": line["category"],
                        "type": "category",
                        "label": f"{line['category']} (${cat_amt:,.2f})",
                        "amount": cat_amt,
                    })

            reply += f"\n**Key Revenue Deposits:**\n"
            for t in data["top_transactions"][:3]:
                reply += f"- {t['transaction_code']} ({t['date']}): **{t['counterparty']}** — ${t['amount']:,.2f}\n"
                citations.append({
                    "id": t["transaction_code"],
                    "type": "transaction",
                    "label": f"{t['transaction_code']} ({t['counterparty']})",
                    "amount": t["amount"],
                    "date": t["date"],
                })
        else:
            reply = (
                f"### Monthly Revenue Summary\n\n"
                f"Total cumulative revenue across all reporting periods is **${grand_total:,.2f}**.\n\n"
                f"**Monthly Totals:**\n"
            )
            for m, amt in sorted(totals.items()):
                reply += f"- **{m}**: ${amt:,.2f}\n"

            reply += f"\n**Top Revenue Deposits:**\n"
            for t in data["top_transactions"][:3]:
                reply += f"- {t['transaction_code']} ({t['date']}): **{t['counterparty']}** — ${t['amount']:,.2f}\n"
                citations.append({
                    "id": t["transaction_code"],
                    "type": "transaction",
                    "label": f"{t['transaction_code']} ({t['counterparty']})",
                    "amount": t["amount"],
                    "date": t["date"],
                })

        return {
            "reply": reply,
            "citations": citations,
            "tools_used": tools_used,
        }

    # 2. PAYROLL QUERY
    # "How much did we spend on payroll each month?" / "Payroll spend"
    if any(k in msg for k in ["payroll", "wages", "salaries", "salary", "staff cost"]):
        tools_used.append("get_payroll_spend")
        data = tool_get_payroll_spend(db)
        totals = data["monthly_totals"]
        grand_total = data["grand_total"]

        reply = (
            f"### Monthly Payroll Spend\n\n"
            f"We spent a total of **${grand_total:,.2f}** on employee compensation and employer payroll taxes.\n\n"
            f"**Spend by Month:**\n"
        )
        for m, amt in sorted(totals.items()):
            reply += f"- **{m}**: ${amt:,.2f}\n"

        reply += f"\n**Payroll Component Breakdown:**\n"
        for line in data["lines"]:
            reply += f"- **{line['category']}**: ${line['total']:,.2f} cumulative\n"
            citations.append({
                "id": line["category"],
                "type": "category",
                "label": f"{line['category']} (${line['total']:,.2f})",
                "amount": line["total"],
            })

        reply += f"\n**Key Payroll Disbursements:**\n"
        for t in data["transactions"][:3]:
            reply += f"- {t['transaction_code']} ({t['date']}): **{t['counterparty']}** — ${abs(t['amount']):,.2f}\n"
            citations.append({
                "id": t["transaction_code"],
                "type": "transaction",
                "label": f"{t['transaction_code']} ({t['counterparty']})",
                "amount": t["amount"],
                "date": t["date"],
            })

        return {
            "reply": reply,
            "citations": citations,
            "tools_used": tools_used,
        }

    # 3. VARIANCE & PROFIT CHANGE QUERY
    # "Why did operating profit change between [month] and [month]?" / "Why did profit change?"
    if any(k in msg for k in ["why did operating profit change", "profit change", "profit variance", "variance between"]):
        tools_used.append("get_operating_profit_variance")
        var_data = tool_get_operating_profit_variance(db)
        base_m = var_data["baseline_month"]
        curr_m = var_data["current_month"]

        # Find operating profit summary item
        op_metric = next((s for s in var_data.get("summary_variances", []) if s["metric"] == "operating_profit"), None)
        rev_metric = next((s for s in var_data.get("summary_variances", []) if s["metric"] in ("revenue", "Revenue")), None)
        cogs_metric = next((s for s in var_data.get("summary_variances", []) if s["metric"] == "cogs"), None)

        delta_amt = op_metric["delta_amount"] if op_metric else 0.0
        delta_pct = op_metric["delta_pct"] if op_metric else 0.0
        is_fav = op_metric["is_favorable"] if op_metric else (delta_amt >= 0)
        base_amt = op_metric["baseline_amount"] if op_metric else 0.0
        curr_amt = op_metric["current_amount"] if op_metric else 0.0

        reply = (
            f"### Operating Profit Variance ({base_m} → {curr_m})\n\n"
            f"Operating profit {'increased' if delta_amt >= 0 else 'decreased'} by **${abs(delta_amt):,.2f}** "
            f"({delta_pct:+.1f}%), moving from **${base_amt:,.2f}** in {base_m} to **${curr_amt:,.2f}** in {curr_m}. "
            f"This shift was **{'Favorable' if is_fav else 'Unfavorable'}**.\n\n"
            f"**Key Operational Drivers:**\n"
        )

        for cv in var_data["category_variances"][:3]:
            polarity = "Favorable" if cv["is_favorable"] else "Unfavorable"
            reply += (
                f"- **{cv['category']}** ({cv['pnl_bucket']}): {cv['delta_amount']:+,.2f} ({cv['delta_pct']:+.1f}%) — *{polarity}*\n"
                f"  *{cv['explanation']}*\n"
            )
            citations.append({
                "id": cv["category"],
                "type": "category",
                "label": f"{cv['category']} ({cv['delta_amount']:+,.2f})",
                "amount": cv["delta_amount"],
            })
            for d in cv["drivers"][:2]:
                citations.append({
                    "id": d["transaction_code"],
                    "type": "transaction",
                    "label": f"{d['transaction_code']} ({d['counterparty']})",
                    "amount": d["amount"],
                    "date": d["date"],
                })

        return {
            "reply": reply,
            "citations": citations,
            "tools_used": tools_used,
        }

    # 4. ATTENTION / REVIEW QUERY
    # "Which transactions need my attention?" / "Attention" / "Review items"
    if any(k in msg for k in ["attention", "review", "flagged", "uncertain", "audit", "triage"]):
        tools_used.append("get_attention_items")
        flagged_items = tool_get_attention_items(db, limit=6)

        if not flagged_items:
            reply = (
                f"### All Transactions Verified\n\n"
                f"There are currently **0 transactions** requiring your attention! "
                f"All ingested bank records have been classified with high confidence (&ge; 85%) or confirmed by a reviewer."
            )
        else:
            reply = (
                f"### Transactions Requiring Review ({len(flagged_items)} items)\n\n"
                f"The following transactions have been flagged by the automated review rules due to "
                f"uncertain confidence scores (< 85%) or balance sheet / CapEx accounting treatments:\n\n"
            )
            for item in flagged_items:
                reply += (
                    f"- **{item['transaction_code']}** ({item['date']}): **{item['description']}** — ${abs(item['amount']):,.2f}\n"
                    f"  - **Proposed Bucket**: `{item['category']}` ({item['pnl_bucket']})\n"
                    f"  - **Reason**: {item['rationale'] or 'Low classification confidence'}\n"
                )
                citations.append({
                    "id": item["transaction_code"],
                    "type": "transaction",
                    "label": f"{item['transaction_code']} (${abs(item['amount']):,.2f})",
                    "amount": item["amount"],
                    "date": item["date"],
                })

        return {
            "reply": reply,
            "citations": citations,
            "tools_used": tools_used,
        }

    # 5. TRANSACTIONS BEHIND VARIANCE / CATEGORY DRILL-DOWN
    # "Show me the transactions behind that variance" / "Transactions behind food inventory"
    if any(k in msg for k in ["transactions behind", "drill down", "underlying transactions", "show me transactions"]):
        tools_used.append("get_transactions_by_category")
        # Extract potential category
        cat_match = "Food Inventory"
        if "food" in msg and "sales" in msg:
            cat_match = "Food Sales"
        elif "beverage" in msg or "alcohol" in msg:
            cat_match = "Beverage"
        elif "payroll" in msg or "wage" in msg:
            cat_match = "Wages"
        elif "rent" in msg:
            cat_match = "Rent"
        elif "packaging" in msg:
            cat_match = "Packaging"

        txns = tool_get_transactions_by_category(db, category_pattern=cat_match, limit=5)
        reply = (
            f"### Underlying Transactions for {cat_match}\n\n"
            f"Found **{len(txns)}** representative transactions matching `{cat_match}`:\n\n"
        )
        for t in txns:
            reply += f"- **{t['transaction_code']}** ({t['date']}): **{t['counterparty'] or t['description']}** — ${abs(t['amount']):,.2f} ({t['category']})\n"
            citations.append({
                "id": t["transaction_code"],
                "type": "transaction",
                "label": f"{t['transaction_code']} ({t['counterparty']})",
                "amount": t["amount"],
                "date": t["date"],
            })

        return {
            "reply": reply,
            "citations": citations,
            "tools_used": tools_used,
        }

    # 6. GENERAL P&L INQUIRY (DEFAULT FALLBACK)
    tools_used.append("get_pnl_summary")
    pnl = generate_monthly_pnl(db)
    tot = pnl["summary"].get("total", {})
    months_str = ", ".join(pnl["months"]) if pnl["months"] else "N/A"

    reply = (
        f"### Financial Overview ({months_str})\n\n"
        f"- **Cumulative Revenue**: ${tot.get('revenue', 0.0):,.2f}\n"
        f"- **Gross Profit**: ${tot.get('gross_profit', 0.0):,.2f} ({tot.get('gross_margin_pct', 0.0):.1f}% margin)\n"
        f"- **Operating Profit (EBITDA)**: ${tot.get('operating_profit', 0.0):,.2f} ({tot.get('operating_margin_pct', 0.0):.1f}% margin)\n"
        f"- **Total Operating Expenses**: ${tot.get('total_operating_expenses', 0.0):,.2f}\n\n"
        f"**You can ask me questions like:**\n"
        f"1. *What was our revenue in Jan 2026?*\n"
        f"2. *How much did we spend on payroll each month?*\n"
        f"3. *Why did operating profit change between Jan and Feb?*\n"
        f"4. *Which transactions need my attention?*\n"
        f"5. *Show me the transactions behind the food inventory variance.*"
    )

    return {
        "reply": reply,
        "citations": citations,
        "tools_used": tools_used,
    }
