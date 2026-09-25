"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2,
  UploadCloud,
  Layers,
  UserPlus,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  FileSpreadsheet,
  ShieldCheck,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

type Step = 1 | 2 | 3 | 4 | 5 | 6;

const STEPS = [
  { step: 1, label: "Account", icon: CheckCircle2 },
  { step: 2, label: "Company", icon: Building2 },
  { step: 3, label: "Connect Data", icon: UploadCloud },
  { step: 4, label: "Chart of Accounts", icon: Layers },
  { step: 5, label: "Invite Team", icon: UserPlus },
  { step: 6, label: "Launch", icon: Sparkles },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [currentStep, setCurrentStep] = useState<Step>(2); // Step 1 is already complete if user is logged in
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Step 2: Company Data
  const [companyName, setCompanyName] = useState("NYC Restaurant Co.");
  const [industry, setIndustry] = useState("Hospitality & Restaurants");

  // Step 3: Data Option
  const [dataOption, setDataOption] = useState<"sample" | "csv">("sample");
  const [csvFile, setCsvFile] = useState<File | null>(null);

  // Step 4: Custom Mapping
  const [customPattern, setCustomPattern] = useState("");
  const [targetCategory, setTargetCategory] = useState("Food Inventory / Supplies");
  const [targetBucket, setTargetBucket] = useState("COGS");

  // Step 5: Invite Member
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("ACCOUNTANT");
  const [invitedMembers, setInvitedMembers] = useState<Array<{ name: string; email: string; role: string }>>([]);

  // Check auth
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/onboarding");
    }
  }, [isLoading, isAuthenticated, router]);

  // Load active tenant name if already exists
  useEffect(() => {
    if (isAuthenticated) {
      apiFetch("/api/v1/tenants/current")
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.name && !companyName) {
            setCompanyName(data.name);
          }
        })
        .catch(() => {});
    }
  }, [isAuthenticated]);

  const handleNext = async () => {
    setError(null);
    setMessage(null);

    // Step 2 submit: Company Workspace
    if (currentStep === 2) {
      if (!companyName.trim()) {
        setError("Please provide your company or workspace name.");
        return;
      }
      setLoading(true);
      try {
        const res = await apiFetch("/api/v1/tenants", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: companyName.trim() }),
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Failed to configure company workspace.");
        }
        setCurrentStep(3);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
      return;
    }

    // Step 3 submit: Data Ingestion
    if (currentStep === 3) {
      setLoading(true);
      try {
        if (dataOption === "sample") {
          const res = await apiFetch("/api/v1/ingest/sample", { method: "POST" });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to load sample dataset.");
          }
          setMessage("Successfully connected NYC Restaurant Co. demonstration dataset (181 transactions).");
        } else if (csvFile) {
          const formData = new FormData();
          formData.append("file", csvFile);
          const res = await apiFetch("/api/v1/imports", {
            method: "POST",
            body: formData,
          });
          if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to upload CSV file.");
          }
          setMessage(`CSV file '${csvFile.name}' uploaded and queued for processing.`);
        }
        setCurrentStep(4);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
      return;
    }

    // Step 4 submit: Chart of Accounts
    if (currentStep === 4) {
      if (customPattern.trim()) {
        setLoading(true);
        try {
          await apiFetch("/api/v1/settings/chart-of-accounts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              raw_pattern: customPattern.trim(),
              target_category: targetCategory,
              target_bucket: targetBucket,
            }),
          });
        } catch {}
        setLoading(false);
      }
      setCurrentStep(5);
      return;
    }

    // Step 5 submit: Team Invitations
    if (currentStep === 5) {
      setCurrentStep(6);
      return;
    }

    // Step 6 submit: Complete
    if (currentStep === 6) {
      router.push("/app");
    }
  };

  const handleAddInvite = async () => {
    if (!inviteEmail.trim() || !inviteName.trim()) {
      setError("Please specify both name and email for invitation.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/api/v1/users/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: inviteName.trim(),
          email: inviteEmail.trim(),
          role: inviteRole,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to send invitation.");
      }
      setInvitedMembers([...invitedMembers, { name: inviteName, email: inviteEmail, role: inviteRole }]);
      setInviteName("");
      setInviteEmail("");
      setMessage(`Invitation sent to ${inviteEmail}.`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] flex flex-col justify-between">
      {/* Top Navbar */}
      <header className="px-8 py-5 border-b border-stone-200/80 bg-white/70 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-stone-900 flex items-center justify-center text-white font-bold text-base shadow-sm">
            F
          </div>
          <span className="font-bold text-lg tracking-tight text-stone-900">FinReview</span>
          <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded bg-stone-100 text-stone-600 border border-stone-200">
            Workspace Setup
          </span>
        </div>
        <div className="text-xs text-stone-500">
          Signed in as <span className="font-semibold text-stone-800">{user?.email}</span>
        </div>
      </header>

      {/* Main Wizard Form */}
      <main className="max-w-2xl w-full mx-auto px-6 py-12 flex-1">
        {/* Progress Bar */}
        <div className="mb-10">
          <div className="flex items-center justify-between mb-3">
            {STEPS.map((s) => (
              <div
                key={s.step}
                className={`flex items-center gap-1.5 text-xs font-medium ${
                  currentStep >= s.step ? "text-stone-900" : "text-stone-400"
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
                    currentStep === s.step
                      ? "bg-stone-900 text-white"
                      : currentStep > s.step
                      ? "bg-emerald-100 text-emerald-800"
                      : "bg-stone-100 text-stone-400"
                  }`}
                >
                  {currentStep > s.step ? "✓" : s.step}
                </div>
                <span className="hidden sm:inline">{s.label}</span>
              </div>
            ))}
          </div>
          <div className="w-full bg-stone-200 h-1.5 rounded-full overflow-hidden">
            <motion.div
              className="bg-stone-900 h-full"
              initial={{ width: "20%" }}
              animate={{ width: `${(currentStep / 6) * 100}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>

        {/* Wizard Step Card */}
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.25 }}
          className="bg-white border border-stone-200/90 rounded-2xl p-8 shadow-sm space-y-6"
        >
          {error && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
              {error}
            </div>
          )}

          {message && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              {message}
            </div>
          )}

          {/* STEP 2: COMPANY WORKSPACE */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-stone-900 tracking-tight">Configure Your Company</h2>
                <p className="text-sm text-stone-600 mt-1">
                  Establish tenant isolation and financial boundaries for your business.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-700 mb-1.5">
                    Company / Tenant Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. NYC Restaurant Co. or Bistro Group LLC"
                    className="w-full px-4 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-stone-900 text-sm focus:outline-none focus:ring-2 focus:ring-stone-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-stone-700 mb-1.5">
                    Industry Domain
                  </label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full px-4 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-stone-900 text-sm focus:outline-none focus:ring-2 focus:ring-stone-400"
                  >
                    <option value="Hospitality & Restaurants">Hospitality & Restaurants</option>
                    <option value="B2B SaaS & Technology">B2B SaaS & Technology</option>
                    <option value="Retail & E-Commerce">Retail & E-Commerce</option>
                    <option value="Professional Services">Professional Services</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: CONNECT DATA */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-stone-900 tracking-tight">Connect Financial Data</h2>
                <p className="text-sm text-stone-600 mt-1">
                  Ingest bank transactions to begin deterministic P&L and AI classification.
                </p>
              </div>

              <div className="space-y-3">
                <div
                  onClick={() => setDataOption("sample")}
                  className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
                    dataOption === "sample"
                      ? "border-stone-900 bg-stone-50/80 shadow-sm"
                      : "border-stone-200 hover:border-stone-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center font-bold">
                        <FileSpreadsheet className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="font-semibold text-stone-900 text-sm">
                          Load Bundled Restaurant Dataset (Recommended)
                        </div>
                        <div className="text-xs text-stone-500 mt-0.5">
                          181 bank transactions (Jan–Mar 2026), pre-verified for restaurant P&L analysis.
                        </div>
                      </div>
                    </div>
                    <input
                      type="radio"
                      checked={dataOption === "sample"}
                      onChange={() => setDataOption("sample")}
                      className="accent-stone-900"
                    />
                  </div>
                </div>

                <div
                  onClick={() => setDataOption("csv")}
                  className={`p-4 rounded-xl border-2 cursor-pointer transition-all ${
                    dataOption === "csv"
                      ? "border-stone-900 bg-stone-50/80 shadow-sm"
                      : "border-stone-200 hover:border-stone-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-stone-100 text-stone-700 flex items-center justify-center font-bold">
                        <UploadCloud className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="font-semibold text-stone-900 text-sm">Upload Custom CSV Bank Export</div>
                        <div className="text-xs text-stone-500 mt-0.5">
                          Upload statement CSV from Chase, Mercury, Toast, or Stripe.
                        </div>
                      </div>
                    </div>
                    <input
                      type="radio"
                      checked={dataOption === "csv"}
                      onChange={() => setDataOption("csv")}
                      className="accent-stone-900"
                    />
                  </div>

                  {dataOption === "csv" && (
                    <div className="mt-4 pt-4 border-t border-stone-200/80">
                      <input
                        type="file"
                        accept=".csv,.txt"
                        onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                        className="text-xs text-stone-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-stone-900 file:text-white hover:file:bg-stone-800"
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STEP 4: CHART OF ACCOUNTS */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-stone-900 tracking-tight">Chart of Accounts Mapping</h2>
                <p className="text-sm text-stone-600 mt-1">
                  FinReview standardizes accounting buckets. Add any company-specific category patterns.
                </p>
              </div>

              <div className="bg-stone-50 rounded-xl p-4 border border-stone-200/80 text-xs text-stone-600 space-y-1.5">
                <div className="font-semibold text-stone-800">Standard P&L Buckets Active:</div>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {["Revenue", "COGS", "Payroll", "Operating Expenses", "Non-P&L / Balance Sheet"].map((b) => (
                    <span key={b} className="px-2 py-0.5 rounded bg-white border border-stone-200 text-stone-700 text-[11px]">
                      {b}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3 pt-2">
                <div className="text-xs font-semibold uppercase tracking-wider text-stone-700">
                  Optional Tenant Override Rule
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <input
                    type="text"
                    placeholder="Pattern (e.g. Sysco)"
                    value={customPattern}
                    onChange={(e) => setCustomPattern(e.target.value)}
                    className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900"
                  />
                  <select
                    value={targetCategory}
                    onChange={(e) => setTargetCategory(e.target.value)}
                    className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900"
                  >
                    <option value="Food Inventory / Supplies">Food Inventory / Supplies</option>
                    <option value="Beverage Inventory / Alcohol">Beverage Inventory / Alcohol</option>
                    <option value="Salaries & Wages">Salaries & Wages</option>
                    <option value="Repairs & Maintenance">Repairs & Maintenance</option>
                    <option value="Capital Expenditure - Equipment Asset">CapEx Equipment (Non-P&L)</option>
                  </select>
                  <select
                    value={targetBucket}
                    onChange={(e) => setTargetBucket(e.target.value)}
                    className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900"
                  >
                    <option value="COGS">COGS</option>
                    <option value="Revenue">Revenue</option>
                    <option value="Payroll">Payroll</option>
                    <option value="Operating Expenses">Operating Expenses</option>
                    <option value="Non-P&L">Non-P&L</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: INVITE TEAM */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-stone-900 tracking-tight">Invite Finance Team</h2>
                <p className="text-sm text-stone-600 mt-1">
                  Add team members with role-based access control (Admin, Accountant, Viewer).
                </p>
              </div>

              <div className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <input
                    type="text"
                    placeholder="Full Name"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900"
                  />
                  <input
                    type="email"
                    placeholder="Colleague Email"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900"
                  />
                  <div className="flex gap-2">
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="px-3 py-2 bg-stone-50 border border-stone-200 rounded-lg text-xs text-stone-900 flex-1"
                    >
                      <option value="ACCOUNTANT">Accountant</option>
                      <option value="VIEWER">Viewer</option>
                      <option value="ADMIN">Admin</option>
                    </select>
                    <button
                      type="button"
                      onClick={handleAddInvite}
                      disabled={loading}
                      className="px-3 py-2 bg-stone-900 text-white rounded-lg text-xs font-semibold hover:bg-stone-800 disabled:opacity-50"
                    >
                      Invite
                    </button>
                  </div>
                </div>

                {invitedMembers.length > 0 && (
                  <div className="mt-4 space-y-1.5 border-t border-stone-100 pt-3">
                    <div className="text-xs font-semibold text-stone-700">Invited Members:</div>
                    {invitedMembers.map((m, i) => (
                      <div key={i} className="flex items-center justify-between p-2 bg-stone-50 rounded-lg text-xs">
                        <span className="font-medium text-stone-800">{m.name} ({m.email})</span>
                        <span className="px-2 py-0.5 rounded bg-white border border-stone-200 text-stone-600 font-mono text-[10px]">
                          {m.role}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* STEP 6: LAUNCH WORKSPACE */}
          {currentStep === 6 && (
            <div className="space-y-6 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-800 mx-auto flex items-center justify-center">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>

              <div>
                <h2 className="text-2xl font-bold text-stone-900 tracking-tight">Workspace Ready</h2>
                <p className="text-sm text-stone-600 mt-2 max-w-md mx-auto">
                  Your multi-tenant workspace is configured with deterministic financial computing, review queue triage, and Ollama AI assistant tools.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3 text-left max-w-md mx-auto pt-2">
                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80">
                  <div className="text-[11px] text-stone-500 font-semibold uppercase">Security</div>
                  <div className="text-xs font-semibold text-stone-800 mt-0.5">PostgreSQL RLS</div>
                </div>
                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80">
                  <div className="text-[11px] text-stone-500 font-semibold uppercase">Engine</div>
                  <div className="text-xs font-semibold text-stone-800 mt-0.5">Decimal Math</div>
                </div>
                <div className="p-3 bg-stone-50 rounded-xl border border-stone-200/80">
                  <div className="text-[11px] text-stone-500 font-semibold uppercase">AI Assistant</div>
                  <div className="text-xs font-semibold text-stone-800 mt-0.5">Ollama Grounded</div>
                </div>
              </div>
            </div>
          )}

          {/* Wizard Action Buttons */}
          <div className="pt-6 border-t border-stone-100 flex items-center justify-between">
            {currentStep > 2 && currentStep < 6 ? (
              <button
                type="button"
                onClick={() => setCurrentStep((currentStep - 1) as Step)}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-stone-200 text-stone-700 rounded-xl text-xs font-semibold hover:bg-stone-50 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back
              </button>
            ) : (
              <div />
            )}

            <button
              type="button"
              onClick={handleNext}
              disabled={loading}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-stone-900 text-white rounded-xl text-xs font-semibold hover:bg-stone-800 transition-colors shadow-sm disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Processing...
                </>
              ) : currentStep === 6 ? (
                <>
                  Enter Workspace
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-stone-400 border-t border-stone-200/60 bg-white/40">
        FinReview B2B Financial Intelligence • Multi-Tenant Tenant Isolation Active
      </footer>
    </div>
  );
}
