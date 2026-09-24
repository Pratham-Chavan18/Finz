from typing import Dict, Any, List, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.transaction import Transaction


def generate_monthly_pnl(
    db: Session,
    start_month: Optional[str] = None,
    end_month: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Computes a deterministic monthly P&L statement from categorized transactions.
    Zero LLM involvement in any arithmetic path.
    Scoped to tenant_id when provided.

    Returns:
      - months: List of distinct sorted YYYY-MM strings
      - summary: Monthly and total KPIs (Revenue, COGS, Gross Profit, Payroll, OpEx, Operating Profit)
      - sections: Hierarchical breakdowns for Revenue, COGS, Payroll, OpEx, and Non-P&L
    """
    query = db.query(Transaction).filter(Transaction.category.isnot(None))
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)

    transactions = query.all()

    # Data structures for accumulation
    # bucket_data[pnl_bucket][category][month] = float
    bucket_data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    all_months_set = set()

    for t in transactions:
        month_str = t.date.strftime("%Y-%m")
        if start_month and month_str < start_month:
            continue
        if end_month and month_str > end_month:
            continue

        all_months_set.add(month_str)
        bucket = t.pnl_bucket or "Operating Expenses"
        cat = t.category or "Uncategorized"
        bucket_data[bucket][cat][month_str] += float(t.amount)

    months = sorted(list(all_months_set))

    # Helper to calculate line items
    def build_section(bucket_name: str, is_expense: bool = True) -> Dict[str, Any]:
        cat_dict = bucket_data.get(bucket_name, {})
        lines = []
        section_monthly_totals = defaultdict(float)
        section_grand_total = 0.0

        for cat, month_map in sorted(cat_dict.items()):
            line_by_month = {}
            line_total = 0.0

            for m in months:
                raw_amt = month_map.get(m, 0.0)
                # For expenses, convert negative outflow to positive display amount
                disp_amt = abs(raw_amt) if is_expense else raw_amt
                disp_amt = round(disp_amt, 2)
                line_by_month[m] = disp_amt
                line_total += disp_amt
                section_monthly_totals[m] += disp_amt

            line_total = round(line_total, 2)
            section_grand_total += line_total

            lines.append({
                "category": cat,
                "by_month": line_by_month,
                "total": line_total,
            })

        # Round section totals
        rounded_monthly_totals = {m: round(section_monthly_totals[m], 2) for m in months}
        rounded_grand_total = round(section_grand_total, 2)

        return {
            "bucket": bucket_name,
            "monthly_totals": rounded_monthly_totals,
            "grand_total": rounded_grand_total,
            "lines": lines,
        }

    # Build sections
    revenue_sec = build_section("Revenue", is_expense=False)
    cogs_sec = build_section("COGS", is_expense=True)
    payroll_sec = build_section("Payroll", is_expense=True)
    opex_sec = build_section("Operating Expenses", is_expense=True)
    non_pnl_sec = build_section("Non-P&L", is_expense=True)

    # Compute high-level monthly summaries & totals
    summary: Dict[str, Any] = {}

    total_revenue = 0.0
    total_cogs = 0.0
    total_gross_profit = 0.0
    total_payroll = 0.0
    total_opex = 0.0
    total_all_opex = 0.0
    total_operating_profit = 0.0

    for m in months:
        rev = revenue_sec["monthly_totals"].get(m, 0.0)
        cogs = cogs_sec["monthly_totals"].get(m, 0.0)
        gross_profit = round(rev - cogs, 2)
        gross_margin_pct = round((gross_profit / rev * 100), 2) if rev > 0 else 0.0

        payroll = payroll_sec["monthly_totals"].get(m, 0.0)
        opex = opex_sec["monthly_totals"].get(m, 0.0)
        total_operating_exp = round(payroll + opex, 2)

        operating_profit = round(gross_profit - total_operating_exp, 2)
        operating_margin_pct = round((operating_profit / rev * 100), 2) if rev > 0 else 0.0

        summary[m] = {
            "revenue": rev,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "gross_margin_pct": gross_margin_pct,
            "payroll": payroll,
            "opex": opex,
            "total_operating_expenses": total_operating_exp,
            "operating_profit": operating_profit,
            "operating_margin_pct": operating_margin_pct,
        }

        total_revenue += rev
        total_cogs += cogs
        total_gross_profit += gross_profit
        total_payroll += payroll
        total_opex += opex
        total_all_opex += total_operating_exp
        total_operating_profit += operating_profit

    # Grand Totals
    total_revenue = round(total_revenue, 2)
    total_cogs = round(total_cogs, 2)
    total_gross_profit = round(total_gross_profit, 2)
    total_payroll = round(total_payroll, 2)
    total_opex = round(total_opex, 2)
    total_all_opex = round(total_all_opex, 2)
    total_operating_profit = round(total_operating_profit, 2)

    total_gross_margin = (
        round((total_gross_profit / total_revenue * 100), 2) if total_revenue > 0 else 0.0
    )
    total_operating_margin = (
        round((total_operating_profit / total_revenue * 100), 2) if total_revenue > 0 else 0.0
    )

    summary["total"] = {
        "revenue": total_revenue,
        "cogs": total_cogs,
        "gross_profit": total_gross_profit,
        "gross_margin_pct": total_gross_margin,
        "payroll": total_payroll,
        "opex": total_opex,
        "total_operating_expenses": total_all_opex,
        "operating_profit": total_operating_profit,
        "operating_margin_pct": total_operating_margin,
    }

    return {
        "months": months,
        "summary": summary,
        "sections": {
            "revenue": revenue_sec,
            "cogs": cogs_sec,
            "payroll": payroll_sec,
            "opex": opex_sec,
            "non_pnl": non_pnl_sec,
        },
    }
