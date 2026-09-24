"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Search, FileText, ArrowRight, ShieldCheck, Database, Layers, ExternalLink } from "lucide-react";
import { apiFetch } from "@/lib/api";

export interface TraceabilityDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  metricKey: string;
  metricLabel?: string;
  month?: string;
}

interface TraceabilityData {
  metric_key: string;
  period: string;
  calculated_value: number;
  formula: string;
  components: Array<{ label: string; value: number; type: string }>;
  transaction_count: number;
  transactions: Array<{
    id: number;
    transaction_code: string;
    date: string;
    description: string;
    counterparty?: string;
    category: string;
    pnl_bucket: string;
    amount: number;
  }>;
}

export default function TraceabilityDrawer({
  isOpen,
  onClose,
  metricKey,
  metricLabel,
  month,
}: TraceabilityDrawerProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<TraceabilityData | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !metricKey) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    const queryParams = new URLSearchParams();
    if (month) queryParams.set("month", month);

    apiFetch(`/api/v1/traceability/${encodeURIComponent(metricKey)}?${queryParams.toString()}`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("Unable to retrieve metric origin.");
        }
        return res.json();
      })
      .then((json) => {
        if (isMounted) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || "Failed to load audit evidence.");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, metricKey, month]);

  const filteredTransactions = (data?.transactions || []).filter((t) => {
    if (!search) return true;
    const term = search.toLowerCase();
    return (
      t.description.toLowerCase().includes(term) ||
      (t.counterparty && t.counterparty.toLowerCase().includes(term)) ||
      t.category.toLowerCase().includes(term) ||
      t.transaction_code.toLowerCase().includes(term)
    );
  });

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-stone-900/40 backdrop-blur-sm"
          />

          {/* Drawer Container */}
          <motion.div
            initial={{ x: "100%", opacity: 0.5 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0.5 }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-[#faf8f5] shadow-2xl border-l border-stone-200 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="px-6 py-5 bg-white border-b border-stone-200 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/60">
                    <ShieldCheck className="w-3.5 h-3.5 mr-1 text-emerald-600" />
                    Verified Evidence
                  </span>
                  <span className="text-xs text-stone-700">Period: {month || "All Time"}</span>
                </div>
                <h2 className="text-xl font-bold text-stone-900 tracking-tight mt-1">
                  {metricLabel || metricKey} Traceability
                </h2>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-stone-700 hover:text-stone-900 hover:bg-stone-100 transition-colors"
                aria-label="Close drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loading ? (
                <div className="space-y-4">
                  <div className="h-28 bg-white border border-stone-200 rounded-xl animate-pulse" />
                  <div className="h-10 bg-white border border-stone-200 rounded-xl animate-pulse" />
                  <div className="space-y-2">
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className="h-16 bg-white border border-stone-200 rounded-xl animate-pulse" />
                    ))}
                  </div>
                </div>
              ) : error ? (
                <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                  {error}
                </div>
              ) : data ? (
                <>
                  {/* Calculation Card */}
                  <div className="bg-white border border-stone-200/80 rounded-xl p-5 shadow-sm space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wider text-stone-700">
                        Mathematical Formula
                      </span>
                      <span className="text-lg font-mono font-bold text-stone-900">
                        ${data.calculated_value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                    </div>

                    <div className="p-3 bg-stone-50 rounded-lg border border-stone-200/60 text-xs font-mono text-stone-700 leading-relaxed break-words">
                      {data.formula}
                    </div>

                    {data.components && data.components.length > 0 && (
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 border-t border-stone-100">
                        {data.components.map((comp, idx) => (
                          <div key={idx} className="p-2.5 bg-stone-50/60 rounded-lg border border-stone-200/40">
                            <div className="text-[11px] text-stone-700 truncate">{comp.label}</div>
                            <div className="text-xs font-semibold text-stone-800 font-mono mt-0.5">
                              ${comp.value?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center gap-1.5 text-[11px] text-stone-700 pt-1">
                      <Database className="w-3.5 h-3.5 text-stone-700" />
                      Calculated directly from {data.transaction_count} underlying transaction records.
                    </div>
                  </div>

                  {/* Transaction Search & Header */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-stone-800">
                        Underlying Transactions ({filteredTransactions.length})
                      </h3>
                    </div>

                    <div className="relative">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-700" />
                      <input
                        type="text"
                        placeholder="Search description, category, or code..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="w-full pl-9 pr-4 py-2 bg-white border border-stone-200 rounded-lg text-xs text-stone-900 placeholder:text-stone-700 focus:outline-none focus:ring-2 focus:ring-stone-400"
                      />
                    </div>
                  </div>

                  {/* Transaction List */}
                  {filteredTransactions.length === 0 ? (
                    <div className="py-12 text-center bg-white border border-stone-200 rounded-xl">
                      <FileText className="w-8 h-8 text-stone-700 mx-auto mb-2" />
                      <p className="text-sm font-medium text-stone-700">No matching transactions found</p>
                      <p className="text-xs text-stone-700 mt-1">Try broadening your search term.</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {filteredTransactions.map((tx) => (
                        <div
                          key={tx.id}
                          className="bg-white border border-stone-200/80 rounded-xl p-3.5 shadow-sm hover:border-stone-300 transition-colors flex items-center justify-between gap-4"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[11px] font-semibold text-stone-700 px-1.5 py-0.5 bg-stone-100 rounded">
                                {tx.transaction_code}
                              </span>
                              <span className="text-[11px] text-stone-700">{tx.date}</span>
                            </div>
                            <div className="text-sm font-medium text-stone-900 truncate mt-1">
                              {tx.description}
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-xs text-stone-700">
                              <span className="px-2 py-0.5 rounded bg-stone-100 border border-stone-200 text-stone-700 text-[10px]">
                                {tx.category}
                              </span>
                              <span className="text-[11px] text-stone-700">{tx.pnl_bucket}</span>
                            </div>
                          </div>

                          <div className="text-right">
                            <div
                              className={`text-sm font-semibold font-mono ${
                                tx.amount >= 0 ? "text-emerald-700" : "text-stone-900"
                              }`}
                            >
                              {tx.amount >= 0 ? "+" : ""}${Math.abs(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : null}
            </div>

            {/* Footer */}
            <div className="px-6 py-3.5 bg-stone-50 border-t border-stone-200 flex items-center justify-between text-xs text-stone-700">
              <span>Origin: Deterministic SQL Ledger</span>
              <button
                onClick={onClose}
                className="px-3.5 py-1.5 bg-stone-900 text-white font-medium rounded-lg hover:bg-stone-800 transition-colors"
              >
                Close
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
