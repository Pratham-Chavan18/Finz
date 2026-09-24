"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  ShieldCheck,
  ArrowRight,
  TrendingUp,
  FileSpreadsheet,
  Layers,
  Sparkles,
  Database,
  Lock,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  ChevronRight,
  Search,
  Users,
  Building2,
  FileText,
  BarChart3,
  Terminal,
} from "lucide-react";
import TraceabilityDrawer from "@/components/TraceabilityDrawer";
import { useAuth } from "@/context/AuthContext";
import { API_BASE_URL } from "@/lib/api";

interface DemoSummary {
  mode: "sample" | "empty";
  workspace_label?: string;
  transactions_analyzed?: number;
  review_period?: string;
  revenue?: string;
  gross_profit?: string;
  operating_profit?: string;
  review_items?: number;
  categorized_count?: number;
}

export default function LandingPage() {
  const router = useRouter();
  const shouldReduceMotion = useReducedMotion();
  const { user, isAuthenticated } = useAuth();

  const [demoSummary, setDemoSummary] = useState<DemoSummary | null>(null);
  const [loadingDemo, setLoadingDemo] = useState(true);

  // Traceability Demo Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [demoMetric, setDemoMetric] = useState({
    key: "operating_profit",
    label: "Operating Profit (EBITDA)",
  });

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/public/demo-summary`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setDemoSummary(data);
      })
      .catch(() => {
        setDemoSummary({ mode: "empty" });
      })
      .finally(() => {
        setLoadingDemo(false);
      });
  }, []);

  const fadeIn = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
  };

  const stagger = {
    visible: {
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] text-stone-900 font-sans selection:bg-stone-200">
      {/* 1. PUBLIC NAVBAR */}
      <header className="sticky top-0 z-40 bg-[#faf8f5]/80 backdrop-blur-md border-b border-stone-200/80 px-6 sm:px-12 py-4 flex items-center justify-between transition-colors">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-stone-900 flex items-center justify-center text-white font-bold text-base shadow-sm group-hover:bg-stone-800 transition-colors">
              F
            </div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-bold text-lg tracking-tight text-stone-900">FinReview</span>
              <span className="hidden sm:inline-block text-[10px] uppercase tracking-wider font-semibold text-stone-700 bg-stone-100 px-1.5 py-0.5 rounded border border-stone-200">
                SaaS
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-xs font-medium text-stone-700">
            <a href="#how-it-works" className="hover:text-stone-900 transition-colors">
              How it Works
            </a>
            <a href="#features" className="hover:text-stone-900 transition-colors">
              Features
            </a>
            <a href="#traceability" className="hover:text-stone-900 transition-colors">
              Traceability
            </a>
            <a href="#architecture" className="hover:text-stone-900 transition-colors">
              Architecture
            </a>
            <a href="#security" className="hover:text-stone-900 transition-colors">
              Security
            </a>
            <a href="#pricing" className="hover:text-stone-900 transition-colors">
              Pricing
            </a>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <Link
              href="/app"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
            >
              Go to Workspace
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="px-3.5 py-2 text-xs font-semibold text-stone-700 hover:text-stone-900 transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
              >
                Start Free
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </>
          )}
        </div>
      </header>

      {/* 2. HERO SECTION */}
      <section className="pt-20 pb-16 px-6 sm:px-12 max-w-6xl mx-auto text-center">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={stagger}
          className="space-y-6 max-w-4xl mx-auto"
        >
          <motion.div variants={fadeIn} className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium bg-white border border-stone-200 shadow-sm text-stone-700">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Deterministic Financial Engine + Ollama AI Reasoning
          </motion.div>

          <motion.h1
            variants={fadeIn}
            className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-stone-900 leading-[1.12]"
          >
            Turn raw transactions into an{" "}
            <span className="underline decoration-stone-300 underline-offset-8">explainable</span> financial review.
          </motion.h1>

          <motion.p
            variants={fadeIn}
            className="text-base sm:text-lg text-stone-700 max-w-2xl mx-auto leading-relaxed"
          >
            FinReview ingests financial transactions, categorizes them, calculates your P&L deterministically,
            explains material variances, and lets your team investigate the underlying evidence with AI.
          </motion.p>

          <motion.div variants={fadeIn} className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-6 py-3 bg-stone-900 hover:bg-stone-800 text-white text-sm font-semibold rounded-xl transition-all shadow-sm"
            >
              Start Free
              <ArrowRight className="w-4 h-4" />
            </Link>

            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 px-6 py-3 bg-white hover:bg-stone-50 text-stone-800 text-sm font-semibold rounded-xl border border-stone-200 transition-all shadow-sm"
            >
              Explore FinReview
            </a>
          </motion.div>
        </motion.div>

        {/* 3. HERO PRODUCT PREVIEW VISUAL */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-14 max-w-5xl mx-auto bg-white border border-stone-200/90 rounded-2xl shadow-xl overflow-hidden text-left"
        >
          {/* Mockup Window Header */}
          <div className="px-6 py-3.5 bg-stone-50 border-b border-stone-200 flex items-center justify-between text-xs text-stone-700">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-stone-300" />
              <span className="w-2.5 h-2.5 rounded-full bg-stone-300" />
              <span className="w-2.5 h-2.5 rounded-full bg-stone-300" />
              <span className="ml-2 font-mono text-[11px] text-stone-600">FinReview • NYC Restaurant Co.</span>
            </div>
            <span className="text-[11px] font-semibold text-stone-700 bg-white px-2 py-0.5 rounded border border-stone-200">
              Sample workspace
            </span>
          </div>

          {/* Mockup Body Content */}
          <div className="p-6 sm:p-8 space-y-6 bg-gradient-to-b from-white to-stone-50/50">
            {/* KPI Cards Row */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div
                onClick={() => {
                  setDemoMetric({ key: "revenue", label: "Top-Line Revenue" });
                  setDrawerOpen(true);
                }}
                className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm hover:border-stone-400 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between text-xs text-stone-700 mb-1">
                  <span>Revenue</span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-xl sm:text-2xl font-bold font-mono text-stone-900">
                  {demoSummary?.revenue || "$396,351"}
                </div>
                <div className="text-[11px] text-emerald-700 mt-1 flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  Top-line sales
                </div>
              </div>

              <div
                onClick={() => {
                  setDemoMetric({ key: "gross_profit", label: "Gross Profit" });
                  setDrawerOpen(true);
                }}
                className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm hover:border-stone-400 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between text-xs text-stone-700 mb-1">
                  <span>Gross Profit</span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-xl sm:text-2xl font-bold font-mono text-stone-900">
                  {demoSummary?.gross_profit || "$253,880"}
                </div>
                <div className="text-[11px] text-stone-700 mt-1">64.1% Gross Margin</div>
              </div>

              <div
                onClick={() => {
                  setDemoMetric({ key: "operating_profit", label: "Operating Profit (EBITDA)" });
                  setDrawerOpen(true);
                }}
                className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm hover:border-stone-400 transition-all cursor-pointer group"
              >
                <div className="flex items-center justify-between text-xs text-stone-700 mb-1">
                  <span>Operating Profit</span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-xl sm:text-2xl font-bold font-mono text-emerald-700">
                  {demoSummary?.operating_profit || "$30,181"}
                </div>
                <div className="text-[11px] text-stone-700 mt-1">Deterministic Math</div>
              </div>

              <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm">
                <div className="text-xs text-stone-700 mb-1">Review Queue</div>
                <div className="text-xl sm:text-2xl font-bold font-mono text-amber-700">
                  {demoSummary?.review_items ?? 5} items
                </div>
                <div className="text-[11px] text-stone-700 mt-1">Human-in-the-loop</div>
              </div>
            </div>

            {/* Split Preview: AI Analyst & Review Queue */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {/* Review Queue Preview Card */}
              <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-stone-800 flex items-center gap-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                    Review Required: Equipment Purchase
                  </span>
                  <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-800 text-[10px] font-semibold border border-amber-200">
                    Flagged
                  </span>
                </div>
                <div className="p-3 bg-stone-50 rounded-lg text-xs space-y-1">
                  <div className="flex justify-between font-mono font-medium">
                    <span>Hobart Commercial Mixer</span>
                    <span className="text-stone-900">$4,250.00</span>
                  </div>
                  <p className="text-[11px] text-stone-700">
                    Flagged as CapEx Asset: Long-term capitalized equipment must not distort Operating Expenses.
                  </p>
                </div>
              </div>

              {/* AI Analyst Preview Card */}
              <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-stone-800 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-stone-700" />
                    AI Analyst: "Why did operating profit change?"
                  </span>
                  <span className="px-2 py-0.5 rounded bg-stone-100 text-stone-700 text-[10px] font-mono">
                    Ollama Tool-Grounded
                  </span>
                </div>
                <div className="p-3 bg-stone-50 rounded-lg text-xs text-stone-700 space-y-1">
                  <p>
                    "Operating profit decreased from <span className="font-mono font-semibold">$15,420</span> in Jan to{" "}
                    <span className="font-mono font-semibold">$7,925</span> in Feb. Top driver was a{" "}
                    <span className="font-semibold text-stone-900">+$3,450 surge in Linen & Laundry</span> and a{" "}
                    <span className="font-semibold text-stone-900">-$2,100 dip in Beverage Sales</span>."
                  </p>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* 4. LIVE PROJECT DATA SECTION ("Financial Intelligence Snapshot") */}
      <section className="py-16 bg-white border-y border-stone-200/80 px-6 sm:px-12">
        <div className="max-w-5xl mx-auto space-y-8">
          <div className="text-center space-y-2">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-stone-100 text-stone-700 border border-stone-200">
              <Database className="w-3.5 h-3.5 text-stone-600" />
              Live Project Data • Sanitized Demo
            </div>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-stone-900">
              Financial Intelligence Snapshot
            </h2>
            <p className="text-xs sm:text-sm text-stone-700 max-w-lg mx-auto">
              Real calculations retrieved dynamically from our restaurant benchmark dataset.
            </p>
          </div>

          {loadingDemo ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 animate-pulse">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-24 bg-stone-100 rounded-xl" />
              ))}
            </div>
          ) : demoSummary?.mode === "empty" ? (
            <div className="p-8 text-center bg-stone-50 rounded-2xl border border-stone-200">
              <p className="text-sm font-semibold text-stone-700">No financial data connected yet.</p>
              <Link
                href="/register"
                className="mt-3 inline-flex items-center gap-1.5 px-4 py-2 bg-stone-900 text-white rounded-xl text-xs font-semibold"
              >
                Import your first dataset
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-5 bg-stone-50/70 border border-stone-200 rounded-2xl">
                <div className="text-xs text-stone-700">Transactions Analyzed</div>
                <div className="text-2xl font-bold font-mono text-stone-900 mt-1">
                  {demoSummary?.transactions_analyzed || 181}
                </div>
                <div className="text-[11px] text-stone-700 mt-0.5">100% Categorized</div>
              </div>

              <div className="p-5 bg-stone-50/70 border border-stone-200 rounded-2xl">
                <div className="text-xs text-stone-700">Review Period</div>
                <div className="text-lg font-bold font-mono text-stone-900 mt-1">
                  {demoSummary?.review_period || "Jan - Mar 2026"}
                </div>
                <div className="text-[11px] text-stone-700 mt-0.5">Quarterly Cohort</div>
              </div>

              <div className="p-5 bg-stone-50/70 border border-stone-200 rounded-2xl">
                <div className="text-xs text-stone-700">Net Operating Profit</div>
                <div className="text-2xl font-bold font-mono text-emerald-700 mt-1">
                  {demoSummary?.operating_profit || "$30,181"}
                </div>
                <div className="text-[11px] text-stone-700 mt-0.5">PostgreSQL Aggregated</div>
              </div>

              <div className="p-5 bg-stone-50/70 border border-stone-200 rounded-2xl">
                <div className="text-xs text-stone-700">Items Needing Review</div>
                <div className="text-2xl font-bold font-mono text-amber-700 mt-1">
                  {demoSummary?.review_items || 5}
                </div>
                <div className="text-[11px] text-stone-700 mt-0.5">Confidence &lt; 0.85</div>
              </div>
            </div>
          )}

          <div className="text-center text-xs text-stone-700">
            Workspace: <span className="font-semibold text-stone-700">FinReview sample workspace</span> • No private tenant data exposed.
          </div>
        </div>
      </section>

      {/* 5. HOW FINREVIEW WORKS (6-STEP WORKFLOW) */}
      <section id="how-it-works" className="py-20 px-6 sm:px-12 max-w-6xl mx-auto">
        <div className="text-center space-y-3 mb-14">
          <h2 className="text-3xl font-bold tracking-tight text-stone-900">How FinReview Works</h2>
          <p className="text-sm text-stone-700 max-w-xl mx-auto">
            A continuous, explainable workflow that transforms chaotic bank transactions into verifiable P&L intelligence.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            {
              step: "01",
              title: "Connect your data",
              desc: "Upload bank statement CSVs or integrate accounting streams. Every row is normalized into Python Decimals.",
              icon: FileSpreadsheet,
            },
            {
              step: "02",
              title: "Categorize transactions",
              desc: "Automated engine applies standard Chart of Accounts rules, detects vendor patterns, and scores classification confidence.",
              icon: Layers,
            },
            {
              step: "03",
              title: "Review uncertain items",
              desc: "Transactions with low confidence or CapEx classifications are routed to a human triage queue with immutable audit logging.",
              icon: AlertCircle,
            },
            {
              step: "04",
              title: "Generate deterministic P&L",
              desc: "Top-line revenue, COGS, payroll, and OpEx are calculated via PostgreSQL sums and Decimal arithmetic—never by an LLM.",
              icon: BarChart3,
            },
            {
              step: "05",
              title: "Investigate variances",
              desc: "MoM changes exceeding materiality thresholds are highlighted with favorable/unfavorable accounting polarity and driving transactions.",
              icon: TrendingUp,
            },
            {
              step: "06",
              title: "Ask the AI Analyst",
              desc: "Ask natural language questions. Ollama invokes backend financial tools to return source-grounded answers citing exact transaction IDs.",
              icon: Sparkles,
            },
          ].map((item, idx) => (
            <motion.div
              key={item.step}
              whileHover={{ y: -4 }}
              transition={{ duration: 0.2 }}
              className="p-6 bg-white border border-stone-200/90 rounded-2xl shadow-sm space-y-3 relative overflow-hidden"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-stone-600 bg-stone-100 px-2 py-0.5 rounded">
                  {item.step}
                </span>
                <item.icon className="w-5 h-5 text-stone-700" />
              </div>
              <h3 className="text-base font-bold text-stone-900">{item.title}</h3>
              <p className="text-xs text-stone-700 leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* 6. TRACEABILITY SECTION ("Every number has an origin.") */}
      <section id="traceability" className="py-20 bg-stone-900 text-white px-6 sm:px-12">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="text-center space-y-3">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-emerald-400">
              Auditability First
            </span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
              Every number has an origin.
            </h2>
            <p className="text-sm text-stone-400 max-w-xl mx-auto">
              FinReview doesn't just tell you what changed. It shows you the financial evidence behind the answer.
            </p>
          </div>

          {/* Traceability Flow Diagram */}
          <div className="p-6 sm:p-8 bg-stone-800/80 border border-stone-700 rounded-2xl space-y-6">
            <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 text-xs font-mono">
              <span className="px-3 py-1.5 rounded-lg bg-stone-700 text-stone-200 border border-stone-600">
                P&L Statement
              </span>
              <span className="text-stone-500">→</span>
              <span className="px-3 py-1.5 rounded-lg bg-emerald-950 text-emerald-300 border border-emerald-700 font-semibold">
                Operating Profit ($30,181)
              </span>
              <span className="text-stone-500">→</span>
              <span className="px-3 py-1.5 rounded-lg bg-stone-700 text-stone-200 border border-stone-600">
                MoM Variance
              </span>
              <span className="text-stone-500">→</span>
              <span className="px-3 py-1.5 rounded-lg bg-stone-700 text-stone-200 border border-stone-600">
                Category Driver
              </span>
              <span className="text-stone-500">→</span>
              <span className="px-3 py-1.5 rounded-lg bg-stone-700 text-stone-200 border border-stone-600">
                Underlying Transaction
              </span>
              <span className="text-stone-500">→</span>
              <span className="px-3 py-1.5 rounded-lg bg-stone-900 text-stone-300 border border-stone-700">
                TX-ID #142
              </span>
            </div>

            <div className="text-center pt-2">
              <button
                onClick={() => {
                  setDemoMetric({ key: "operating_profit", label: "Operating Profit (EBITDA)" });
                  setDrawerOpen(true);
                }}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-stone-950 text-xs font-bold rounded-xl transition-all shadow-md"
              >
                <Search className="w-3.5 h-3.5" />
                Click to Test Interactive Traceability Drawer
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* 7. AI + DETERMINISTIC ARCHITECTURE SECTION */}
      <section id="architecture" className="py-20 px-6 sm:px-12 max-w-5xl mx-auto">
        <div className="text-center space-y-3 mb-12">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-stone-700">
            System Design
          </span>
          <h2 className="text-3xl font-bold tracking-tight text-stone-900">
            AI explains the numbers. Your financial engine calculates them.
          </h2>
          <p className="text-sm text-stone-700 max-w-xl mx-auto">
            Strict separation between natural language reasoning and authoritative monetary math.
          </p>
        </div>

        {/* ASCII / Modern Architecture Box */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 sm:p-8 shadow-sm">
          <div className="max-w-md mx-auto space-y-3 font-mono text-xs text-center">
            <div className="p-3 bg-stone-100 rounded-xl font-semibold text-stone-800">
              USER QUESTION: "Why did gross margin drop in Feb?"
            </div>
            <div className="text-stone-600 font-bold">↓</div>
            <div className="p-3 bg-stone-900 text-white rounded-xl">
              AI MODEL ROUTER (Ollama nemotron-3-nano)
            </div>
            <div className="text-stone-600 font-bold">↓ (Calls get_monthly_pnl & get_variances)</div>
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-950 font-sans text-left space-y-1">
              <div className="font-bold text-xs uppercase font-mono text-emerald-800">
                Deterministic Financial Engine
              </div>
              <p className="text-xs text-emerald-900">
                PostgreSQL Aggregations + Python Decimal Math. Zero arithmetic delegated to LLMs.
              </p>
            </div>
            <div className="text-stone-600 font-bold">↓ (Returns exact numbers & transaction codes)</div>
            <div className="p-3 bg-stone-900 text-white rounded-xl">
              GROUNDED AI EXPLANATION WITH EVIDENCE CITATIONS
            </div>
          </div>
        </div>
      </section>

      {/* 8. SECURITY SECTION */}
      <section id="security" className="py-20 bg-white border-y border-stone-200/80 px-6 sm:px-12">
        <div className="max-w-5xl mx-auto space-y-12">
          <div className="text-center space-y-3">
            <span className="text-xs font-mono font-semibold uppercase tracking-wider text-stone-700">
              Enterprise Defense
            </span>
            <h2 className="text-3xl font-bold tracking-tight text-stone-900">
              Built for sensitive financial data.
            </h2>
            <p className="text-sm text-stone-700 max-w-xl mx-auto">
              Multi-tenant architecture ensuring no company's ledger or AI prompt history is ever shared.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-5 bg-stone-50 rounded-2xl border border-stone-200 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-stone-900 text-white flex items-center justify-center font-bold text-xs">
                <Lock className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-stone-900">PostgreSQL Row-Level Security</h3>
              <p className="text-xs text-stone-700 leading-relaxed">
                Every query enforces session-local tenant context. Database-level boundaries prevent cross-tenant queries.
              </p>
            </div>

            <div className="p-5 bg-stone-50 rounded-2xl border border-stone-200 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-stone-900 text-white flex items-center justify-center font-bold text-xs">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-stone-900">Append-Only Audit Trail</h3>
              <p className="text-xs text-stone-700 leading-relaxed">
                All manual overrides log user ID, timestamp, and previous/new categories. Audit logs cannot be deleted.
              </p>
            </div>

            <div className="p-5 bg-stone-50 rounded-2xl border border-stone-200 space-y-2">
              <div className="w-8 h-8 rounded-lg bg-stone-900 text-white flex items-center justify-center font-bold text-xs">
                <Users className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-stone-900">Role-Based Access (RBAC)</h3>
              <p className="text-xs text-stone-700 leading-relaxed">
                Admin, Accountant, and Viewer roles with strict server-side authorization enforcement.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 9. SAAS PRICING SECTION (NO STRIPE) */}
      <section id="pricing" className="py-20 px-6 sm:px-12 max-w-6xl mx-auto">
        <div className="text-center space-y-3 mb-14">
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-stone-700">
            Fair SaaS Pricing
          </span>
          <h2 className="text-3xl font-bold tracking-tight text-stone-900">
            Plans built for growing finance teams.
          </h2>
          <p className="text-sm text-stone-700 max-w-xl mx-auto">
            Choose the volume and reasoning power suited for your business.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* STARTER */}
          <div className="p-8 bg-white border border-stone-200 rounded-2xl shadow-sm space-y-6 flex flex-col justify-between">
            <div className="space-y-4">
              <div>
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-stone-700">
                  Starter
                </span>
                <div className="text-3xl font-bold font-mono text-stone-900 mt-2">$99</div>
                <div className="text-xs text-stone-700">per month, billed annually</div>
              </div>

              <div className="space-y-2.5 text-xs text-stone-700 border-t border-stone-100 pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>1,000 transactions / month</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>CSV Statement Ingestion</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Automated AI Categorization</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Deterministic Monthly P&L</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>50,000 monthly AI tokens</span>
                </div>
              </div>
            </div>

            <Link
              href="/register"
              className="w-full py-2.5 px-4 bg-stone-100 hover:bg-stone-200 text-stone-900 text-xs font-semibold rounded-xl text-center transition-colors"
            >
              Start Free
            </Link>
          </div>

          {/* PRO (FEATURED) */}
          <div className="p-8 bg-white border-2 border-stone-900 rounded-2xl shadow-md space-y-6 flex flex-col justify-between relative">
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-stone-900 text-white text-[10px] uppercase font-bold tracking-wider px-3 py-1 rounded-full">
              Most Popular
            </span>

            <div className="space-y-4">
              <div>
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-stone-700">
                  Pro
                </span>
                <div className="text-3xl font-bold font-mono text-stone-900 mt-2">$299</div>
                <div className="text-xs text-stone-700">per month, billed annually</div>
              </div>

              <div className="space-y-2.5 text-xs text-stone-700 border-t border-stone-100 pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="font-semibold text-stone-900">10,000 transactions / month</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>All Starter features included</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Advanced Ollama AI Analyst</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Interactive Traceability Drawer</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>500,000 monthly AI tokens</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Team RBAC (Accountant & Viewer)</span>
                </div>
              </div>
            </div>

            <Link
              href="/register"
              className="w-full py-2.5 px-4 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl text-center transition-colors shadow-sm"
            >
              Get Started
            </Link>
          </div>

          {/* ENTERPRISE */}
          <div className="p-8 bg-white border border-stone-200 rounded-2xl shadow-sm space-y-6 flex flex-col justify-between">
            <div className="space-y-4">
              <div>
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-stone-700">
                  Enterprise
                </span>
                <div className="text-3xl font-bold font-mono text-stone-900 mt-2">Custom</div>
                <div className="text-xs text-stone-700">tailored to transaction volume</div>
              </div>

              <div className="space-y-2.5 text-xs text-stone-700 border-t border-stone-100 pt-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Unlimited transactions</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Custom Model Router configuration</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Dedicated tenant infrastructure</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Custom Chart of Accounts mapping</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Audit log export & SLA support</span>
                </div>
              </div>
            </div>

            <a
              href="mailto:sales@finreview.internal"
              className="w-full py-2.5 px-4 bg-stone-100 hover:bg-stone-200 text-stone-900 text-xs font-semibold rounded-xl text-center transition-colors"
            >
              Contact Sales
            </a>
          </div>
        </div>
      </section>

      {/* 10. FINAL CALL TO ACTION */}
      <section className="py-20 bg-white border-t border-stone-200 px-6 sm:px-12 text-center">
        <div className="max-w-3xl mx-auto space-y-6">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-stone-900">
            Start your financial review.
          </h2>
          <p className="text-sm sm:text-base text-stone-700 max-w-xl mx-auto">
            Experience explainable financial intelligence. Ingest your statements, inspect variances, and trace every number to the ledger.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-6 py-3 bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold rounded-xl transition-all shadow-sm"
            >
              Create Free Workspace
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* 11. FOOTER */}
      <footer className="py-10 bg-[#faf8f5] border-t border-stone-200/80 px-6 sm:px-12 text-xs text-stone-700">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 font-medium">
            <span className="font-bold text-stone-900">FinReview</span> • Explainable Financial SaaS
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <a href="#how-it-works" className="hover:text-stone-900 transition-colors">
              How it Works
            </a>
            <a href="#traceability" className="hover:text-stone-900 transition-colors">
              Traceability
            </a>
            <a href="#architecture" className="hover:text-stone-900 transition-colors">
              Architecture
            </a>
            <a href="#security" className="hover:text-stone-900 transition-colors">
              Security
            </a>
            <a href="#pricing" className="hover:text-stone-900 transition-colors">
              Pricing
            </a>
          </div>
        </div>
      </footer>

      {/* Traceability Demonstration Drawer */}
      <TraceabilityDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        metricKey={demoMetric.key}
        metricLabel={demoMetric.label}
      />
    </div>
  );
}
