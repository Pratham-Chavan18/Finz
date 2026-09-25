from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from app.models.transaction import Transaction
from app.services.categorization import CHART_OF_ACCOUNTS


def generate_monthly_pnl(
    db: Session,
    start_month: Optional[str] = None,
    end_month: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Computes a deterministic monthly P&L statement from categorized transactions using Decimal precision.
    Zero LLM involvement in any arithmetic path.
    Scoped to tenant_id when provided.

    Uncategorized transactions are never silently dropped; they are explicitly tracked and surfaced
    with their count, net dollar amount, and monthly breakdown.

    Returns:
      - months: List of distinct sorted YYYY-MM strings
      - summary: Monthly and total KPIs (Revenue, COGS, Gross Profit, Payroll, OpEx, Operating Profit)
      - sections: Hierarchical breakdowns for Revenue, COGS, Payroll, OpEx, and Non-P&L
      - uncategorized: Explicit metadata for uncategorized/pending transactions
    """
    query = db.query(Transaction)
    if tenant_id is not None:
        query = query.filter(Transaction.tenant_id == tenant_id)

    all_transactions = query.all()

    # Data structures for accumulation using Decimal
    # bucket_data[pnl_bucket][category][month] = Decimal
    bucket_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: Decimal("0.00"))))
    all_months_set = set()

    uncategorized_txns = []
    uncategorized_by_month = defaultdict(lambda: Decimal("0.00"))
    uncategorized_count_by_month = defaultdict(int)

    non_pnl_cats = {c["category"] for c in CHART_OF_ACCOUNTS if c.get("pnl_bucket") == "Non-P&L"}

    for t in all_transactions:
        month_str = t.date.strftime("%Y-%m")
        if start_month and month_str < start_month:
            continue
        if end_month and month_str > end_month:
            continue

        all_months_set.add(month_str)
        cat = (t.category or "").strip()
        bucket = (t.pnl_bucket or "").strip()
        amt = Decimal(str(t.amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Check for uncategorized
        if not cat or cat.lower() == "uncategorized":
            uncategorized_txns.append(t)
            uncategorized_by_month[month_str] += amt
            uncategorized_count_by_month[month_str] += 1
            continue

        # Non-P&L
        if bucket == "Non-P&L" or cat in non_pnl_cats:
            bucket_data["Non-P&L"][cat][month_str] += amt
            continue

        # P&L Buckets
        effective_bucket = bucket if bucket in ("Revenue", "COGS", "Payroll", "Operating Expenses") else "Operating Expenses"
        bucket_data[effective_bucket][cat][month_str] += amt

    months = sorted(list(all_months_set))

    # Helper to calculate line items with Decimal
    def build_section(bucket_name: str, is_expense: bool = True) -> Dict[str, Any]:
        cat_dict = bucket_data.get(bucket_name, {})
        lines = []
        section_monthly_totals = defaultdict(lambda: Decimal("0.00"))
        section_grand_total = Decimal("0.00")

        for cat, month_map in sorted(cat_dict.items()):
            line_by_month = {}
            line_total = Decimal("0.00")

            for m in months:
                raw_amt = month_map.get(m, Decimal("0.00"))
                # For expenses, convert negative outflow to positive display amount
                disp_amt = abs(raw_amt) if is_expense else raw_amt
                disp_amt = disp_amt.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                line_by_month[m] = float(disp_amt)
                line_total += disp_amt
                section_monthly_totals[m] += disp_amt

            line_total = line_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            section_grand_total += line_total

            lines.append({
                "category": cat,
                "by_month": line_by_month,
                "total": float(line_total),
            })

        # Quantize section totals
        quantized_monthly_totals = {
            m: float(section_monthly_totals[m].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            for m in months
        }
        quantized_grand_total = float(section_grand_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        return {
            "bucket": bucket_name,
            "monthly_totals": quantized_monthly_totals,
            "grand_total": quantized_grand_total,
            "lines": lines,
            "_raw_monthly_totals": section_monthly_totals,
            "_raw_grand_total": section_grand_total,
        }

    # Build sections
    revenue_sec = build_section("Revenue", is_expense=False)
    cogs_sec = build_section("COGS", is_expense=True)
    payroll_sec = build_section("Payroll", is_expense=True)
    opex_sec = build_section("Operating Expenses", is_expense=True)
    non_pnl_sec = build_section("Non-P&L", is_expense=True)

    # Compute high-level monthly summaries & totals in Decimal
    summary: Dict[str, Any] = {}

    total_revenue_dec = Decimal("0.00")
    total_cogs_dec = Decimal("0.00")
    total_gross_profit_dec = Decimal("0.00")
    total_payroll_dec = Decimal("0.00")
    total_opex_dec = Decimal("0.00")
    total_all_opex_dec = Decimal("0.00")
    total_operating_profit_dec = Decimal("0.00")

    for m in months:
        rev_dec = revenue_sec["_raw_monthly_totals"].get(m, Decimal("0.00"))
        cogs_dec = cogs_sec["_raw_monthly_totals"].get(m, Decimal("0.00"))
        gross_profit_dec = (rev_dec - cogs_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gross_margin_pct = (
            float(((gross_profit_dec / rev_dec) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            if rev_dec > Decimal("0.00") else 0.0
        )

        payroll_dec = payroll_sec["_raw_monthly_totals"].get(m, Decimal("0.00"))
        opex_dec = opex_sec["_raw_monthly_totals"].get(m, Decimal("0.00"))
        total_operating_exp_dec = (payroll_dec + opex_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        operating_profit_dec = (gross_profit_dec - total_operating_exp_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        operating_margin_pct = (
            float(((operating_profit_dec / rev_dec) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            if rev_dec > Decimal("0.00") else 0.0
        )

        summary[m] = {
            "revenue": float(rev_dec),
            "cogs": float(cogs_dec),
            "gross_profit": float(gross_profit_dec),
            "gross_margin_pct": gross_margin_pct,
            "payroll": float(payroll_dec),
            "opex": float(opex_dec),
            "total_operating_expenses": float(total_operating_exp_dec),
            "operating_profit": float(operating_profit_dec),
            "operating_margin_pct": operating_margin_pct,
        }

        total_revenue_dec += rev_dec
        total_cogs_dec += cogs_dec
        total_gross_profit_dec += gross_profit_dec
        total_payroll_dec += payroll_dec
        total_opex_dec += opex_dec
        total_all_opex_dec += total_operating_exp_dec
        total_operating_profit_dec += operating_profit_dec

    # Grand Margins
    grand_gross_margin = (
        float(((total_gross_profit_dec / total_revenue_dec) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if total_revenue_dec > Decimal("0.00") else 0.0
    )
    grand_operating_margin = (
        float(((total_operating_profit_dec / total_revenue_dec) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if total_revenue_dec > Decimal("0.00") else 0.0
    )

    summary["total"] = {
        "revenue": float(total_revenue_dec.quantize(Decimal("0.01"))),
        "cogs": float(total_cogs_dec.quantize(Decimal("0.01"))),
        "gross_profit": float(total_gross_profit_dec.quantize(Decimal("0.01"))),
        "gross_margin_pct": grand_gross_margin,
        "payroll": float(total_payroll_dec.quantize(Decimal("0.01"))),
        "opex": float(total_opex_dec.quantize(Decimal("0.01"))),
        "total_operating_expenses": float(total_all_opex_dec.quantize(Decimal("0.01"))),
        "operating_profit": float(total_operating_profit_dec.quantize(Decimal("0.01"))),
        "operating_margin_pct": grand_operating_margin,
    }

    # Clean internal raw structures
    for sec in (revenue_sec, cogs_sec, payroll_sec, opex_sec, non_pnl_sec):
        sec.pop("_raw_monthly_totals", None)
        sec.pop("_raw_grand_total", None)

    # Compute explicit Uncategorized / Pending Review summary
    total_uncategorized_dec = sum(uncategorized_by_month.values(), Decimal("0.00")).quantize(Decimal("0.01"))

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
        "uncategorized": {
            "title": "Uncategorized / Pending Review",
            "count": len(uncategorized_txns),
            "total_count": len(uncategorized_txns),
            "total_amount": float(total_uncategorized_dec),
            "by_month": {m: float(uncategorized_by_month[m].quantize(Decimal("0.01"))) for m in months},
            "count_by_month": {m: uncategorized_count_by_month[m] for m in months},
            "is_zero": len(uncategorized_txns) == 0,
        },
    }
