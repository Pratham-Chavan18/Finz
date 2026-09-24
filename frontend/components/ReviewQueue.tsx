"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  CheckCircle2,
  XCircle,
  Edit3,
  AlertTriangle,
  RefreshCw,
  History,
  ShieldCheck,
  Sparkles,
  HelpCircle,
  Tag,
  ArrowRight,
} from "lucide-react";
import CorrectionModal from "@/components/CorrectionModal";
import { apiFetch } from "@/lib/api";

interface FlaggedItem {
  id: number;
  transaction_code: string;
  date: string;
  description: string;
  counterparty: string | null;
  amount: number;
  method: string | null;
  category: string | null;
  pnl_bucket: string | null;
  confidence: number | null;
  rationale: string | null;
  review_status: string;
}

interface AuditLogItem {
  id: number;
  transaction_id: number;
  transaction_code: string;
  description: string;
  amount: number;
  previous_category: string | null;
  new_category: string;
  source: string;
  note: string | null;
  created_at: string | null;
}

interface ReviewQueueProps {
  apiUrl?: string;
  onActionComplete?: () => void;
}

export default function ReviewQueue({
  onActionComplete,
}: ReviewQueueProps) {
  const shouldReduceMotion = useReducedMotion();
  const [items, setItems] = useState<FlaggedItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Correction Modal
  const [selectedTxn, setSelectedTxn] = useState<FlaggedItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Track completed/dismissed items and fetch count to prevent stale responses restoring items
  const completedItemIdsRef = useRef<Set<number>>(new Set());
  const fetchCounterRef = useRef<number>(0);

  const fetchQueue = async () => {
    const currentFetchId = ++fetchCounterRef.current;
    setLoading(true);
    try {
      const [queueRes, auditRes] = await Promise.all([
        apiFetch("/api/v1/review-queue"),
        apiFetch("/api/v1/audit-logs?limit=15"),
      ]);

      if (currentFetchId !== fetchCounterRef.current) return;

      if (queueRes.ok) {
        const queueData = await queueRes.json();
        const incoming: FlaggedItem[] = queueData.items || [];
        setItems(incoming.filter((i) => !completedItemIdsRef.current.has(i.id)));
      }
      if (auditRes.ok) {
        const auditData = await auditRes.json();
        setAuditLogs(auditData.logs || []);
      }
    } catch (err) {
      console.error("Failed to fetch review queue:", err);
    } finally {
      if (currentFetchId === fetchCounterRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleConfirm = async (item: FlaggedItem) => {
    setActionLoadingId(item.id);
    setActionMessage(null);
    try {
      const res = await apiFetch(`/api/v1/transactions/${item.id}/confirm`, {
        method: "POST",
      });
      if (res.ok) {
        completedItemIdsRef.current.add(item.id);
        // Optimistically remove from view for instant smooth animation
        setItems((prev) => prev.filter((i) => i.id !== item.id));
        setActionMessage(`Confirmed "${item.description}" as ${item.category}.`);
        fetchQueue();
        if (onActionComplete) onActionComplete();
      }
    } catch (err) {
      console.error("Failed to confirm item:", err);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDismiss = async (item: FlaggedItem) => {
    setActionLoadingId(item.id);
    setActionMessage(null);
    try {
      const res = await apiFetch(`/api/v1/transactions/${item.id}/dismiss`, {
        method: "POST",
      });
      if (res.ok) {
        completedItemIdsRef.current.add(item.id);
        setItems((prev) => prev.filter((i) => i.id !== item.id));
        setActionMessage(`Dismissed review flag for "${item.description}".`);
        fetchQueue();
        if (onActionComplete) onActionComplete();
      }
    } catch (err) {
      console.error("Failed to dismiss flag:", err);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleCorrectionSuccess = (newCategory: string) => {
    if (selectedTxn) {
      completedItemIdsRef.current.add(selectedTxn.id);
      setItems((prev) => prev.filter((i) => i.id !== selectedTxn.id));
      setActionMessage(`Reclassified transaction #${selectedTxn.id} to "${newCategory}".`);
    }
    fetchQueue();
    if (onActionComplete) onActionComplete();
  };

  const formatCurrency = (amount: number) => {
    const formatted = Math.abs(amount).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return amount < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  const lowConfidenceCount = items.filter((i) => (i.confidence ?? 1) < 0.85).length;
  const nonPnLCount = items.filter((i) => i.pnl_bucket === "Non-P&L").length;

  return (
    <div className="space-y-6">
      {/* Overview Metric Pills */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.05 }}
          className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
        >
          <span className="text-xs text-[var(--color-muted)] font-medium">Pending Review Items</span>
          <div className="text-2xl font-bold text-[var(--color-ink)] mt-1 font-mono">
            {items.length}
          </div>
          <div className="text-[11px] text-[var(--color-muted)] mt-0.5">
            Require human verification
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.1 }}
          className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
        >
          <span className="text-xs text-[var(--color-muted)] font-medium">Low Confidence Flag (&lt;85%)</span>
          <div className="text-2xl font-bold text-amber-700 mt-1 font-mono">
            {lowConfidenceCount}
          </div>
          <div className="text-[11px] text-[var(--color-muted)] mt-0.5">
            Ambiguous descriptions / vendors
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.15 }}
          className="bg-[#ffffff] rounded-xl p-4 border border-[var(--color-hairline)] shadow-xs"
        >
          <span className="text-xs text-[var(--color-muted)] font-medium">Balance Sheet / CapEx</span>
          <div className="text-2xl font-bold text-slate-800 mt-1 font-mono">
            {nonPnLCount}
          </div>
          <div className="text-[11px] text-[var(--color-muted)] mt-0.5">
            Non-P&amp;L asset purchases &amp; tax remittances
          </div>
        </motion.div>
      </div>

      {/* Action Toast Feedback */}
      <AnimatePresence>
        {actionMessage && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{actionMessage}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="text-xs font-semibold hover:underline cursor-pointer"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Queue Toolbar */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <h3 className="text-lg font-bold tracking-tight text-[var(--color-ink)]">
            Items Requiring Review
          </h3>
          <p className="text-xs text-[var(--color-muted)]">
            Verify accounting treatment, confirm proposed classification, or assign to standard Chart of Accounts.
          </p>
        </div>

        <motion.button
          onClick={fetchQueue}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.05 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.95 }}
          className="p-2 rounded-xl border border-[var(--color-hairline)] text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
          title="Refresh review queue"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </motion.button>
      </div>

      {/* Flagged Item Cards List with AnimatePresence */}
      {items.length === 0 ? (
        <div className="bg-[#ffffff] rounded-2xl p-12 border border-[var(--color-hairline)] text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 mx-auto rounded-full bg-[var(--color-brand-mint)]/40 flex items-center justify-center text-[var(--color-brand-teal)] font-bold">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h4 className="text-base font-bold text-[var(--color-ink)]">
              All Transactions Verified
            </h4>
            <p className="text-xs text-[var(--color-muted)] max-w-sm mx-auto">
              No transactions currently flagged for review. Any classification with confidence &lt; 0.85 or balance sheet treatment will automatically appear here.
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <AnimatePresence mode="popLayout">
            {items.map((item) => (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{
                  opacity: 0,
                  scale: shouldReduceMotion ? 1 : 0.95,
                  x: shouldReduceMotion ? 0 : 16,
                  transition: { duration: 0.2 },
                }}
                className="bg-[#ffffff] rounded-2xl p-5 border border-[var(--color-hairline)] hover:border-[var(--color-muted)] transition-all shadow-xs space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-semibold text-[var(--color-muted)]">
                        {item.transaction_code} • {item.date}
                      </span>

                      {/* Confidence Pill */}
                      {item.confidence !== null && (
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold border ${
                            item.confidence >= 0.85
                              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                              : "bg-amber-100 text-amber-900 border-amber-300"
                          }`}
                        >
                          {Math.round(item.confidence * 100)}% Confidence
                        </span>
                      )}

                      {/* Non-P&L Badge */}
                      {item.pnl_bucket === "Non-P&L" && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-800 border border-slate-300 font-semibold">
                          Balance Sheet Item
                        </span>
                      )}
                    </div>

                    <h4 className="text-sm font-semibold text-[var(--color-ink)]">
                      {item.description}
                    </h4>

                    {item.counterparty && (
                      <p className="text-xs text-[var(--color-body)]">
                        Counterparty: <strong className="text-[var(--color-ink)]">{item.counterparty}</strong>
                      </p>
                    )}
                  </div>

                  {/* Amount */}
                  <div className="text-right">
                    <span
                      className={`text-base font-bold font-mono ${
                        item.amount >= 0 ? "text-emerald-600" : "text-[var(--color-ink)]"
                      }`}
                    >
                      {formatCurrency(item.amount)}
                    </span>
                    <span className="block text-[11px] text-[var(--color-muted)]">
                      {item.method || "Bank Transfer"}
                    </span>
                  </div>
                </div>

                {/* Proposed Classification & Explanation */}
                <div className="bg-[var(--color-canvas)] rounded-xl p-3 border border-[var(--color-hairline)] text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--color-muted)] font-medium">Proposed:</span>
                    <span className="px-2.5 py-0.5 rounded-full bg-[var(--color-surface-soft)] font-bold text-[var(--color-ink)] border border-[var(--color-hairline)]">
                      {item.category || "Uncategorized"}
                    </span>
                    <span className="text-[11px] text-[var(--color-muted)]">({item.pnl_bucket})</span>
                  </div>

                  {item.rationale && (
                    <div className="text-[11px] text-[var(--color-muted)] italic max-w-md truncate" title={item.rationale}>
                      &ldquo;{item.rationale}&rdquo;
                    </div>
                  )}
                </div>

                {/* Triage Action Buttons */}
                <div className="flex items-center justify-end gap-2 pt-1">
                  <motion.button
                    type="button"
                    onClick={() => handleDismiss(item)}
                    disabled={actionLoadingId === item.id}
                    whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                    whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                    className="px-3.5 py-1.5 rounded-xl border border-[var(--color-hairline)] text-xs font-semibold text-[var(--color-body)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
                  >
                    Dismiss Flag
                  </motion.button>

                  <motion.button
                    type="button"
                    onClick={() => {
                      setSelectedTxn(item);
                      setIsModalOpen(true);
                    }}
                    disabled={actionLoadingId === item.id}
                    whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                    whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                    className="px-3.5 py-1.5 rounded-xl bg-[var(--color-brand-peach)] text-[var(--color-ink)] text-xs font-semibold hover:bg-[var(--color-brand-peach)]/80 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Correct Classification</span>
                  </motion.button>

                  <motion.button
                    type="button"
                    onClick={() => handleConfirm(item)}
                    disabled={actionLoadingId === item.id}
                    whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
                    whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                    className="px-4 py-1.5 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold hover:bg-[var(--color-primary-active)] disabled:opacity-50 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm</span>
                  </motion.button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Audit Trail Section */}
      <div className="space-y-3 pt-4 border-t border-[var(--color-hairline)]">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-[var(--color-muted)]" />
          <h4 className="text-sm font-bold text-[var(--color-ink)]">
            Audit Trail (Recent Human &amp; Model Corrections)
          </h4>
        </div>

        {auditLogs.length === 0 ? (
          <div className="text-xs text-[var(--color-muted)] italic">
            No audit log entries recorded yet. Manual corrections and confirmations will appear here.
          </div>
        ) : (
          <div className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[var(--color-surface-soft)] border-b border-[var(--color-hairline)] text-[var(--color-muted)] font-medium">
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Transaction</th>
                  <th className="py-2.5 px-4">Previous Category</th>
                  <th className="py-2.5 px-4">New Category</th>
                  <th className="py-2.5 px-4">Source / Reviewer</th>
                  <th className="py-2.5 px-4">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-hairline)]">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-[var(--color-canvas)]/50 transition-colors">
                    <td className="py-2.5 px-4 font-mono text-[var(--color-muted)]">
                      {log.created_at ? new Date(log.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                    <td className="py-2.5 px-4 font-mono font-medium text-[var(--color-ink)]">
                      {log.transaction_code}
                    </td>
                    <td className="py-2.5 px-4 text-[var(--color-muted)]">
                      {log.previous_category || "None"}
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-emerald-800">
                      {log.new_category}
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded-full bg-[var(--color-surface-soft)] text-[11px] font-medium border border-[var(--color-hairline)]">
                        {log.source}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 text-[var(--color-body)] max-w-xs truncate" title={log.note || ""}>
                      {log.note || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reclassification Modal */}
      <CorrectionModal
        transaction={selectedTxn}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedTxn(null);
        }}
        onSuccess={handleCorrectionSuccess}
      />
    </div>
  );
}
