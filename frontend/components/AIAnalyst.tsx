"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  Sparkles,
  Send,
  Loader2,
  Database,
  ExternalLink,
  Tag,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface CitationItem {
  id: string | number;
  label: string;
  type: string;
  amount?: number;
  date?: string;
  category?: string;
}

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  citations?: CitationItem[];
  toolsUsed?: string[];
  timestamp: string;
}

const DEFAULT_SUGGESTIONS: string[] = [
  "What was our revenue in Jan 2026?",
  "How much did we spend on payroll each month?",
  "Why did operating profit change between Jan and Feb?",
  "Which transactions need my attention?",
  "Show me the transactions behind that variance.",
];

interface AIAnalystProps {
  apiUrl?: string;
}

export default function AIAnalyst({}: AIAnalystProps) {
  const shouldReduceMotion = useReducedMotion();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome-1",
      sender: "assistant",
      text: "👋 Hello! I am your **FinReview AI Financial Analyst**. I have direct access to your verified transaction database, deterministic monthly P&L figures, and month-over-month variance calculations.\n\nAsk me about any financial metrics, unusual cost spikes, or flagged attention items.",
      citations: [],
      toolsUsed: [],
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: shouldReduceMotion ? "auto" : "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    async function loadSuggestions() {
      try {
        const res = await apiFetch("/api/v1/chat/suggestions");
        if (res.ok) {
          const data = await res.json();
          setSuggestions(
            data.suggestions && data.suggestions.length > 0
              ? data.suggestions
              : DEFAULT_SUGGESTIONS
          );
        } else {
          setSuggestions(DEFAULT_SUGGESTIONS);
        }
      } catch {
        setSuggestions(DEFAULT_SUGGESTIONS);
      }
    }
    loadSuggestions();
  }, []);

  const handleSendMessage = async (msgText: string) => {
    const textToSend = msgText.trim();
    if (!textToSend || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await apiFetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: textToSend }),
      });

      if (!res.ok) {
        throw new Error("Failed to receive analyst response.");
      }

      const data = await res.json();
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: data.reply,
        citations: data.citations || [],
        toolsUsed: data.tools_used || [],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          sender: "assistant",
          text: `⚠️ **Unable to process query:** ${err.message || "Please check that your backend server is running."}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val: number | undefined) => {
    if (val === undefined || isNaN(val)) return "$0.00";
    const formatted = Math.abs(val).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return val < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  return (
    <div className="space-y-6">
      {/* Header Integrity Card */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-[var(--color-surface-soft)] border border-[var(--color-hairline)]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[var(--color-brand-lavender)]/40 flex items-center justify-center text-[var(--color-ink)] shrink-0 font-bold">
            <Sparkles className="w-4 h-4 text-indigo-700" />
          </div>
          <div>
            <div className="text-xs font-bold text-[var(--color-ink)] flex items-center gap-2">
              <span>Source-Grounded Financial Analyst</span>
              <span className="text-[10px] px-2 py-0.2 rounded-full bg-[var(--color-brand-mint)]/40 text-emerald-950 font-mono font-semibold">
                Zero Hallucinations
              </span>
            </div>
            <p className="text-[11px] text-[var(--color-muted)]">
              Tool-calling engine queries database directly before responding. Click citations to trace records.
            </p>
          </div>
        </div>

        <motion.button
          type="button"
          onClick={() => setMessages([])}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
          className="text-xs font-semibold px-2.5 py-1 rounded-lg border border-[var(--color-hairline)] bg-[#ffffff] text-[var(--color-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-canvas)] transition-all cursor-pointer"
        >
          Clear Chat
        </motion.button>
      </div>

      {/* Suggested Prompts Stream */}
      {suggestions.length > 0 && (
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-[var(--color-muted)] uppercase tracking-wider">
            Suggested Financial Review Queries:
          </span>
          <div className="flex flex-wrap items-center gap-2">
            {suggestions.map((s, idx) => (
              <motion.button
                key={idx}
                type="button"
                onClick={() => handleSendMessage(s)}
                disabled={loading}
                whileHover={shouldReduceMotion || loading ? undefined : { scale: 1.02 }}
                whileTap={shouldReduceMotion || loading ? undefined : { scale: 0.98 }}
                className="text-xs px-3 py-1.5 rounded-full bg-[#ffffff] border border-[var(--color-hairline)] text-[var(--color-body)] hover:border-[var(--color-primary)] hover:text-[var(--color-ink)] transition-all shadow-xs cursor-pointer text-left"
              >
                &ldquo;{s}&rdquo;
              </motion.button>
            ))}
          </div>
        </div>
      )}

      {/* Main Conversation Stream */}
      <div className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] shadow-xs flex flex-col h-[520px] overflow-hidden">
        {/* Messages Scroll Area */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: shouldReduceMotion ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
                className={`flex gap-3 max-w-3xl ${
                  msg.sender === "user" ? "ml-auto justify-end" : "mr-auto justify-start"
                }`}
              >
                {msg.sender === "assistant" && (
                  <div className="w-8 h-8 rounded-xl bg-[var(--color-primary)] text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs mt-1">
                    AI
                  </div>
                )}

                <div
                  className={`space-y-2 rounded-2xl p-4 text-xs leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-[var(--color-primary)] text-white rounded-tr-xs shadow-xs"
                      : "bg-[var(--color-canvas)] border border-[var(--color-hairline)] text-[var(--color-ink)] rounded-tl-xs shadow-2xs"
                  }`}
                >
                  {/* Tools executed indicator */}
                  {msg.toolsUsed && msg.toolsUsed.length > 0 && (
                    <div className="flex items-center gap-1.5 pb-1 border-b border-[var(--color-hairline)]">
                      <Database className="w-3 h-3 text-[var(--color-brand-teal)]" />
                      <span className="font-mono text-[10px] text-[var(--color-muted)] font-semibold">
                        Executed: {msg.toolsUsed.join(", ")}
                      </span>
                    </div>
                  )}

                  {/* Message Markdown Body */}
                  <div className="whitespace-pre-wrap font-sans">
                    {msg.text}
                  </div>

                  {/* Clickable Citation Chips */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="pt-2 border-t border-[var(--color-hairline)] space-y-1.5">
                      <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--color-muted)] block">
                        Cited Data Records (100% Traceability):
                      </span>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {msg.citations.map((c, i) => (
                          <motion.button
                            key={i}
                            type="button"
                            onClick={() => setSelectedCitation(c)}
                            whileHover={shouldReduceMotion ? undefined : { scale: 1.03 }}
                            whileTap={shouldReduceMotion ? undefined : { scale: 0.97 }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-mono font-semibold bg-[#ffffff] border border-[var(--color-hairline)] text-[var(--color-ink)] hover:border-[var(--color-brand-teal)] hover:bg-[var(--color-surface-soft)] transition-all cursor-pointer shadow-2xs"
                          >
                            <Tag className="w-2.5 h-2.5 text-[var(--color-brand-teal)]" />
                            <span>{c.label}</span>
                          </motion.button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div
                    className={`text-[10px] text-right font-mono ${
                      msg.sender === "user" ? "text-white/70" : "text-[var(--color-muted)]"
                    }`}
                  >
                    {msg.timestamp}
                  </div>
                </div>

                {msg.sender === "user" && (
                  <div className="w-8 h-8 rounded-xl bg-[var(--color-surface-strong)] text-[var(--color-ink)] flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs mt-1">
                    You
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {loading && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 max-w-md mr-auto"
            >
              <div className="w-8 h-8 rounded-xl bg-[var(--color-primary)] text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
                AI
              </div>
              <div className="bg-[var(--color-canvas)] border border-[var(--color-hairline)] rounded-2xl p-4 text-xs text-[var(--color-muted)] flex items-center gap-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-[var(--color-primary)]" />
                <span>Executing deterministic database queries...</span>
              </div>
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(input);
          }}
          className="p-4 bg-[var(--color-surface-soft)] border-t border-[var(--color-hairline)] flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything about revenue, payroll, profit variance, or attention items..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-[#ffffff] border border-[var(--color-hairline)] text-xs text-[var(--color-ink)] placeholder-[var(--color-muted)] focus:outline-none focus:border-[var(--color-primary)] transition-all"
          />

          <motion.button
            type="submit"
            disabled={!input.trim() || loading}
            whileHover={shouldReduceMotion || !input.trim() || loading ? undefined : { scale: 1.01 }}
            whileTap={shouldReduceMotion || !input.trim() || loading ? undefined : { scale: 0.98 }}
            className="px-4 py-2.5 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold hover:bg-[var(--color-primary-active)] disabled:opacity-40 transition-all flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </motion.button>
        </form>
      </div>

      {/* Citation Detail Modal */}
      <AnimatePresence>
        {selectedCitation && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedCitation(null)}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs"
          >
            <motion.div
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
              onClick={(e) => e.stopPropagation()}
              className="bg-[#ffffff] rounded-2xl border border-[var(--color-hairline)] max-w-sm w-full p-5 shadow-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--color-brand-mint)]/40 text-emerald-950 font-mono">
                  {selectedCitation.type.toUpperCase()} RECORD
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedCitation(null)}
                  className="text-xs text-[var(--color-muted)] hover:text-[var(--color-ink)] cursor-pointer"
                >
                  ✕ Close
                </button>
              </div>

              <div className="space-y-2 text-xs">
                <div className="text-sm font-bold text-[var(--color-ink)]">
                  {selectedCitation.label}
                </div>
                {selectedCitation.amount !== undefined && (
                  <div className="font-mono text-sm font-bold text-emerald-700">
                    {formatCurrency(selectedCitation.amount)}
                  </div>
                )}
                {selectedCitation.date && (
                  <div className="text-[var(--color-muted)] font-mono">
                    Date: {selectedCitation.date}
                  </div>
                )}
                {selectedCitation.category && (
                  <div className="text-[var(--color-body)]">
                    Category: <strong>{selectedCitation.category}</strong>
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-[var(--color-hairline)] flex justify-end">
                <motion.button
                  type="button"
                  onClick={() => setSelectedCitation(null)}
                  whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
                  whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
                  className="px-3 py-1.5 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold cursor-pointer"
                >
                  Done
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
