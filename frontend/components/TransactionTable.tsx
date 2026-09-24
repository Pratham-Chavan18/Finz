"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  Search,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Edit3,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Tag,
  Filter,
} from "lucide-react";
import CorrectionModal from "@/components/CorrectionModal";
import { apiFetch } from "@/lib/api";

interface TransactionItem {
  id: number;
  transaction_code: string | null;
  date: string;
  description: string;
  counterparty: string | null;
  amount: number;
  method: string | null;
  category: string | null;
  pnl_bucket: string | null;
  confidence: number | null;
  rationale: string | null;
  is_flagged_for_review: boolean;
  review_status: string;
}

interface StatsData {
  total_transactions: number;
  total_inflows: number;
  total_outflows: number;
  net_cash_flow: number;
  categorized_count: number;
  uncategorized_count: number;
  flagged_count: number;
  date_range: { start: string | null; end: string | null };
}

interface TransactionTableProps {
  apiUrl?: string;
  onRefreshTrigger?: () => void;
}

export default function TransactionTable({
  onRefreshTrigger,
}: TransactionTableProps) {
  const shouldReduceMotion = useReducedMotion();
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [categorizing, setCategorizing] = useState(false);
  const [categorizeMessage, setCategorizeMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [bucketFilter, setBucketFilter] = useState<string>("");
  const [flaggedFilter, setFlaggedFilter] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<string>("date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Edit / Correction Modal state
  const [editingTransaction, setEditingTransaction] = useState<TransactionItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchStats = async () => {
    try {
      const res = await apiFetch("/api/v1/transactions/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch {
      // ignore
    }
  };

  const fetchTransactions = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString(),
        sort_by: sortBy,
        sort_dir: sortDir,
      });

      if (search.trim()) params.append("search", search.trim());
      if (categoryFilter) params.append("category", categoryFilter);
      if (bucketFilter) params.append("pnl_bucket", bucketFilter);
      if (flaggedFilter !== null) params.append("is_flagged", flaggedFilter.toString());

      const res = await apiFetch(`/api/v1/transactions?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setTransactions(data.items);
        setTotalPages(data.pages);
        setTotalCount(data.total);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchTransactions();
  }, [page, limit, sortBy, sortDir, categoryFilter, bucketFilter, flaggedFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchTransactions();
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const handleCategorizeAll = async () => {
    setCategorizing(true);
    setCategorizeMessage(null);
    try {
      const res = await apiFetch("/api/v1/categorize/batch?force=true", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setCategorizeMessage({
          type: "success",
          text: `Successfully categorized ${data.categorized_count} transactions (${data.flagged_for_review} flagged for review).`,
        });
        fetchStats();
        fetchTransactions();
        if (onRefreshTrigger) onRefreshTrigger();
      } else {
        let errDetail = "";
        try {
          const errData = await res.json();
          errDetail = errData.detail || errData.message || "";
        } catch {
          // ignore json parse error
        }
        setCategorizeMessage({
          type: "error",
          text: errDetail || `Batch categorization failed with status ${res.status}.`,
        });
      }
    } catch (err: any) {
      setCategorizeMessage({
        type: "error",
        text: `Error: ${err.message || "Failed to batch categorize."}`,
      });
    } finally {
      setCategorizing(false);
    }
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortDir("asc");
    }
    setPage(1);
  };

  const openCorrectionModal = (tx: TransactionItem) => {
    setEditingTransaction(tx);
    setIsModalOpen(true);
  };

  const handleCorrectionSuccess = (newCategory: string) => {
    fetchTransactions();
    fetchStats();
    if (onRefreshTrigger) onRefreshTrigger();
  };

  const formatCurrency = (amount: number) => {
    const formatted = Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${formatted}` : `+$${formatted}`;
  };

  const getCategoryBadgeClass = (pnlBucket: string | null, category: string | null) => {
    if (!category) return "bg-[var(--color-surface-soft)] text-[var(--color-muted)] border-[var(--color-hairline)]";

    const b = (pnlBucket || category).toLowerCase();
    if (b.includes("revenue") || b.includes("sales")) {
      return "bg-[var(--color-brand-mint)]/30 text-emerald-950 border-[var(--color-brand-mint)]/70 hover:bg-[var(--color-brand-mint)]/50";
    }
    if (b.includes("cogs") || b.includes("food") || b.includes("beverage")) {
      return "bg-[var(--color-brand-peach)]/30 text-orange-950 border-[var(--color-brand-peach)]/70 hover:bg-[var(--color-brand-peach)]/50";
    }
    if (b.includes("payroll") || b.includes("wage") || b.includes("salary")) {
      return "bg-[var(--color-brand-lavender)]/30 text-indigo-950 border-[var(--color-brand-lavender)]/70 hover:bg-[var(--color-brand-lavender)]/50";
    }
    if (b.includes("opex") || b.includes("rent") || b.includes("utilities") || b.includes("operating")) {
      return "bg-[var(--color-brand-ochre)]/30 text-amber-950 border-[var(--color-brand-ochre)]/70 hover:bg-[var(--color-brand-ochre)]/50";
    }
    if (b.includes("non-p&l") || b.includes("equipment") || b.includes("tax remittance")) {
      return "bg-slate-100 text-slate-800 border-slate-300 hover:bg-slate-200";
    }
    return "bg-[var(--color-surface-soft)] text-[var(--color-body-strong)] border-[var(--color-hairline)] hover:bg-[var(--color-surface-card)]";
  };

  return (
    <div className="space-y-6">
      {/* Financial Overview Stats Cards */}
      {stats && stats.total_transactions > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <motion.div
            initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.05 }}
            className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
          >
            <span className="text-xs text-[var(--color-muted)] font-medium">Total Transactions</span>
            <div className="text-2xl font-bold text-[var(--color-ink)] mt-1">
              {stats.total_transactions}
            </div>
            <div className="text-[11px] text-[var(--color-muted)] mt-0.5">
              {stats.date_range.start} → {stats.date_range.end}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.1 }}
            className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
          >
            <span className="text-xs text-[var(--color-muted)] font-medium">Total Inflows (Revenue)</span>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              +${stats.total_inflows.toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-[var(--color-muted)] mt-0.5">POS, Catering, Deposits</div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.15 }}
            className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
          >
            <span className="text-xs text-[var(--color-muted)] font-medium">Total Outflows (Expenses)</span>
            <div className="text-2xl font-bold text-slate-800 mt-1">
              -${Math.abs(stats.total_outflows).toLocaleString("en-US", { minimumFractionDigits: 2 })}
            </div>
            <div className="text-[11px] text-[var(--color-muted)] mt-0.5">COGS, Payroll, OpEx</div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: 0.2 }}
            className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
          >
            <span className="text-xs text-[var(--color-muted)] font-medium">Categorization Status</span>
            <div className="text-2xl font-bold text-[var(--color-primary)] mt-1">
              {stats.categorized_count} / {stats.total_transactions}
            </div>
            <div className="text-[11px] text-amber-700 mt-0.5 font-medium">
              {stats.flagged_count} flagged for review
            </div>
          </motion.div>
        </div>
      )}

      {/* Categorization Banner Message if triggered */}
      <AnimatePresence>
        {categorizeMessage && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className={`p-3.5 rounded-xl border text-xs flex items-center justify-between ${
              categorizeMessage.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                : "bg-red-50 border-red-200 text-red-800"
            }`}
          >
            <div className="flex items-center gap-2">
              {categorizeMessage.type === "success" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{categorizeMessage.text}</span>
            </div>
            <button
              onClick={() => setCategorizeMessage(null)}
              className="text-xs font-semibold hover:underline cursor-pointer"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Control Bar: Search, Filters, Limit, Categorize Action */}
      <div className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] flex flex-col md:flex-row items-center justify-between gap-3 shadow-xs">
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto flex-1">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]" />
            <input
              type="text"
              data-testid="transaction-search-input"
              placeholder="Search description, payee, code..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-xl bg-[var(--color-canvas)] border border-[var(--color-hairline)] text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-all"
            />
          </div>

          {/* Bucket Filter */}
          <select
            value={bucketFilter}
            onChange={(e) => {
              setBucketFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 rounded-xl bg-[var(--color-canvas)] border border-[var(--color-hairline)] text-xs text-[var(--color-body)] focus:outline-none focus:border-[var(--color-primary)] cursor-pointer"
          >
            <option value="">All Buckets</option>
            <option value="Revenue">Revenue</option>
            <option value="COGS">COGS</option>
            <option value="Payroll">Payroll</option>
            <option value="Operating Expenses">Operating Expenses</option>
            <option value="Non-P&L">Non-P&L (CapEx/Tax)</option>
          </select>

          {/* Flagged Filter */}
          <motion.button
            whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
            onClick={() => {
              setFlaggedFilter(flaggedFilter === true ? null : true);
              setPage(1);
            }}
            className={`px-3 py-2 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-all cursor-pointer ${
              flaggedFilter === true
                ? "bg-[var(--color-brand-peach)] text-[var(--color-ink)] border-[var(--color-brand-peach)] font-semibold shadow-xs"
                : "bg-[var(--color-canvas)] border-[var(--color-hairline)] text-[var(--color-body)] hover:border-[var(--color-muted)]"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Flagged for Review</span>
          </motion.button>
        </div>

        {/* Action Buttons: Categorize All + Refresh */}
        <div className="flex items-center gap-2.5 w-full md:w-auto justify-end">
          <motion.button
            onClick={handleCategorizeAll}
            disabled={categorizing}
            whileHover={shouldReduceMotion || categorizing ? undefined : { scale: 1.01 }}
            whileTap={shouldReduceMotion || categorizing ? undefined : { scale: 0.98 }}
            className="px-3.5 py-2 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold hover:bg-[var(--color-primary-active)] disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${categorizing ? "animate-spin" : ""}`} />
            <span>{categorizing ? "Categorizing..." : "Categorize All"}</span>
          </motion.button>

          <span className="text-xs text-[var(--color-muted)] pl-2">
            <strong>{transactions.length}</strong> of <strong>{totalCount}</strong>
          </span>

          <motion.button
            onClick={() => {
              fetchStats();
              fetchTransactions();
            }}
            whileHover={shouldReduceMotion ? undefined : { scale: 1.05 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.95 }}
            className="p-2 rounded-xl border border-[var(--color-hairline)] text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
            title="Refresh transactions"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </motion.button>
        </div>
      </div>

      {/* Data-Dense Table with Click-to-Edit Category Badges */}
      <div className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[var(--color-surface-soft)] border-b border-[var(--color-hairline)] text-[var(--color-muted)] uppercase tracking-wider font-semibold">
                <th
                  onClick={() => handleSort("transaction_code")}
                  className="py-3 px-4 cursor-pointer hover:text-[var(--color-ink)] select-none w-20"
                >
                  <div className="flex items-center gap-1">
                    <span>ID</span>
                    {sortBy === "transaction_code" && (
                      sortDir === "asc" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />
                    )}
                  </div>
                </th>
                <th
                  onClick={() => handleSort("date")}
                  className="py-3 px-4 cursor-pointer hover:text-[var(--color-ink)] select-none w-28"
                >
                  <div className="flex items-center gap-1">
                    <span>Date</span>
                    {sortBy === "date" && (
                      sortDir === "asc" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />
                    )}
                  </div>
                </th>
                <th className="py-3 px-4">Description</th>
                <th className="py-3 px-4">Counterparty</th>
                <th
                  onClick={() => handleSort("amount")}
                  className="py-3 px-4 text-right cursor-pointer hover:text-[var(--color-ink)] select-none w-28"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Amount</span>
                    {sortBy === "amount" && (
                      sortDir === "asc" ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />
                    )}
                  </div>
                </th>
                <th className="py-3 px-4">Category (Click to Correct)</th>
                <th className="py-3 px-4 w-28">P&amp;L Bucket</th>
                <th className="py-3 px-4 text-center w-24">Review</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-hairline)]">
              {loading && transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[var(--color-muted)]">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <RefreshCw className="w-5 h-5 animate-spin text-[var(--color-primary)]" />
                      <span>Loading transactions...</span>
                    </div>
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[var(--color-muted)]">
                    No transactions found matching your filters.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className="hover:bg-[var(--color-canvas)] transition-colors group"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-[var(--color-muted)]">
                      {tx.transaction_code || `TX-${tx.id}`}
                    </td>
                    <td className="py-3 px-4 font-mono text-[var(--color-body)] whitespace-nowrap">
                      {tx.date}
                    </td>
                    <td className="py-3 px-4 font-medium text-[var(--color-ink)] max-w-xs truncate" title={tx.description}>
                      {tx.description}
                    </td>
                    <td className="py-3 px-4 text-[var(--color-body)] max-w-[150px] truncate" title={tx.counterparty || ""}>
                      {tx.counterparty || "—"}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-semibold whitespace-nowrap">
                      <span
                        className={
                          tx.amount >= 0
                            ? "text-emerald-600 font-bold"
                            : "text-[var(--color-ink)]"
                        }
                      >
                        {formatCurrency(tx.amount)}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <motion.button
                        type="button"
                        onClick={() => openCorrectionModal(tx)}
                        whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
                        whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[11px] font-medium transition cursor-pointer max-w-[200px] truncate ${getCategoryBadgeClass(
                          tx.pnl_bucket,
                          tx.category
                        )}`}
                        title="Click to manually reclassify category with audit trail"
                      >
                        <Tag className="w-2.5 h-2.5 shrink-0 opacity-70" />
                        <span className="truncate">{tx.category || "Uncategorized"}</span>
                        <Edit3 className="w-2.5 h-2.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity ml-1" />
                      </motion.button>
                    </td>
                    <td className="py-3 px-4 text-[11px] font-medium text-[var(--color-muted)]">
                      {tx.pnl_bucket || "—"}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {tx.is_flagged_for_review ? (
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-semibold"
                          title={tx.rationale || "Flagged for manual review"}
                        >
                          <AlertTriangle className="w-2.5 h-2.5 text-amber-700" />
                          Review
                        </span>
                      ) : tx.review_status === "confirmed" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 text-[10px] font-semibold">
                          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                          Confirmed
                        </span>
                      ) : (
                        <span className="text-[11px] text-[var(--color-muted)]">
                          Auto
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="bg-[var(--color-surface-soft)] px-4 py-3 border-t border-[var(--color-hairline)] flex items-center justify-between">
          <div className="text-xs text-[var(--color-muted)]">
            Page <strong>{page}</strong> of <strong>{totalPages}</strong> ({totalCount} items)
          </div>
          <div className="flex items-center gap-2">
            <motion.button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              whileHover={shouldReduceMotion || page <= 1 ? undefined : { scale: 1.05 }}
              whileTap={shouldReduceMotion || page <= 1 ? undefined : { scale: 0.95 }}
              className="p-1.5 rounded-lg border border-[var(--color-hairline)] text-xs text-[var(--color-body)] disabled:opacity-40 hover:bg-[#ffffff] transition cursor-pointer"
            >
              <ChevronLeft className="w-4 h-4" />
            </motion.button>
            <motion.button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              whileHover={shouldReduceMotion || page >= totalPages ? undefined : { scale: 1.05 }}
              whileTap={shouldReduceMotion || page >= totalPages ? undefined : { scale: 0.95 }}
              className="p-1.5 rounded-lg border border-[var(--color-hairline)] text-xs text-[var(--color-body)] disabled:opacity-40 hover:bg-[#ffffff] transition cursor-pointer"
            >
              <ChevronRight className="w-4 h-4" />
            </motion.button>
          </div>
        </div>
      </div>

      {/* Reclassification / Correction Modal */}
      <CorrectionModal
        transaction={editingTransaction}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setEditingTransaction(null);
        }}
        onSuccess={handleCorrectionSuccess}
      />
    </div>
  );
}
