"use client";

import React, { useState, useEffect } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  ShieldCheck,
  HelpCircle,
  FileSpreadsheet,
  Download,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface PnLLine {
  category: string;
  by_month: Record<string, number>;
  total: number;
}

interface PnLSection {
  bucket: string;
  monthly_totals: Record<string, number>;
  grand_total: number;
  lines: PnLLine[];
}

interface PnLSummaryItem {
  revenue: number;
  cogs: number;
  gross_profit: number;
  gross_margin_pct: number;
  payroll: number;
  opex: number;
  total_operating_expenses: number;
  operating_profit: number;
  operating_margin_pct: number;
}

interface PnLData {
  months: string[];
  summary: Record<string, PnLSummaryItem>;
  sections: {
    revenue: PnLSection;
    cogs: PnLSection;
    payroll: PnLSection;
    opex: PnLSection;
    non_pnl: PnLSection;
  };
}

interface PnLStatementProps {
  apiUrl?: string;
  onDataChanged?: () => void;
  onMetricClick?: (metricKey: string, metricLabel: string, month?: string) => void;
}

/**
 * Presentation-only animated currency renderer that smoothly counts up to
 * the exact backend number on initial load, while respecting prefers-reduced-motion.
 * The backend remains the single source of truth.
 */
function AnimatedFinancialValue({
  value,
  className = "",
}: {
  value: number;
  className?: string;
}) {
  const shouldReduceMotion = useReducedMotion();
  const [displayValue, setDisplayValue] = useState(shouldReduceMotion ? value : 0);

  useEffect(() => {
    if (shouldReduceMotion) {
      setDisplayValue(value);
      return;
    }

    let startTimestamp: number | null = null;
    const duration = 500; // 0.5s smooth count-up
    const startVal = 0;
    const endVal = value;

    let reqId: number;

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      // easeOutExpo for natural fintech decelerating count-up
      const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setDisplayValue(startVal + (endVal - startVal) * ease);
      if (progress < 1) {
        reqId = requestAnimationFrame(step);
      } else {
        setDisplayValue(endVal); // Ensures exact backend precision
      }
    };

    reqId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(reqId);
  }, [value, shouldReduceMotion]);

  const formatted = Math.abs(displayValue).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const prefix = displayValue < 0 ? "-$" : "$";

  return <span className={className}>{prefix}{formatted}</span>;
}

