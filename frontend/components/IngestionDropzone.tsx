"use client";

import React, { useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  RefreshCw,
  FileText,
  ArrowRight,
  Database,
  Filter,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface IngestionDropzoneProps {
  onIngestSuccess: () => void;
  apiUrl?: string;
}

export type IngestState =
  | "IDLE"
  | "FILE_SELECTED"
  | "UPLOADING"
  | "PARSING"
  | "VALIDATING"
  | "CATEGORIZING"
  | "COMPLETED"
  | "ERROR";

export default function IngestionDropzone({
  onIngestSuccess,
}: IngestionDropzoneProps) {
  const shouldReduceMotion = useReducedMotion();
  const [isDragging, setIsDragging] = useState(false);
  const [ingestState, setIngestState] = useState<IngestState>("IDLE");
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);
  const [ingestStats, setIngestStats] = useState<{
    inserted: number;
    skipped: number;
    total: number;
  } | null>(null);

  const handleFileUpload = async (file: File) => {
    if (!file.name.endsWith(".csv") && !file.name.endsWith(".txt")) {
      setStatusMessage({ type: "error", text: "Please upload a valid CSV or TXT file." });
      setIngestState("ERROR");
      return;
    }

    setSelectedFileName(file.name);
    setIngestState("FILE_SELECTED");

    // Begin upload
    await new Promise((r) => setTimeout(r, 200));
    setIngestState("UPLOADING");

    const formData = new FormData();
    formData.append("file", file);

    try {
      setIngestState("PARSING");
      const res = await apiFetch("/api/v1/ingest", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to ingest transaction file");
      }

      setIngestState("VALIDATING");
      await new Promise((r) => setTimeout(r, 250));

      setIngestState("CATEGORIZING");
      // Trigger automatic batch categorization for newly ingested items
      const catRes = await apiFetch("/api/v1/categorize/batch", {
        method: "POST",
      });
      if (!catRes.ok) {
        let catDetail = "";
        try {
          const catData = await catRes.json();
          catDetail = catData.detail || catData.message || "";
        } catch {
          // ignore json parse error
        }
        throw new Error(catDetail || `Batch categorization failed with status ${catRes.status}`);
      }

      setIngestState("COMPLETED");
      setIngestStats({
        inserted: data.inserted ?? 0,
        skipped: data.skipped ?? 0,
        total: (data.inserted ?? 0) + (data.skipped ?? 0),
      });

      setStatusMessage({
        type: "success",
        text: `Ingestion complete: ${data.inserted} new transactions inserted (${data.skipped} duplicates skipped).`,
      });

      onIngestSuccess();
    } catch (err: any) {
      setIngestState("ERROR");
      setStatusMessage({
        type: "error",
        text: `Ingestion failed: ${err.message || "Could not complete operation."}`,
      });
    }
  };

  const handleLoadSample = async () => {
    setSelectedFileName("NYC Restaurant Co. - Raw Transactions.csv");
    setIngestState("UPLOADING");
    setStatusMessage(null);

    try {
      setIngestState("PARSING");
      const res = await apiFetch("/api/v1/ingest/sample", {
        method: "POST",
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to load sample dataset");
      }

      setIngestState("VALIDATING");
      await new Promise((r) => setTimeout(r, 200));

      setIngestState("CATEGORIZING");
      const catRes = await apiFetch("/api/v1/categorize/batch", {
        method: "POST",
      });
      if (!catRes.ok) {
        let catDetail = "";
        try {
          const catData = await catRes.json();
          catDetail = catData.detail || catData.message || "";
        } catch {
          // ignore json parse error
        }
        throw new Error(catDetail || `Batch categorization failed with status ${catRes.status}`);
      }

      setIngestState("COMPLETED");
      setIngestStats({
        inserted: data.inserted ?? 0,
        skipped: data.skipped ?? 0,
        total: data.total ?? 181,
      });

      setStatusMessage({
        type: "success",
        text: `Loaded NYC Restaurant Co. dataset (${data.inserted} new transactions, ${data.total} total).`,
      });
      onIngestSuccess();
    } catch (err: any) {
      setIngestState("ERROR");
      setStatusMessage({
        type: "error",
        text: `Failed to load sample dataset: ${err.message || "API connection error"}`,
      });
    }
  };

  const handleResetData = async () => {
    if (!confirm("Are you sure you want to clear all transactions from the database?")) return;
    try {
      const res = await apiFetch("/api/v1/transactions", {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Failed to clear transactions (status ${res.status}).`);
      }
      setIngestState("IDLE");
      setIngestStats(null);
      setSelectedFileName(null);
      setStatusMessage({ type: "info", text: data.message || "Database cleared." });
      onIngestSuccess();
    } catch (err: any) {
      setStatusMessage({ type: "error", text: err.message || "Failed to clear transactions." });
    }
  };

  const isWorking =
    ingestState === "UPLOADING" ||
    ingestState === "PARSING" ||
    ingestState === "VALIDATING" ||
    ingestState === "CATEGORIZING";

  const getStepNumber = (state: IngestState): number => {
    switch (state) {
      case "FILE_SELECTED":
        return 1;
      case "UPLOADING":
        return 2;
      case "PARSING":
        return 3;
      case "VALIDATING":
        return 4;
      case "CATEGORIZING":
        return 5;
      case "COMPLETED":
        return 6;
      default:
        return 0;
    }
  };

  const currentStep = getStepNumber(ingestState);

  return (
    <div className="space-y-4">
      {/* Clay Ingestion Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!isWorking) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          if (!isWorking && e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileUpload(e.dataTransfer.files[0]);
          }
        }}
        className={`border-2 border-dashed rounded-2xl p-8 md:p-12 text-center transition-all bg-[var(--color-surface-card)] relative overflow-hidden ${
          isDragging
            ? "border-[var(--color-primary)] bg-[var(--color-surface-strong)]"
            : "border-[var(--color-hairline)] hover:border-[var(--color-muted)]"
        }`}
      >
        <div className="max-w-md mx-auto space-y-4">
          <motion.div
            animate={
              isWorking && !shouldReduceMotion
                ? { scale: [1, 1.05, 1], rotate: [0, 2, -2, 0] }
                : {}
            }
            transition={{ repeat: Infinity, duration: 2 }}
            className="w-14 h-14 mx-auto rounded-2xl bg-[var(--color-surface-soft)] border border-[var(--color-hairline)] flex items-center justify-center text-[var(--color-ink)] shadow-xs"
          >
            {isWorking ? (
              <Loader2 className="w-7 h-7 animate-spin text-[var(--color-primary)]" />
            ) : ingestState === "COMPLETED" ? (
              <CheckCircle2 className="w-7 h-7 text-emerald-600" />
            ) : (
              <UploadCloud className="w-7 h-7 text-[var(--color-primary)]" />
            )}
          </motion.div>

          <div className="space-y-1">
            <h3 className="font-semibold text-lg text-[var(--color-ink)]">
              {ingestState === "IDLE"
                ? "Drop bank transaction CSV file here"
                : ingestState === "FILE_SELECTED"
                ? `Selected: ${selectedFileName}`
                : isWorking
                ? `Processing ${selectedFileName || "Transactions"}...`
                : ingestState === "COMPLETED"
                ? "Ingestion & Categorization Complete"
                : "Upload Bank Transactions"}
            </h3>
            <p className="text-xs text-[var(--color-muted)]">
              Supports CSV formats with Date, Description, Counterparty, and Amount.
            </p>
          </div>

          {/* Operational Progress Stepper */}
          <AnimatePresence>
            {(isWorking || ingestState === "COMPLETED") && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="pt-2 pb-1 space-y-2"
              >
                {/* Progress Bar */}
                <div className="w-full bg-[var(--color-surface-soft)] rounded-full h-1.5 overflow-hidden border border-[var(--color-hairline)]">
                  <motion.div
                    className="h-full bg-[var(--color-primary)] rounded-full"
                    initial={{ width: "0%" }}
                    animate={{
                      width: `${(currentStep / 6) * 100}%`,
                    }}
                    transition={{ duration: 0.3, ease: "easeOut" }}
                  />
                </div>

                {/* Step Indicators */}
                <div className="flex items-center justify-between text-[10px] font-medium text-[var(--color-muted)]">
                  <span className={currentStep >= 2 ? "text-[var(--color-ink)] font-semibold" : ""}>
                    1. Upload
                  </span>
                  <span className={currentStep >= 3 ? "text-[var(--color-ink)] font-semibold" : ""}>
                    2. Parse
                  </span>
                  <span className={currentStep >= 4 ? "text-[var(--color-ink)] font-semibold" : ""}>
                    3. Validate
                  </span>
                  <span className={currentStep >= 5 ? "text-[var(--color-ink)] font-semibold" : ""}>
                    4. Categorize
                  </span>
                  <span className={currentStep >= 6 ? "text-emerald-700 font-semibold" : ""}>
                    5. Ready
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <motion.label
              whileHover={shouldReduceMotion || isWorking ? undefined : { scale: 1.01 }}
              whileTap={shouldReduceMotion || isWorking ? undefined : { scale: 0.98 }}
              className={`cursor-pointer px-5 py-2.5 rounded-xl bg-[var(--color-primary)] text-white text-xs font-semibold hover:bg-[var(--color-primary-active)] transition flex items-center gap-2 shadow-xs ${
                isWorking ? "opacity-50 pointer-events-none" : ""
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Browse Local File</span>
              <input
                type="file"
                accept=".csv,.txt"
                className="hidden"
                disabled={isWorking}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileUpload(e.target.files[0]);
                  }
                }}
              />
            </motion.label>

            <motion.button
              type="button"
              data-testid="load-sample-btn"
              onClick={handleLoadSample}
              disabled={isWorking}
              whileHover={shouldReduceMotion || isWorking ? undefined : { scale: 1.01 }}
              whileTap={shouldReduceMotion || isWorking ? undefined : { scale: 0.98 }}
              className={`cursor-pointer px-5 py-2.5 rounded-xl bg-[var(--color-surface-soft)] border border-[var(--color-hairline)] text-xs font-semibold text-[var(--color-ink)] hover:bg-[var(--color-surface-strong)] transition flex items-center gap-1.5 shadow-xs ${
                isWorking ? "opacity-50" : ""
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-[var(--color-brand-lavender)]" />
              <span>Load NYC Restaurant Co. (181 Txns)</span>
            </motion.button>
          </div>
        </div>
      </div>

      {/* Status Feedback Banner */}
      <AnimatePresence>
        {statusMessage && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className={`p-4 rounded-xl text-xs font-medium flex items-center justify-between border ${
              statusMessage.type === "success"
                ? "bg-[var(--color-brand-mint)]/20 border-[var(--color-brand-mint)] text-emerald-950"
                : statusMessage.type === "error"
                ? "bg-red-50 border-red-200 text-red-800"
                : "bg-[var(--color-surface-soft)] border-[var(--color-hairline)] text-[var(--color-ink)]"
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMessage.type === "success" && (
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              )}
              {statusMessage.type === "error" && (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
              )}
              <span>{statusMessage.text}</span>
            </div>
            <button
              onClick={() => {
                setStatusMessage(null);
                setIngestState("IDLE");
              }}
              className="text-[var(--color-muted)] hover:text-[var(--color-ink)] text-xs ml-4 cursor-pointer"
            >
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Dataset Reset Control */}
      <div className="flex justify-end">
        <motion.button
          onClick={handleResetData}
          disabled={isWorking}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
          className="text-xs text-[var(--color-muted)] hover:text-red-600 transition-colors flex items-center gap-1 cursor-pointer"
        >
          <RefreshCw className="w-3 h-3" />
          <span>Reset / Clear Database</span>
        </motion.button>
      </div>
    </div>
  );
}
