from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, extract
from app.models.transaction import Transaction
from app.services.pnl import generate_monthly_pnl


def calculate_monthly_variances(
    db: Session,
    baseline_month: Optional[str] = None,
    current_month: Optional[str] = None,
    min_amount: float = 1000.0,
    min_pct: float = 10.0,
    only_material: bool = True,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Computes deterministic month-over-month variances between two reporting months.
    Classifies favorable vs unfavorable polarity according to accounting standards:
      - Revenue / Gross Profit / Operating Profit: positive delta is Favorable.
      - Expenses (COGS, Payroll, OpEx): negative delta is Favorable (cost savings).
    Scoped to tenant_id when provided.
    """
    pnl = generate_monthly_pnl(db, tenant_id=tenant_id)
    available_months = pnl["months"]

    if len(available_months) < 2:
        return {
            "baseline_month": baseline_month,
            "current_month": current_month,
            "available_months": available_months,
            "message": "At least two months of categorized transactions are required to compute variances.",
            "summary_variances": [],
            "category_variances": [],
        }

    # Resolve default baseline and current months
    if not baseline_month or baseline_month not in available_months:
        baseline_month = available_months[0]
    if not current_month or current_month not in available_months:
        current_month = available_months[1] if len(available_months) > 1 else available_months[-1]

    # Summary level KPIs
    base_sum = pnl["summary"].get(baseline_month, {})
    curr_sum = pnl["summary"].get(current_month, {})

    summary_metrics = [
        {"metric": "revenue", "label": "Top-Line Revenue", "is_expense": False},
        {"metric": "cogs", "label": "Cost of Goods Sold (COGS)", "is_expense": True},
        {"metric": "gross_profit", "label": "Gross Profit", "is_expense": False},
        {"metric": "payroll", "label": "Payroll Expenses", "is_expense": True},
        {"metric": "opex", "label": "Operating Expenses (OpEx)", "is_expense": True},
        {"metric": "total_operating_expenses", "label": "Total Operating Expenses", "is_expense": True},
        {"metric": "operating_profit", "label": "Operating Profit (EBITDA)", "is_expense": False},
    ]

    summary_variances = []
    for sm in summary_metrics:
        m_key = sm["metric"]
        b_val = base_sum.get(m_key, 0.0)
        c_val = curr_sum.get(m_key, 0.0)
        delta_amt = round(c_val - b_val, 2)
        delta_pct = round((delta_amt / b_val * 100), 2) if b_val != 0 else (100.0 if c_val != 0 else 0.0)

        # Favorable logic:
        # If is_expense: decrease in cost (delta < 0) is Favorable!
        # If revenue/profit: increase (delta > 0) is Favorable!
        if sm["is_expense"]:
            is_fav = delta_amt <= 0
        else:
            is_fav = delta_amt >= 0

        is_mat = abs(delta_amt) >= min_amount and (b_val == 0 or abs(delta_pct) >= min_pct)

        summary_variances.append({
            "metric": m_key,
            "label": sm["label"],
            "baseline_amount": b_val,
            "current_amount": c_val,
            "delta_amount": delta_amt,
            "delta_pct": delta_pct,
            "is_favorable": is_fav,
            "is_material": is_mat,
        })

    # Line item category level variances
    category_variances = []

    sections = pnl["sections"]
    section_keys = [
        ("revenue", "Revenue", False),
        ("cogs", "COGS", True),
        ("payroll", "Payroll", True),
        ("opex", "Operating Expenses", True),
    ]

    for sec_id, bucket_name, is_expense in section_keys:
        sec = sections.get(sec_id, {})
        lines = sec.get("lines", [])

        for l in lines:
            cat_name = l["category"]
            b_val = l["by_month"].get(baseline_month, 0.0)
            c_val = l["by_month"].get(current_month, 0.0)
            delta_amt = round(c_val - b_val, 2)
            delta_pct = round((delta_amt / b_val * 100), 2) if b_val != 0 else (100.0 if c_val != 0 else 0.0)

            # Polarity
            if is_expense:
                is_fav = delta_amt <= 0
            else:
                is_fav = delta_amt >= 0

            is_mat = abs(delta_amt) >= min_amount and (b_val == 0 or abs(delta_pct) >= min_pct)

            if only_material and not is_mat:
                continue

            # Fetch driving transactions from the current month
            # Parse year and month
            curr_y, curr_m = [int(x) for x in current_month.split("-")]
            txns_query = (
                db.query(Transaction)
                .filter(
                    Transaction.category == cat_name,
                    extract("year", Transaction.date) == curr_y,
                    extract("month", Transaction.date) == curr_m,
                )
            )
            if tenant_id is not None:
                txns_query = txns_query.filter(Transaction.tenant_id == tenant_id)

            txns = (
                txns_query
                .order_by(desc(func.abs(Transaction.amount)))
                .limit(5)
                .all()
            )

            drivers = []
            driver_counterparties = set()
            for t in txns_query:
                drivers.append({
                    "id": t.id,
                    "transaction_code": t.transaction_code or f"TX-{t.id}",
                    "date": str(t.date),
                    "description": t.description,
                    "counterparty": t.counterparty or "Unknown",
                    "amount": round(t.amount, 2),
                    "method": t.method,
                })
                if t.counterparty:
                    driver_counterparties.add(t.counterparty)

            # Generate narrative explanation citing concrete drivers
            direction = "increased" if delta_amt > 0 else "decreased"
            status_text = "Favorable" if is_fav else "Unfavorable"
            counterparty_list = ", ".join(list(driver_counterparties)[:3]) if driver_counterparties else "routine activity"

            explanation = (
                f"{cat_name} {direction} by ${abs(delta_amt):,.2f} ({delta_pct:+.1f}%) "
                f"from {baseline_month} (${b_val:,.2f}) to {current_month} (${c_val:,.2f}). "
                f"This {status_text.lower()} shift was primarily driven by transactions involving {counterparty_list}."
            )

            category_variances.append({
                "category": cat_name,
                "pnl_bucket": bucket_name,
                "baseline_amount": b_val,
                "current_amount": c_val,
                "delta_amount": delta_amt,
                "delta_pct": delta_pct,
                "is_favorable": is_fav,
                "is_material": is_mat,
                "explanation": explanation,
                "drivers": drivers,
            })

    # Sort category variances by absolute delta descending (highest impact first)
    category_variances.sort(key=lambda x: abs(x["delta_amount"]), reverse=True)

    return {
        "baseline_month": baseline_month,
        "current_month": current_month,
        "available_months": available_months,
        "thresholds": {
            "min_amount": min_amount,
            "min_pct": min_pct,
            "only_material": only_material,
        },
        "summary_variances": summary_variances,
        "category_variances": category_variances,
    }
