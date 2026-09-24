"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { X, Check, AlertCircle, Sparkles, Building2, HelpCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface CategoryItem {
  category: string;
  pnl_bucket: string;
  description: string;
}

interface TransactionToEdit {
  id: number;
  transaction_code: string | null;
  date: string;
  description: string;
  counterparty: string | null;
  amount: number;
  category: string | null;
  pnl_bucket: string | null;
  rationale: string | null;
}

interface CorrectionModalProps {
  transaction: TransactionToEdit | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedCategory: string) => void;
  apiUrl?: string;
}

export default function CorrectionModal({
  transaction,
  isOpen,
  onClose,
  onSuccess,
}: CorrectionModalProps) {
  const shouldReduceMotion = useReducedMotion();
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [buckets, setBuckets] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch Chart of Accounts on mount
  useEffect(() => {
    async function loadCategories() {
      try {
        const res = await apiFetch("/api/v1/categories");
        if (res.ok) {
          const data = await res.json();
          setCategories(data.chart_of_accounts || []);
          setBuckets(data.buckets || []);
        }
      } catch (err) {
        console.error("Failed to fetch categories:", err);
      }
    }
    loadCategories();
  }, []);

  // Set initial category when transaction prop changes
  useEffect(() => {
    if (transaction) {
      setSelectedCategory(transaction.category || "");
      setNote("");
      setError(null);
    }
  }, [transaction]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCategory || !transaction) {
      setError("Please select a category.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await apiFetch(`/api/v1/transactions/${transaction.id}/category`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category: selectedCategory,
          note: note.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to update category.");
      }

      onSuccess(selectedCategory);
      onClose();
    } catch (err: any) {
      setError(err.message || "An error occurred while saving the correction.");
    } finally {
      setSubmitting(false);
    }
  };

  const formatCurrency = (amount: number) => {
    const formatted = Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  return (
    <AnimatePresence>
      {isOpen && transaction && (
        <motion.div
          key="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs"
        >
          <motion.div
            key="modal-dialog"
            initial={{
              opacity: 0,
              scale: shouldReduceMotion ? 1 : 0.96,
              y: shouldReduceMotion ? 0 : 8,
            }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{
              opacity: 0,
              scale: shouldReduceMotion ? 1 : 0.96,
              y: shouldReduceMotion ? 0 : 4,
            }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] max-w-lg w-full p-6 shadow-xl space-y-6 relative"
          >
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[var(--color-brand-peach)]/30 border border-[var(--color-brand-peach)] text-[11px] font-semibold text-[var(--color-ink)]">
                  Audited Correction
                </div>
                <h3 className="text-xl font-bold tracking-tight text-[var(--color-ink)]">
                  Reclassify Transaction
                </h3>
                <p className="text-xs text-[var(--color-muted)]">
                  Updates downstream P&amp;L calculations and creates an immutable audit trail.
                </p>
              </div>
              <motion.button
                type="button"
                onClick={onClose}
                whileHover={shouldReduceMotion ? undefined : { scale: 1.05 }}
                whileTap={shouldReduceMotion ? undefined : { scale: 0.95 }}
                className="p-1.5 rounded-xl border border-[var(--color-hairline)] text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
              >
                <X className="w-4 h-4" />
              </motion.button>
            </div>

            {/* Transaction Summary Card */}
            <div className="bg-[var(--color-canvas)] rounded-xl p-4 border border-[var(--color-hairline)] space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-mono text-[var(--color-muted)] font-medium">
                  {transaction.transaction_code || `TX-${transaction.id}`} • {transaction.date}
                </span>
                <span
                  className={`font-mono font-bold text-sm ${
                    transaction.amount >= 0 ? "text-emerald-600" : "text-slate-900"
                  }`}
                >
                  {formatCurrency(transaction.amount)}
                </span>
              </div>

              <div className="font-medium text-[var(--color-ink)] text-sm">
                {transaction.description}
              </div>

              {transaction.counterparty && (
                <div className="text-[var(--color-body)] flex items-center gap-1">
                  <span className="text-[var(--color-muted)]">Counterparty:</span>
                  <strong className="text-[var(--color-ink)]">{transaction.counterparty}</strong>
                </div>
              )}

              {transaction.rationale && (
                <div className="text-[11px] text-[var(--color-muted)] bg-[var(--color-surface-soft)] p-2 rounded-lg border border-[var(--color-hairline)] italic">
                  AI Rationale: {transaction.rationale}
                </div>
              )}
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--color-ink)] flex items-center justify-between">
                  <span>Standard Chart of Accounts Category</span>
                  <span className="text-[11px] font-normal text-[var(--color-muted)]">
                    Required
                  </span>
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[var(--color-canvas)] border border-[var(--color-hairline)] text-xs font-medium text-[var(--color-ink)] focus:outline-none focus:border-[var(--color-primary)] transition-all cursor-pointer"
                >
                  <option value="" disabled>
                    Select a category...
                  </option>
                  {buckets.map((bucket) => {
                    const bucketCats = categories.filter((c) => c.pnl_bucket === bucket);
                    if (bucketCats.length === 0) return null;
                    return (
                      <optgroup key={bucket} label={`— ${bucket.toUpperCase()} —`}>
                        {bucketCats.map((c) => (
                          <option key={c.category} value={c.category}>
                            {c.category}
                          </option>
                        ))}
                      </optgroup>
                    );
                  })}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-[var(--color-ink)] flex items-center justify-between">
                  <span>Reviewer Note / Justification</span>
                  <span className="text-[11px] font-normal text-[var(--color-muted)]">
                    Optional
                  </span>
                </label>
                <textarea
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g., Reclassified as to-go packaging supplies per invoice details..."
                  className="w-full px-3.5 py-2 rounded-xl bg-[var(--color-canvas)] border border-[var(--color-hairline)] text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-all resize-none"
                />
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-2">
                <motion.button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                  whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                  className="px-4 py-2 rounded-xl border border-[var(--color-hairline)] text-xs font-semibold text-[var(--color-body)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
                >
                  Cancel
                </motion.button>
                <motion.button
                  type="submit"
                  disabled={submitting}
                  whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                  whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                  className="px-5 py-2 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold hover:bg-[var(--color-primary-active)] disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>{submitting ? "Saving..." : "Save Correction"}</span>
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
