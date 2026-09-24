"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  TrendingUp,
  MessageSquare,
  ShieldCheck,
  ArrowRight,
  Database,
  BarChart3,
  Layers,
  Sparkles,
  LogOut,
  User as UserIcon,
  ChevronDown,
  Loader2,
  Building2,
  Users,
  Settings,
  Compass,
} from "lucide-react";
import IngestionDropzone from "@/components/IngestionDropzone";
import TransactionTable from "@/components/TransactionTable";
import PnLStatement from "@/components/PnLStatement";
import VarianceCards from "@/components/VarianceCards";
import ReviewQueue from "@/components/ReviewQueue";
import AIAnalyst from "@/components/AIAnalyst";
import TraceabilityDrawer from "@/components/TraceabilityDrawer";
import { useAuth } from "@/context/AuthContext";
import { apiFetch, API_BASE_URL } from "@/lib/api";

type WorkflowTab = "overview" | "ingest" | "transactions" | "review" | "pnl" | "variances" | "chat";

const WORKFLOW_TABS: { id: WorkflowTab; label: string; icon?: React.ReactNode; badge?: boolean }[] = [
  { id: "overview", label: "Overview" },
  { id: "ingest", label: "1. Ingest" },
  { id: "transactions", label: "2. Transactions" },
  { id: "review", label: "3. Review", badge: true },
  { id: "pnl", label: "4. P&L Statement" },
  { id: "variances", label: "5. Variances" },
  { id: "chat", label: "6. AI Analyst", icon: <Sparkles className="w-3.5 h-3.5 text-stone-700" /> },
];

