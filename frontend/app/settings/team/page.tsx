"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Users,
  UserPlus,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Shield,
  ShieldCheck,
  Mail,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function TeamSettingsPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [members, setMembers] = useState<Array<{
    id: number;
    name: string;
    email: string;
    role: string;
    is_active: boolean;
    created_at: string;
    last_login_at?: string;
  }>>([]);

  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("ACCOUNTANT");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/settings/team");
    }
  }, [isLoading, isAuthenticated, router]);

  const loadTeam = async () => {
    try {
      setLoading(true);
      const res = await apiFetch("/api/v1/users/team");
      if (res.ok) {
        const json = await res.json();
        setMembers(json.members || []);
      }
    } catch {
      setError("Failed to load team members.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadTeam();
    }
  }, [isAuthenticated]);

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteName.trim() || !inviteEmail.trim()) return;

    setInviting(true);
    setError(null);
    setMessage(null);

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
        throw new Error(err.detail || "Failed to invite user.");
      }

      setMessage(`Invitation sent to ${inviteEmail.trim()} as ${inviteRole}.`);
      setInviteName("");
      setInviteEmail("");
      loadTeam();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      const res = await apiFetch(`/api/v1/users/${userId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update role.");
      }
      setMessage("Role updated successfully.");
      loadTeam();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const isAdmin = user?.role === "ADMIN";

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
              <Users className="w-4 h-4 text-stone-700" />
              Team & Permissions
            </h1>
            <p className="text-xs text-stone-500">Manage tenant members and role-based access control (RBAC).</p>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-4xl w-full mx-auto p-6 md:p-8 space-y-8">
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

        {/* Invite Member Card (Admins only) */}
        {isAdmin && (
          <div className="bg-white border border-stone-200/90 rounded-2xl p-6 shadow-sm space-y-4">
            <div>
              <h2 className="text-sm font-bold text-stone-900">Invite Finance Team Member</h2>
              <p className="text-xs text-stone-500 mt-0.5">
                New members will be granted immediate access to this tenant workspace.
              </p>
            </div>

            <form onSubmit={handleInvite} className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2">
              <div>
                <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                  Full Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Sarah Jenkins"
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  placeholder="name@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase text-stone-600 mb-1">
                  RBAC Role
                </label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="w-full px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-900 focus:outline-none focus:ring-2 focus:ring-stone-400"
                >
                  <option value="ACCOUNTANT">Accountant (Classify, Review, P&L)</option>
                  <option value="VIEWER">Viewer (Read-only)</option>
                  <option value="ADMIN">Admin (Full Workspace Control)</option>
                </select>
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={inviting || !inviteName.trim() || !inviteEmail.trim()}
                  className="w-full py-2 px-4 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm disabled:opacity-50"
                >
                  {inviting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
                  Send Invite
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Team Members List */}
        <div className="bg-white border border-stone-200/90 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-stone-900">Workspace Members ({members.length})</h2>
            <div className="flex items-center gap-2 text-xs text-stone-500">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Tenant Isolation Enforced
            </div>
          </div>

          {loading ? (
            <div className="py-8 text-center text-xs text-stone-500">Loading members...</div>
          ) : (
            <div className="divide-y divide-stone-100">
              {members.map((m) => (
                <div key={m.id} className="py-3.5 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-stone-900 text-white flex items-center justify-center font-bold text-xs">
                      {m.name?.[0]?.toUpperCase() || "U"}
                    </div>
                    <div>
                      <div className="font-semibold text-stone-900 flex items-center gap-2">
                        {m.name}
                        {m.id === user?.id && (
                          <span className="text-[10px] text-stone-500 bg-stone-100 px-1.5 py-0.2 rounded">You</span>
                        )}
                      </div>
                      <div className="text-stone-500 text-[11px]">{m.email}</div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {isAdmin && m.id !== user?.id ? (
                      <select
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.id, e.target.value)}
                        className="px-2.5 py-1 bg-stone-50 border border-stone-200 rounded-lg text-xs font-mono font-medium text-stone-800"
                      >
                        <option value="ADMIN">ADMIN</option>
                        <option value="ACCOUNTANT">ACCOUNTANT</option>
                        <option value="VIEWER">VIEWER</option>
                      </select>
                    ) : (
                      <span className="px-2.5 py-1 rounded-lg bg-stone-100 text-stone-700 font-mono text-[11px] font-semibold border border-stone-200">
                        {m.role}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Roles Breakdown Card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm space-y-1.5">
            <div className="font-bold text-stone-900 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-stone-800" />
              ADMIN
            </div>
            <p className="text-stone-500 text-[11px]">
              Complete control: user management, role assignments, company settings, and all financial workflows.
            </p>
          </div>

          <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm space-y-1.5">
            <div className="font-bold text-stone-900 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-stone-600" />
              ACCOUNTANT
            </div>
            <p className="text-stone-500 text-[11px]">
              Financial operations: import CSVs, override categories, review queue triage, P&L, variances, and AI analyst.
            </p>
          </div>

          <div className="p-4 bg-white border border-stone-200 rounded-xl shadow-sm space-y-1.5">
            <div className="font-bold text-stone-900 flex items-center gap-1.5">
              <Shield className="w-4 h-4 text-stone-400" />
              VIEWER
            </div>
            <p className="text-stone-500 text-[11px]">
              Read-only view of P&L statements, transactions, variances, and permitted read-only AI investigations.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
