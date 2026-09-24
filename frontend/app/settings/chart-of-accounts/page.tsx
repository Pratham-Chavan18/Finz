"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Layers,
  Plus,
  Trash2,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Building2,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function ChartOfAccountsPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<{
    standard_accounts: Array<{ category: string; pnl_bucket: string; description: string }>;
    buckets: string[];
    custom_mappings: Array<{ id: number; raw_pattern: string; target_category: string; target_bucket: string }>;
  } | null>(null);

  const [rawPattern, setRawPattern] = useState("");
  const [targetCategory, setTargetCategory] = useState("Food Inventory / Supplies");
  const [targetBucket, setTargetBucket] = useState("COGS");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/settings/chart-of-accounts");
    }
  }, [isLoading, isAuthenticated, router]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/api/v1/settings/chart-of-accounts");
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch {
      setError("Failed to load chart of accounts settings.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const handleAddMapping = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawPattern.trim()) return;

    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const res = await apiFetch("/api/v1/settings/chart-of-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          raw_pattern: rawPattern.trim(),
          target_category: targetCategory,
          target_bucket: targetBucket,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create mapping rule.");
      }

      setMessage(`Mapping saved for '${rawPattern.trim()}'.`);
      setRawPattern("");
      loadData();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      const res = await apiFetch(`/api/v1/settings/chart-of-accounts/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setMessage("Mapping removed.");
        loadData();
      }
    } catch {
      setError("Failed to delete mapping.");
    }
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] text-stone-900 flex flex-col font-sans">
      {/* Top Bar */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-stone-200/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/app"
            className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-100 text-stone-700 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-base font-bold text-stone-900 tracking-tight flex items-center gap-2">
              <Layers className="w-4 h-4 text-stone-700" />
              Chart of Accounts & Category Mapping
            </h1>
            <p className="text-xs text-stone-500">Configure tenant-specific accounting classification rules.</p>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto p-6 md:p-8 space-y-8">
        {message && (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            {message}
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
            {error}
          </div>
        )}

        {/* Add Custom Mapping Card */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-stone-900">Add Tenant Mapping Override</h2>
              <p className="text-xs text-stone-500 mt-0.5">
                Automatically route transactions matching this keyword to a specific P&L category.
              </p>
            </div>
          </div>

          <form onSubmit={handleAddMapping} className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2">
            <div>
              <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                Keyword / Payee Pattern
              </label>
              <input
                type="text"
                placeholder="e.g. Sysco, Toast, Uber"
                value={rawPattern}
                onChange={(e) => setRawPattern(e.target.value)}
                className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                Target Category
              </label>
              <select
                value={targetCategory}
                onChange={(e) => {
                  setTargetCategory(e.target.value);
                  const found = data?.standard_accounts.find((a) => a.category === e.target.value);
                  if (found) setTargetBucket(found.pnl_bucket);
                }}
                className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
              >
                {data?.standard_accounts.map((acc) => (
                  <option key={acc.category} value={acc.category}>
                    {acc.category} ({acc.pnl_bucket})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                P&L Bucket
              </label>
              <select
                value={targetBucket}
                onChange={(e) => setTargetBucket(e.target.value)}
                className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
              >
                <option value="Revenue">Revenue</option>
                <option value="COGS">COGS</option>
                <option value="Payroll">Payroll</option>
                <option value="Operating Expenses">Operating Expenses</option>
                <option value="Non-P&L">Non-P&L</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                type="submit"
                disabled={saving || !rawPattern.trim()}
                className="w-full py-2 px-4 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Add Mapping
              </button>
            </div>
          </form>
        </div>

        {/* Custom Mappings Table */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-stone-900">
            Active Tenant Mappings ({data?.custom_mappings.length || 0})
          </h2>

          {loading ? (
            <div className="py-8 text-center text-xs text-stone-500">Loading custom mappings...</div>
          ) : !data?.custom_mappings || data.custom_mappings.length === 0 ? (
            <div className="py-8 text-center text-xs text-stone-500 bg-stone-50 rounded-xl border border-stone-200/60">
              No custom mapping rules added yet. Standard Chart of Accounts categorization is active.
            </div>
          ) : (
            <div className="divide-y divide-stone-100">
              {data.custom_mappings.map((m) => (
                <div key={m.id} className="py-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-semibold px-2 py-0.5 rounded bg-stone-100 text-stone-800 border border-stone-200">
                      "{m.raw_pattern}"
                    </span>
                    <span className="text-stone-400">→</span>
                    <span className="font-semibold text-stone-900">{m.target_category}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-stone-100 text-stone-600 border border-stone-200">
                      {m.target_bucket}
                    </span>
                  </div>
                  <button
                    onClick={() => handleDelete(m.id)}
                    className="p-1.5 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Standard Accounts Reference */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-6 shadow-sm space-y-4">
          <h2 className="text-sm font-bold text-stone-900">Standard FinReview Chart of Accounts</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data?.standard_accounts.map((acc, idx) => (
              <div key={idx} className="p-3 bg-stone-50 rounded-xl border border-stone-200/60 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-900">{acc.category}</span>
                  <span className="px-2 py-0.5 rounded bg-white text-[10px] font-mono text-stone-600 border border-stone-200">
                    {acc.pnl_bucket}
                  </span>
                </div>
                <p className="text-[11px] text-stone-500 mt-1">{acc.description}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