export default function AppPage() {
  const router = useRouter();
  const shouldReduceMotion = useReducedMotion();
  const { user, isLoading, isAuthenticated, logout } = useAuth();

  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [activeTab, setActiveTab] = useState<WorkflowTab>("overview");
  const [refreshKey, setRefreshKey] = useState(0);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Tenant state
  const [tenant, setTenant] = useState<any>(null);

  // Traceability Drawer state
  const [traceabilityOpen, setTraceabilityOpen] = useState(false);
  const [selectedMetric, setSelectedMetric] = useState<{ key: string; label: string; month?: string }>({
    key: "operating_profit",
    label: "Operating Profit (EBITDA)",
  });

  // Close user menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Redirect to /login if unauthenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/app");
    }
  }, [isLoading, isAuthenticated, router]);

  // Load tenant metadata
  useEffect(() => {
    if (isAuthenticated) {
      apiFetch("/api/v1/tenants/current")
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setTenant(data);
        })
        .catch(() => {});
    }
  }, [isAuthenticated, refreshKey]);

  const checkBackend = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/health`, { cache: "no-store" });
      if (res.ok) {
        setBackendStatus("online");
      } else {
        setBackendStatus("offline");
      }
    } catch {
      setBackendStatus("offline");
    }
  };

  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRefreshAll = () => {
    setRefreshKey((k) => k + 1);
  };

  const openTraceability = (key: string, label: string, month?: string) => {
    setSelectedMetric({ key, label, month });
    setTraceabilityOpen(true);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#faf8f5] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-stone-700" />
          <p className="text-xs text-stone-600 font-medium">Loading FinReview Workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#faf8f5] text-stone-900 flex flex-col font-sans">
      {/* Top Application Navigation */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-stone-200/80 px-6 py-3 flex items-center justify-between shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        {/* Left: Brand + Tenant Switcher */}
        <div className="flex items-center gap-5">
          <Link href="/app" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded-lg bg-stone-900 flex items-center justify-center text-white font-bold text-sm shadow-sm group-hover:bg-stone-800 transition-colors">
              F
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-bold text-base tracking-tight text-stone-900">FinReview</span>
              <span className="text-[10px] uppercase tracking-wider font-semibold text-stone-600 bg-stone-100 px-1.5 py-0.5 rounded border border-stone-200">
                SaaS
              </span>
            </div>
          </Link>

          {/* Tenant Workspace Badge */}
          {tenant && (
            <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-stone-50 border border-stone-200 rounded-lg text-xs">
              <Building2 className="w-3.5 h-3.5 text-stone-600" />
              <span className="font-medium text-stone-800 truncate max-w-[160px]">{tenant.name}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-stone-200/70 text-stone-700 uppercase">
                {tenant.plan}
              </span>
            </div>
          )}
        </div>

        {/* Center: Workflow Tabs */}
        <nav className="hidden md:flex items-center gap-1 bg-stone-100/80 p-1 rounded-xl border border-stone-200/60">
          {WORKFLOW_TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                data-testid={`tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  isActive
                    ? "bg-white text-stone-900 shadow-sm border border-stone-200/60"
                    : "text-stone-700 hover:text-stone-900 hover:bg-white/50"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Right: User Menu & Quick Links */}
        <div className="flex items-center gap-3">
          <Link
            href="/onboarding"
            className="hidden lg:inline-flex items-center gap-1.5 text-xs text-stone-700 hover:text-stone-900 font-medium px-2.5 py-1.5 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <Compass className="w-3.5 h-3.5" />
            Setup Guide
          </Link>

          <Link
            href="/settings/chart-of-accounts"
            className="hidden lg:inline-flex items-center gap-1.5 text-xs text-stone-700 hover:text-stone-900 font-medium px-2.5 py-1.5 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <Layers className="w-3.5 h-3.5" />
            Chart of Accounts
          </Link>

          <Link
            href="/settings/team"
            className="hidden lg:inline-flex items-center gap-1.5 text-xs text-stone-700 hover:text-stone-900 font-medium px-2.5 py-1.5 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <Users className="w-3.5 h-3.5" />
            Team
          </Link>

          {/* User Dropdown */}
          <div className="relative" ref={userMenuRef}>
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-stone-100 border border-stone-200 transition-colors"
            >
              <div className="w-6 h-6 rounded-full bg-stone-900 text-white flex items-center justify-center text-xs font-semibold">
                {user?.name?.[0]?.toUpperCase() || "U"}
              </div>
              <span className="text-xs font-medium text-stone-800 hidden sm:inline">{user?.name || user?.email}</span>
              <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200">
                {user?.role || "VIEWER"}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-stone-600" />
            </button>

            {userMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white border border-stone-200 rounded-xl shadow-lg py-1.5 z-50 text-xs">
                <div className="px-3 py-2 border-b border-stone-100">
                  <div className="font-semibold text-stone-900">{user?.name}</div>
                  <div className="text-[11px] text-stone-600 truncate">{user?.email}</div>
                  {tenant && (
                    <div className="text-[10px] text-stone-600 mt-1 flex items-center gap-1">
                      <Building2 className="w-3 h-3 text-stone-600" />
                      {tenant.name}
                    </div>
                  )}
                </div>

                <Link
                  href="/onboarding"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-stone-50 text-stone-700"
                >
                  <Compass className="w-3.5 h-3.5" />
                  Onboarding Wizard
                </Link>

                <Link
                  href="/settings/chart-of-accounts"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-stone-50 text-stone-700"
                >
                  <Layers className="w-3.5 h-3.5" />
                  Chart of Accounts Mapping
                </Link>

                <Link
                  href="/settings/team"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 hover:bg-stone-50 text-stone-700"
                >
                  <Users className="w-3.5 h-3.5" />
                  Team & Permissions
                </Link>

                <div className="border-t border-stone-100 mt-1 pt-1">
                  <button
                    onClick={async () => {
                      setUserMenuOpen(false);
                      await logout();
                      router.push("/");
                    }}
                    className="w-full text-left flex items-center gap-2 px-3 py-2 hover:bg-red-50 text-red-600 font-medium"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Sign Out
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Mobile Tab Navigation */}
      <div className="md:hidden flex overflow-x-auto bg-white border-b border-stone-200 px-4 py-2 gap-2 text-xs">
        {WORKFLOW_TABS.map((tab) => (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id}-mobile`}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap font-medium ${
              activeTab === tab.id ? "bg-stone-900 text-white" : "bg-stone-100 text-stone-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8">
        {/* OVERVIEW TAB */}
        {activeTab === "overview" && (
          <div className="space-y-8">
            {/* Header Banner */}
            <div className="bg-white border border-stone-200/90 rounded-2xl p-6 sm:p-8 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200/80">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  Deterministic Financial Engine • PostgreSQL RLS Active
                </div>
                <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-stone-900">
                  {tenant?.name || "Financial Review"} Workspace
                </h1>
                <p className="text-sm text-stone-600 max-w-2xl">
                  End-to-end explainable review workflow: Ingest transactions, automate classification,
                  triage uncertain items, compute exact mathematical P&L, and investigate variances with Ollama AI.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => openTraceability("operating_profit", "Operating Profit (EBITDA)")}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold rounded-xl transition-colors border border-stone-200"
                >
                  <Database className="w-3.5 h-3.5 text-stone-600" />
                  Inspect Operating Profit Origin
                </button>

                <button
                  onClick={() => setActiveTab("ingest")}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition-colors shadow-sm"
                >
                  <UploadCloud className="w-3.5 h-3.5" />
                  Ingest Transactions
                </button>
              </div>
            </div>

            {/* Quick KPIs / Summary */}
            <PnLStatement key={`pnl-summary-${refreshKey}`} onDataChanged={handleRefreshAll} onMetricClick={openTraceability} />

            {/* Variance Cards */}
            <VarianceCards key={`var-summary-${refreshKey}`} />

            {/* Review Queue Preview */}
            <ReviewQueue key={`rev-summary-${refreshKey}`} onActionComplete={handleRefreshAll} />
          </div>
        )}

        {/* 1. INGEST TAB */}
        {activeTab === "ingest" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-stone-900">1. Data Ingestion</h2>
              <p className="text-xs text-stone-600 mt-1">
                Upload raw CSV bank statements or load the bundled sample dataset. All records are scoped to your company workspace.
              </p>
            </div>
            <IngestionDropzone
              onIngestSuccess={() => {
                handleRefreshAll();
                setActiveTab("transactions");
              }}
            />
          </div>
        )}

        {/* 2. TRANSACTIONS TAB */}
        {activeTab === "transactions" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold tracking-tight text-stone-900">2. Stored Transactions</h2>
                <p className="text-xs text-stone-600 mt-1">
                  Filter, search, and verify all ingested ledger entries. Click any category to manually override.
                </p>
              </div>
            </div>
            <TransactionTable key={`tx-tab-${refreshKey}`} onRefreshTrigger={handleRefreshAll} />
          </div>
        )}

        {/* 3. REVIEW TAB */}
        {activeTab === "review" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-stone-900">3. Human Review & Audit Trail</h2>
              <p className="text-xs text-stone-600 mt-1">
                Ambiguous transactions, low-confidence classifications, and material capital expenditures flagged for verification.
              </p>
            </div>
            <ReviewQueue key={`rev-tab-${refreshKey}`} onActionComplete={handleRefreshAll} />
          </div>
        )}

        {/* 4. P&L TAB */}
        {activeTab === "pnl" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold tracking-tight text-stone-900">4. Monthly P&L Statement</h2>
                <p className="text-xs text-stone-600 mt-1">
                  Authoritative financial statement computed deterministically via PostgreSQL numeric aggregations.
                </p>
              </div>
            </div>
            <PnLStatement key={`pnl-tab-${refreshKey}`} onDataChanged={handleRefreshAll} onMetricClick={openTraceability} />
          </div>
        )}

        {/* 5. VARIANCES TAB */}
        {activeTab === "variances" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-stone-900">5. Month-over-Month Variances</h2>
              <p className="text-xs text-stone-600 mt-1">
                Automated driver analysis highlighting favorable vs. unfavorable line-item changes exceeding materiality thresholds.
              </p>
            </div>
            <VarianceCards key={`var-tab-${refreshKey}`} />
          </div>
        )}

        {/* 6. CHAT TAB */}
        {activeTab === "chat" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-bold tracking-tight text-stone-900">6. AI Financial Analyst</h2>
              <p className="text-xs text-stone-600 mt-1">
                Source-grounded financial assistant powered by Ollama with tenant-isolated database tools.
              </p>
            </div>
            <AIAnalyst key={`chat-tab-${refreshKey}`} />
          </div>
        )}
      </main>

      {/* Global Traceability Drawer */}
      <TraceabilityDrawer
        isOpen={traceabilityOpen}
        onClose={() => setTraceabilityOpen(false)}
        metricKey={selectedMetric.key}
        metricLabel={selectedMetric.label}
        month={selectedMetric.month}
      />

      {/* Bottom Footer */}
      <footer className="border-t border-stone-200/80 bg-white/50 py-5 text-center text-xs text-stone-600">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-stone-800">FinReview</span> • Production B2B Financial SaaS
          </div>
          <div className="flex items-center gap-4 text-stone-600">
            <span>Deterministic PostgreSQL Math</span>
            <span>•</span>
            <span>Tenant Isolated Caching</span>
            <span>•</span>
            <span>Ollama Assisted</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