export default function PnLStatement({ onDataChanged, onMetricClick }: PnLStatementProps) {
  const shouldReduceMotion = useReducedMotion();
  const [data, setData] = useState<PnLData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Section collapse states
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    revenue: true,
    cogs: true,
    payroll: true,
    opex: true,
    non_pnl: false,
  });

  const fetchPnL = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/pnl");
      if (!res.ok) {
        throw new Error("Failed to load P&L statement data.");
      }
      const json = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || "An error occurred while fetching P&L data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPnL();
  }, []);

  const toggleSection = (secKey: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [secKey]: !prev[secKey],
    }));
  };

  const formatCurrency = (amount: number | undefined) => {
    if (amount === undefined || isNaN(amount)) return "$0.00";
    const formatted = Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  const formatPercent = (pct: number | undefined) => {
    if (pct === undefined || isNaN(pct)) return "0.0%";
    return `${pct.toFixed(1)}%`;
  };

  const handleExportCSV = () => {
    if (!data) return;

    const escapeCSV = (val: string | number) => `"${String(val).replace(/"/g, '""')}"`;

    const header = [escapeCSV("Line Item"), ...data.months.map(escapeCSV), escapeCSV("Total")].join(",");
    const rows: string[] = [header];

    const addSectionToCSV = (title: string, section: PnLSection) => {
      rows.push(escapeCSV(title.toUpperCase()));
      section.lines.forEach((l) => {
        const lineRow = [
          escapeCSV(l.category),
          ...data.months.map((m) => (l.by_month[m] || 0).toFixed(2)),
          l.total.toFixed(2),
        ];
        rows.push(lineRow.join(","));
      });
      const totalRow = [
        escapeCSV(`Total ${title}`),
        ...data.months.map((m) => (section.monthly_totals[m] || 0).toFixed(2)),
        section.grand_total.toFixed(2),
      ];
      rows.push(totalRow.join(","));
    };

    addSectionToCSV("Revenue", data.sections.revenue);
    addSectionToCSV("Cost of Goods Sold (COGS)", data.sections.cogs);

    // Gross Profit row
    const grossProfitRow = [
      escapeCSV("Gross Profit"),
      ...data.months.map((m) => (data.summary[m]?.gross_profit || 0).toFixed(2)),
      data.months.reduce((acc, m) => acc + (data.summary[m]?.gross_profit || 0), 0).toFixed(2),
    ];
    rows.push(grossProfitRow.join(","));

    addSectionToCSV("Payroll & Labor", data.sections.payroll);
    addSectionToCSV("Operating Expenses (OpEx)", data.sections.opex);

    // Operating Profit row
    const operatingProfitRow = [
      escapeCSV("Operating Profit"),
      ...data.months.map((m) => (data.summary[m]?.operating_profit || 0).toFixed(2)),
      data.months.reduce((acc, m) => acc + (data.summary[m]?.operating_profit || 0), 0).toFixed(2),
    ];
    rows.push(operatingProfitRow.join(","));

    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `NYC_Restaurant_Co_PnL_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (loading && !data) {
    return (
      <div className="bg-[#ffffff] rounded-2xl p-12 border border-[var(--color-hairline)] text-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-[var(--color-primary)]" />
        <p className="text-sm font-medium text-[var(--color-body)]">
          Calculating monthly P&amp;L statement from bank transactions...
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 rounded-2xl p-8 border border-red-200 text-center space-y-3">
        <p className="text-sm text-red-800 font-medium">{error || "No P&L data available."}</p>
        <motion.button
          onClick={fetchPnL}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
          className="px-4 py-2 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold cursor-pointer"
        >
          Retry Calculation
        </motion.button>
      </div>
    );
  }

  const { months, sections, summary } = data;

  // Calculate combined multi-month totals for summary metrics
  const totalSummary = months.reduce(
    (acc, m) => {
      const s = summary[m] || {
        revenue: 0,
        cogs: 0,
        gross_profit: 0,
        gross_margin_pct: 0,
        payroll: 0,
        opex: 0,
        total_operating_expenses: 0,
        operating_profit: 0,
        operating_margin_pct: 0,
      };
      acc.revenue += s.revenue;
      acc.cogs += s.cogs;
      acc.gross_profit += s.gross_profit;
      acc.payroll += s.payroll;
      acc.opex += s.opex;
      acc.total_operating_expenses += s.total_operating_expenses;
      acc.operating_profit += s.operating_profit;
      return acc;
    },
    {
      revenue: 0,
      cogs: 0,
      gross_profit: 0,
      payroll: 0,
      opex: 0,
      total_operating_expenses: 0,
      operating_profit: 0,
      gross_margin_pct: 0,
      operating_margin_pct: 0,
    }
  );

  totalSummary.gross_margin_pct =
    totalSummary.revenue > 0 ? (totalSummary.gross_profit / totalSummary.revenue) * 100 : 0;
  totalSummary.operating_margin_pct =
    totalSummary.revenue > 0 ? (totalSummary.operating_profit / totalSummary.revenue) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header with Title, Determinism Badge, and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-[var(--color-ink)]">
              Monthly Profit &amp; Loss Statement
            </h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[var(--color-brand-mint)]/40 border border-[var(--color-brand-mint)] text-[11px] font-semibold text-emerald-950">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
              100% Deterministic Engine
            </span>
          </div>
          <p className="text-xs text-[var(--color-muted)] mt-0.5">
            Standard GAAP hierarchy: Revenue → COGS → Gross Profit → Operating Expenses → Operating Profit.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <motion.button
            onClick={handleExportCSV}
            whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
            className="px-3.5 py-2 rounded-xl bg-[var(--color-surface-soft)] border border-[var(--color-hairline)] text-xs font-semibold text-[var(--color-ink)] hover:bg-[var(--color-surface-strong)] transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Statement CSV</span>
          </motion.button>
          <motion.button
            onClick={fetchPnL}
            whileHover={shouldReduceMotion ? undefined : { scale: 1.05 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.95 }}
            className="p-1.5 rounded-lg border border-[var(--color-hairline)] bg-[#ffffff] text-[var(--color-muted)] hover:text-[var(--color-ink)] transition-all cursor-pointer"
            title="Refresh calculations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </div>

      {/* Top Level Metric Cards with Presentation Animated Currency */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Revenue */}
        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.05 }}
          onClick={() => onMetricClick?.("revenue", "Total Period Revenue")}
          className="bg-[#ffffff] rounded-xl p-5 border border-[var(--color-hairline)] shadow-xs hover:border-stone-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[var(--color-muted)] font-medium">
            <span>Total Period Revenue</span>
            <span className="text-[10px] text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity">Trace →</span>
          </div>
          <div className="text-2xl font-bold text-[var(--color-ink)] mt-1.5 font-mono">
            <AnimatedFinancialValue value={totalSummary.revenue} />
          </div>
          <div className="text-[11px] text-emerald-700 font-medium mt-1 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            <span>Top-line food, bar &amp; catering</span>
          </div>
        </motion.div>

        {/* Gross Profit & Margin */}
        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.1 }}
          onClick={() => onMetricClick?.("gross_profit", "Gross Profit (Margin %)")}
          className="bg-[#ffffff] rounded-xl p-5 border border-[var(--color-hairline)] shadow-xs hover:border-stone-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[var(--color-muted)] font-medium">
            <span>Gross Profit (Margin %)</span>
            <span className="text-[10px] text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity">Trace →</span>
          </div>
          <div className="text-2xl font-bold text-emerald-800 mt-1.5 font-mono">
            <AnimatedFinancialValue value={totalSummary.gross_profit} />
          </div>
          <div className="text-[11px] text-[var(--color-muted)] font-medium mt-1 flex items-center gap-1">
            <span className="px-1.5 py-0.5 rounded-md bg-[var(--color-brand-mint)]/40 text-emerald-950 font-bold font-mono">
              {totalSummary.gross_margin_pct.toFixed(1)}% margin
            </span>
            <span>(Rev - COGS)</span>
          </div>
        </motion.div>

        {/* Total Operating Expenses */}
        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.15 }}
          onClick={() => onMetricClick?.("operating_expenses", "Total Operating Expenses")}
          className="bg-[#ffffff] rounded-xl p-5 border border-[var(--color-hairline)] shadow-xs hover:border-stone-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[var(--color-muted)] font-medium">
            <span>Total Operating Expenses</span>
            <span className="text-[10px] text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity">Trace →</span>
          </div>
          <div className="text-2xl font-bold text-slate-800 mt-1.5 font-mono">
            <AnimatedFinancialValue value={totalSummary.total_operating_expenses} />
          </div>
          <div className="text-[11px] text-[var(--color-muted)] mt-1">
            Payroll {formatCurrency(totalSummary.payroll)} + OpEx {formatCurrency(totalSummary.opex)}
          </div>
        </motion.div>

        {/* Operating Profit & Margin */}
        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.2 }}
          onClick={() => onMetricClick?.("operating_profit", "Operating Profit (EBITDA)")}
          className="bg-[#ffffff] rounded-xl p-5 border border-[var(--color-hairline)] shadow-xs hover:border-stone-400 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-xs text-[var(--color-muted)] font-medium">
            <span>Operating Profit (EBITDA)</span>
            <span className="text-[10px] text-stone-700 opacity-0 group-hover:opacity-100 transition-opacity">Trace →</span>
          </div>
          <div
            className={`text-2xl font-bold mt-1.5 font-mono ${
              totalSummary.operating_profit >= 0 ? "text-emerald-700" : "text-red-700"
            }`}
          >
            <AnimatedFinancialValue value={totalSummary.operating_profit} />
          </div>
          <div className="text-[11px] font-medium mt-1 flex items-center gap-1">
            <span
              className={`px-1.5 py-0.5 rounded-md font-bold font-mono ${
                totalSummary.operating_margin_pct >= 0
                  ? "bg-[var(--color-brand-mint)]/40 text-emerald-950"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {totalSummary.operating_margin_pct.toFixed(1)}% operating margin
            </span>
          </div>
        </motion.div>
      </div>

      {/* Main Hierarchical P&L Grid */}
      <div className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[var(--color-surface-soft)] border-b border-[var(--color-hairline)] text-[var(--color-muted)] uppercase tracking-wider font-semibold">
                <th className="py-3.5 px-4 min-w-[240px]">Financial Statement Line Item</th>
                {months.map((m) => (
                  <th key={m} className="py-3.5 px-4 text-right min-w-[130px] font-mono">
                    {m}
                  </th>
                ))}
                <th className="py-3.5 px-4 text-right min-w-[140px] font-mono bg-[var(--color-canvas)]">
                  Total Period
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-hairline)] font-medium">
              {/* ---------------- 1. REVENUE SECTION ---------------- */}
              <tr
                onClick={() => toggleSection("revenue")}
                className="bg-[var(--color-canvas)] cursor-pointer hover:bg-[var(--color-surface-card)] transition-colors select-none"
              >
                <td className="py-3 px-4 font-bold text-[var(--color-ink)] flex items-center gap-1.5">
                  {expandedSections.revenue ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  <span>REVENUE / SALES</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-3 px-4 text-right font-mono font-bold text-emerald-700">
                    {formatCurrency(sections.revenue.monthly_totals[m])}
                  </td>
                ))}
                <td className="py-3 px-4 text-right font-mono font-bold text-emerald-800 bg-[var(--color-canvas)]">
                  {formatCurrency(sections.revenue.grand_total)}
                </td>
              </tr>
              {expandedSections.revenue &&
                sections.revenue.lines.map((l) => (
                  <tr key={l.category} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                    <td className="py-2.5 pl-8 pr-4 text-[var(--color-body)]">{l.category}</td>
                    {months.map((m) => (
                      <td key={m} className="py-2.5 px-4 text-right font-mono text-[var(--color-body)]">
                        {formatCurrency(l.by_month[m] || 0)}
                      </td>
                    ))}
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-[var(--color-ink)] bg-[var(--color-canvas)]/30">
                      {formatCurrency(l.total)}
                    </td>
                  </tr>
                ))}

              {/* ---------------- 2. COGS SECTION ---------------- */}
              <tr
                onClick={() => toggleSection("cogs")}
                className="bg-[var(--color-canvas)] cursor-pointer hover:bg-[var(--color-surface-card)] transition-colors select-none"
              >
                <td className="py-3 px-4 font-bold text-[var(--color-ink)] flex items-center gap-1.5">
                  {expandedSections.cogs ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  <span>COST OF GOODS SOLD (COGS)</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-3 px-4 text-right font-mono font-bold text-slate-800">
                    {formatCurrency(sections.cogs.monthly_totals[m])}
                  </td>
                ))}
                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900 bg-[var(--color-canvas)]">
                  {formatCurrency(sections.cogs.grand_total)}
                </td>
              </tr>
              {expandedSections.cogs &&
                sections.cogs.lines.map((l) => (
                  <tr key={l.category} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                    <td className="py-2.5 pl-8 pr-4 text-[var(--color-body)]">{l.category}</td>
                    {months.map((m) => (
                      <td key={m} className="py-2.5 px-4 text-right font-mono text-[var(--color-body)]">
                        {formatCurrency(l.by_month[m] || 0)}
                      </td>
                    ))}
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-[var(--color-ink)] bg-[var(--color-canvas)]/30">
                      {formatCurrency(l.total)}
                    </td>
                  </tr>
                ))}

              {/* ---------------- 3. GROSS PROFIT ROW (CALCULATED) ---------------- */}
              <tr className="bg-[var(--color-brand-mint)]/15 border-y-2 border-[var(--color-brand-mint)]/60 font-bold">
                <td className="py-3.5 px-4 text-emerald-950 flex items-center justify-between">
                  <span>GROSS PROFIT (Revenue - COGS)</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-3.5 px-4 text-right font-mono text-emerald-900">
                    {formatCurrency(summary[m]?.gross_profit)}
                    <span className="block text-[10px] font-normal text-emerald-700">
                      {formatPercent(summary[m]?.gross_margin_pct)} margin
                    </span>
                  </td>
                ))}
                <td className="py-3.5 px-4 text-right font-mono text-emerald-950 bg-[var(--color-brand-mint)]/20">
                  {formatCurrency(totalSummary.gross_profit)}
                  <span className="block text-[10px] font-normal text-emerald-800">
                    {formatPercent(totalSummary.gross_margin_pct)} margin
                  </span>
                </td>
              </tr>

              {/* ---------------- 4. PAYROLL SECTION ---------------- */}
              <tr
                onClick={() => toggleSection("payroll")}
                className="bg-[var(--color-canvas)] cursor-pointer hover:bg-[var(--color-surface-card)] transition-colors select-none"
              >
                <td className="py-3 px-4 font-bold text-[var(--color-ink)] flex items-center gap-1.5">
                  {expandedSections.payroll ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  <span>PAYROLL &amp; LABOR</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-3 px-4 text-right font-mono font-bold text-slate-800">
                    {formatCurrency(sections.payroll.monthly_totals[m])}
                  </td>
                ))}
                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900 bg-[var(--color-canvas)]">
                  {formatCurrency(sections.payroll.grand_total)}
                </td>
              </tr>
              {expandedSections.payroll &&
                sections.payroll.lines.map((l) => (
                  <tr key={l.category} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                    <td className="py-2.5 pl-8 pr-4 text-[var(--color-body)]">{l.category}</td>
                    {months.map((m) => (
                      <td key={m} className="py-2.5 px-4 text-right font-mono text-[var(--color-body)]">
                        {formatCurrency(l.by_month[m] || 0)}
                      </td>
                    ))}
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-[var(--color-ink)] bg-[var(--color-canvas)]/30">
                      {formatCurrency(l.total)}
                    </td>
                  </tr>
                ))}

              {/* ---------------- 5. OPERATING EXPENSES (OPEX) SECTION ---------------- */}
              <tr
                onClick={() => toggleSection("opex")}
                className="bg-[var(--color-canvas)] cursor-pointer hover:bg-[var(--color-surface-card)] transition-colors select-none"
              >
                <td className="py-3 px-4 font-bold text-[var(--color-ink)] flex items-center gap-1.5">
                  {expandedSections.opex ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  <span>OPERATING EXPENSES (OPEX)</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-3 px-4 text-right font-mono font-bold text-slate-800">
                    {formatCurrency(sections.opex.monthly_totals[m])}
                  </td>
                ))}
                <td className="py-3 px-4 text-right font-mono font-bold text-slate-900 bg-[var(--color-canvas)]">
                  {formatCurrency(sections.opex.grand_total)}
                </td>
              </tr>
              {expandedSections.opex &&
                sections.opex.lines.map((l) => (
                  <tr key={l.category} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                    <td className="py-2.5 pl-8 pr-4 text-[var(--color-body)]">{l.category}</td>
                    {months.map((m) => (
                      <td key={m} className="py-2.5 px-4 text-right font-mono text-[var(--color-body)]">
                        {formatCurrency(l.by_month[m] || 0)}
                      </td>
                    ))}
                    <td className="py-2.5 px-4 text-right font-mono font-semibold text-[var(--color-ink)] bg-[var(--color-canvas)]/30">
                      {formatCurrency(l.total)}
                    </td>
                  </tr>
                ))}

              {/* ---------------- 6. TOTAL OPEX SUB-TOTAL ---------------- */}
              <tr className="bg-[var(--color-surface-soft)] font-semibold border-t border-[var(--color-hairline)] text-slate-800">
                <td className="py-3 px-4 pl-8">Total Operating Costs (Payroll + OpEx)</td>
                {months.map((m) => (
                  <td key={m} className="py-3 px-4 text-right font-mono">
                    {formatCurrency(summary[m]?.total_operating_expenses)}
                  </td>
                ))}
                <td className="py-3 px-4 text-right font-mono font-bold bg-[var(--color-surface-soft)]">
                  {formatCurrency(totalSummary.total_operating_expenses)}
                </td>
              </tr>

              {/* ---------------- 7. OPERATING PROFIT (EBITDA) ---------------- */}
              <tr className="bg-[var(--color-surface-dark)] text-white font-bold border-t-2 border-[var(--color-primary)]">
                <td className="py-4 px-4 text-sm tracking-wide">
                  OPERATING PROFIT (Gross Profit - Total OpEx)
                </td>
                {months.map((m) => {
                  const val = summary[m]?.operating_profit || 0;
                  return (
                    <td
                      key={m}
                      className={`py-4 px-4 text-right font-mono text-sm ${
                        val >= 0 ? "text-emerald-400 font-bold" : "text-red-400 font-bold"
                      }`}
                    >
                      {formatCurrency(val)}
                      <span className="block text-[10px] font-normal text-slate-300">
                        {formatPercent(summary[m]?.operating_margin_pct)} margin
                      </span>
                    </td>
                  );
                })}
                <td
                  className={`py-4 px-4 text-right font-mono text-sm bg-black/40 ${
                    totalSummary.operating_profit >= 0 ? "text-emerald-400 font-bold" : "text-red-400 font-bold"
                  }`}
                >
                  {formatCurrency(totalSummary.operating_profit)}
                  <span className="block text-[10px] font-normal text-slate-300">
                    {formatPercent(totalSummary.operating_margin_pct)} margin
                  </span>
                </td>
              </tr>

              {/* ---------------- 8. NON-P&L / BALANCE SHEET (OPTIONAL) ---------------- */}
              <tr
                onClick={() => toggleSection("non_pnl")}
                className="bg-slate-50 cursor-pointer hover:bg-slate-100 transition-colors select-none text-[var(--color-muted)]"
              >
                <td className="py-2.5 px-4 font-semibold text-xs flex items-center gap-1.5">
                  {expandedSections.non_pnl ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  <span>Non-P&amp;L Transactions (CapEx / Sales Tax Remittance)</span>
                </td>
                {months.map((m) => (
                  <td key={m} className="py-2.5 px-4 text-right font-mono text-xs">
                    {formatCurrency(sections.non_pnl.monthly_totals[m])}
                  </td>
                ))}
                <td className="py-2.5 px-4 text-right font-mono text-xs bg-slate-100">
                  {formatCurrency(sections.non_pnl.grand_total)}
                </td>
              </tr>
              {expandedSections.non_pnl &&
                sections.non_pnl.lines.map((l) => (
                  <tr key={l.category} className="hover:bg-slate-50 text-[var(--color-muted)]">
                    <td className="py-2 pl-8 pr-4 text-xs italic">{l.category}</td>
                    {months.map((m) => (
                      <td key={m} className="py-2 px-4 text-right font-mono text-xs">
                        {formatCurrency(l.by_month[m] || 0)}
                      </td>
                    ))}
                    <td className="py-2 px-4 text-right font-mono text-xs bg-slate-50">
                      {formatCurrency(l.total)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
