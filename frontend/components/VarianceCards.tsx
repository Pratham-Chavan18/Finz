"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  AlertCircle,
  Filter,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  Sparkles,
  Layers,
  ArrowRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface DriverTransaction {
  id: number;
  transaction_code: string;
  date: string;
  description: string;
  counterparty: string;
  amount: number;
  method: string | null;
}

interface CategoryVarianceItem {
  category: string;
  pnl_bucket: string;
  baseline_amount: number;
  current_amount: number;
  delta_amount: number;
  delta_pct: number;
  is_favorable: boolean;
  is_material: boolean;
  explanation: string;
  drivers: DriverTransaction[];
}

interface SummaryVarianceItem {
  metric: string;
  label: string;
  baseline_amount: number;
  current_amount: number;
  delta_amount: number;
  delta_pct: number;
  is_favorable: boolean;
  is_material: boolean;
}

interface VarianceResponse {
  baseline_month: string;
  current_month: string;
  available_months: string[];
  materiality_thresholds: {
    percentage: number;
    dollar: number;
  };
  summary_variances: SummaryVarianceItem[];
  category_variances: CategoryVarianceItem[];
}

interface VarianceCardsProps {
  apiUrl?: string;
  onNavigateToTransactions?: (category: string) => void;
}

export default function VarianceCards({
  onNavigateToTransactions,
}: VarianceCardsProps) {
  const shouldReduceMotion = useReducedMotion();
  const [data, setData] = useState<VarianceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedDrivers, setExpandedDrivers] = useState<Record<string, boolean>>({});

  // Month selection state
  const [baselineMonth, setBaselineMonth] = useState<string>("");
  const [currentMonth, setCurrentMonth] = useState<string>("");
  const [onlyMaterial, setOnlyMaterial] = useState<boolean>(true);

  const fetchVariances = async (baseM?: string, currM?: string, mat?: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (baseM) params.append("baseline_month", baseM);
      if (currM) params.append("current_month", currM);
      params.append("only_material", (mat !== undefined ? mat : onlyMaterial).toString());
      params.append("min_amount", "1000");
      params.append("min_pct", "10");

      const res = await apiFetch(`/api/v1/variance?${params.toString()}`);
      if (!res.ok) {
        throw new Error("Failed to load variance analysis.");
      }
      const json: VarianceResponse = await res.json();
      setData(json);

      if (!baselineMonth && json.baseline_month) setBaselineMonth(json.baseline_month);
      if (!currentMonth && json.current_month) setCurrentMonth(json.current_month);
    } catch (err: any) {
      setError(err.message || "An error occurred while fetching variance data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVariances();
  }, []);

  const handleMonthChange = (newBase: string, newCurr: string) => {
    setBaselineMonth(newBase);
    setCurrentMonth(newCurr);
    fetchVariances(newBase, newCurr, onlyMaterial);
  };

  const toggleMaterialFilter = () => {
    const nextVal = !onlyMaterial;
    setOnlyMaterial(nextVal);
    fetchVariances(baselineMonth, currentMonth, nextVal);
  };

  const toggleDrivers = (catName: string) => {
    setExpandedDrivers((prev) => ({
      ...prev,
      [catName]: !prev[catName],
    }));
  };

  const formatCurrency = (amount: number) => {
    const formatted = Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  const formatMonthLabel = (m: string) => {
    if (!m) return "";
    const [year, month] = m.split("-");
    const date = new Date(parseInt(year), parseInt(month) - 1, 1);
    return date.toLocaleDateString("en-US", { month: "short", year: "numeric" });
  };

  if (loading && !data) {
    return (
      <div className="bg-[#ffffff] rounded-2xl p-12 border border-[var(--color-hairline)] text-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto text-[var(--color-primary)]" />
        <p className="text-sm font-medium text-[var(--color-body)]">
          Computing Month-over-Month variances and material breach thresholds...
        </p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-red-50 rounded-2xl p-8 border border-red-200 text-center space-y-3">
        <p className="text-sm text-red-800 font-medium">{error || "No variance data available."}</p>
        <motion.button
          onClick={() => fetchVariances(baselineMonth, currentMonth, onlyMaterial)}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
          className="px-4 py-2 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold cursor-pointer"
        >
          Retry Calculation
        </motion.button>
      </div>
    );
  }

  const { available_months } = data;

  return (
    <div className="space-y-6">
      {/* Header & Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold tracking-tight text-[var(--color-ink)]">
              Month-over-Month Variance &amp; Driver Attribution
            </h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-[var(--color-brand-lavender)]/40 border border-[var(--color-brand-lavender)] text-[11px] font-semibold text-indigo-950">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-700" />
              Threshold: &gt;10% &amp; &gt;$1,000
            </span>
          </div>
          <p className="text-xs text-[var(--color-muted)] mt-0.5">
            Compares {formatMonthLabel(data.baseline_month)} against {formatMonthLabel(data.current_month)} with automated transaction-level driver tracing.
          </p>
        </div>

        {/* Month Selector & Materiality Toggle */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-[#ffffff] p-1 rounded-xl border border-[var(--color-hairline)] shadow-xs text-xs">
            <span className="text-[var(--color-muted)] pl-2 font-medium">Base:</span>
            <select
              value={data.baseline_month || ""}
              onChange={(e) => handleMonthChange(e.target.value, currentMonth)}
              className="bg-transparent py-1 px-2 font-mono font-medium focus:outline-none cursor-pointer"
            >
              {available_months.map((m) => (
                <option key={`base-${m}`} value={m}>
                  {formatMonthLabel(m)}
                </option>
              ))}
            </select>

            <span className="text-[var(--color-muted)] font-medium">vs</span>

            <span className="text-[var(--color-muted)] font-medium">Current:</span>
            <select
              value={data.current_month || ""}
              onChange={(e) => handleMonthChange(baselineMonth, e.target.value)}
              className="bg-transparent py-1 px-2 font-mono font-medium focus:outline-none cursor-pointer"
            >
              {available_months.map((m) => (
                <option key={`curr-${m}`} value={m}>
                  {formatMonthLabel(m)}
                </option>
              ))}
            </select>
          </div>

          <motion.button
            onClick={toggleMaterialFilter}
            whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
            className={`px-3 py-2 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs cursor-pointer ${
              onlyMaterial
                ? "bg-[var(--color-brand-peach)] text-[var(--color-ink)] border-[var(--color-brand-peach)]"
                : "bg-[#ffffff] border-[var(--color-hairline)] text-[var(--color-muted)] hover:text-[var(--color-ink)]"
            }`}
          >
            <Filter className="w-3.5 h-3.5" />
            <span>{onlyMaterial ? "Material Breaches Only" : "Show All Shifts"}</span>
          </motion.button>
        </div>
      </div>

      {/* High-Level Executive Summary Cards */}
      {data.summary_variances && data.summary_variances.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {data.summary_variances.map((s, idx) => (
            <motion.div
              key={s.metric}
              initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: idx * 0.05 }}
              className="bg-[#ffffff] rounded-xl p-5 border border-[var(--color-hairline)] shadow-xs space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-[var(--color-muted)] font-medium">{s.label}</span>
                <span
                  className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    s.is_favorable
                      ? "bg-[var(--color-brand-mint)]/40 text-emerald-950"
                      : "bg-red-100 text-red-900"
                  }`}
                >
                  {s.is_favorable ? (
                    <ArrowUpRight className="w-3 h-3 text-emerald-700" />
                  ) : (
                    <ArrowDownRight className="w-3 h-3 text-red-700" />
                  )}
                  <span>{s.is_favorable ? "Favorable" : "Unfavorable"}</span>
                </span>
              </div>

              <div className="flex items-baseline justify-between">
                <div className="text-xl font-bold font-mono text-[var(--color-ink)]">
                  {s.delta_amount >= 0 ? "+" : ""}{formatCurrency(s.delta_amount)}
                </div>
                <span
                  className={`text-xs font-mono font-semibold ${
                    s.is_favorable ? "text-emerald-700" : "text-red-700"
                  }`}
                >
                  {s.delta_pct >= 0 ? "+" : ""}{s.delta_pct.toFixed(1)}%
                </span>
              </div>

              <div className="text-[11px] text-[var(--color-muted)] flex items-center justify-between pt-1 border-t border-[var(--color-hairline)] font-mono">
                <span>{formatMonthLabel(data.baseline_month)}: {formatCurrency(s.baseline_amount)}</span>
                <span>→</span>
                <span>{formatMonthLabel(data.current_month)}: {formatCurrency(s.current_amount)}</span>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Material Category Variance Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-lg font-bold tracking-tight text-[var(--color-ink)]">
              Category Variance &amp; Driver Breakdown
            </h3>
            <p className="text-xs text-[var(--color-muted)]">
              Concrete operational drivers and underlying transactions explaining material deviations.
            </p>
          </div>
          <span className="text-xs text-[var(--color-muted)] font-medium">
            {data.category_variances.length} material shift{data.category_variances.length === 1 ? "" : "s"}
          </span>
        </div>

        {data.category_variances.length === 0 ? (
          <div className="bg-[#ffffff] rounded-2xl p-10 border border-[var(--color-hairline)] text-center text-xs text-[var(--color-muted)]">
            No variances exceed the current materiality threshold (&gt;$1,000 and &gt;10%). Toggle filter above to view all shifts.
          </div>
        ) : (
          data.category_variances.map((v, idx) => (
            <motion.div
              key={v.category}
              initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, delay: idx * 0.04 }}
              className="bg-[#ffffff] rounded-2xl p-6 border border-[var(--color-hairline)] shadow-xs space-y-4 hover:border-[var(--color-muted)] transition-all"
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--color-surface-soft)] text-[var(--color-body)] border border-[var(--color-hairline)]">
                      {v.pnl_bucket}
                    </span>
                    <h4 className="text-base font-bold text-[var(--color-ink)]">
                      {v.category}
                    </h4>
                  </div>
                  <div className="text-xs text-[var(--color-muted)] flex items-center gap-2 font-mono">
                    <span>{formatMonthLabel(data.baseline_month)}: {formatCurrency(v.baseline_amount)}</span>
                    <span>→</span>
                    <span>{formatMonthLabel(data.current_month)}: {formatCurrency(v.current_amount)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-lg font-bold font-mono text-[var(--color-ink)]">
                      {v.delta_amount >= 0 ? "+" : ""}{formatCurrency(v.delta_amount)}
                    </div>
                    <div
                      className={`text-xs font-mono font-bold ${
                        v.is_favorable ? "text-emerald-700" : "text-red-700"
                      }`}
                    >
                      {v.delta_pct >= 0 ? "+" : ""}{v.delta_pct.toFixed(1)}% MoM
                    </div>
                  </div>

                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold border ${
                      v.is_favorable
                        ? "bg-[var(--color-brand-mint)]/40 text-emerald-950 border-[var(--color-brand-mint)]"
                        : "bg-[var(--color-brand-peach)]/40 text-red-950 border-[var(--color-brand-peach)]"
                    }`}
                  >
                    {v.is_favorable ? "Favorable" : "Unfavorable"}
                  </span>
                </div>
              </div>

              {/* Narrative Explanation Banner */}
              <div className="p-3.5 rounded-xl bg-[var(--color-surface-soft)] border border-[var(--color-hairline)] text-xs text-[var(--color-ink)] flex items-start gap-2.5">
                <Sparkles className="w-4 h-4 text-[var(--color-brand-lavender)] shrink-0 mt-0.5" />
                <div className="flex-1 font-medium leading-relaxed">
                  {v.explanation}
                </div>
              </div>

              {/* Transaction Drivers Drawer / Toggle */}
              {v.drivers && v.drivers.length > 0 && (
                <div className="pt-2 border-t border-[var(--color-hairline)]">
                  <div className="flex items-center justify-between">
                    <motion.button
                      type="button"
                      onClick={() => toggleDrivers(v.category)}
                      whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                      whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                      className="text-xs font-semibold text-[var(--color-body)] hover:text-[var(--color-ink)] flex items-center gap-1.5 cursor-pointer py-1"
                    >
                      <Layers className="w-3.5 h-3.5 text-[var(--color-primary)]" />
                      <span>
                        {expandedDrivers[v.category]
                          ? "Hide Driver Transactions"
                          : `View Top ${v.drivers.length} Driver Transactions`}
                      </span>
                    </motion.button>

                    {onNavigateToTransactions && (
                      <motion.button
                        type="button"
                        onClick={() => onNavigateToTransactions(v.category)}
                        whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
                        whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                        className="text-xs text-[var(--color-muted)] hover:text-[var(--color-ink)] flex items-center gap-1 cursor-pointer"
                      >
                        <span>Filter in Transactions table</span>
                        <ArrowRight className="w-3 h-3" />
                      </motion.button>
                    )}
                  </div>

                  {/* Expandable Transaction Details with Framer Motion AnimatePresence */}
                  <AnimatePresence>
                    {expandedDrivers[v.category] && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2, ease: "easeOut" }}
                        className="mt-3 overflow-hidden"
                      >
                        <div className="rounded-xl border border-[var(--color-hairline)] bg-[var(--color-canvas)] overflow-hidden">
                          <table className="w-full text-left border-collapse text-xs">
                            <thead>
                              <tr className="bg-[var(--color-surface-soft)] border-b border-[var(--color-hairline)] text-[var(--color-muted)] font-medium">
                                <th className="py-2 px-3">Code</th>
                                <th className="py-2 px-3">Date</th>
                                <th className="py-2 px-3">Description</th>
                                <th className="py-2 px-3">Counterparty</th>
                                <th className="py-2 px-3 text-right">Amount</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--color-hairline)]">
                              {v.drivers.map((d) => (
                                <tr key={d.id} className="hover:bg-white/60 transition-colors">
                                  <td className="py-2 px-3 font-mono font-medium text-[var(--color-muted)]">
                                    {d.transaction_code}
                                  </td>
                                  <td className="py-2 px-3 font-mono text-[var(--color-body)]">{d.date}</td>
                                  <td className="py-2 px-3 font-medium text-[var(--color-ink)] max-w-xs truncate">
                                    {d.description}
                                  </td>
                                  <td className="py-2 px-3 text-[var(--color-body)]">{d.counterparty}</td>
                                  <td className="py-2 px-3 text-right font-mono font-bold">
                                    {formatCurrency(d.amount)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
