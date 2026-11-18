import { useState } from "react";
import {
  AlertOctagon,
  ArrowLeft,
  CheckCircle2,
  Cpu,
  FileSearch,
  FileText,
  History,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCheck,
} from "lucide-react";

import { api } from "../lib/api";
import type { DocumentDetail } from "../types/api";
import { SeverityBadge, StatusBadge } from "./StatusBadge";

interface DocumentInspectorProps {
  document: DocumentDetail;
  onBack: () => void;
  onUpdated: (doc: DocumentDetail) => void;
  onDeleted: (id: string) => void;
}

const FIELD_LABELS: Array<[string, string]> = [
  ["document_category", "Category"],
  ["document_type", "Document Type"],
  ["full_name", "Full Name"],
  ["document_number", "Document Number"],
  ["date_of_birth", "Date of Birth"],
  ["issue_date", "Issue Date"],
  ["expiry_date", "Expiry Date"],
  ["issuing_authority", "Issuing Authority"],
  ["country", "Country"],
  ["address", "Address"],
  ["institution_name", "Institution / Employer"],
  ["account_number", "Account Number"],
  ["statement_period", "Statement Period"],
  ["currency", "Currency"],
  ["total_amount", "Total / Balance"],
  ["tax_id", "Tax ID"],
];

export function DocumentInspector({
  document: doc,
  onBack,
  onUpdated,
  onDeleted,
}: DocumentInspectorProps) {
  const [reviewerName, setReviewerName] = useState("Shriyansh Gupta");
  const [reviewNotes, setReviewNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRawOcr, setShowRawOcr] = useState(false);

  const outcome = doc.outcome;
  const fields = doc.extracted_fields;

  async function handleReview(decision: "PASS" | "FAIL") {
    if (reviewNotes.trim().length < 3) {
      setError("Please add brief analyst notes explaining your review decision.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api.submitReview(doc.id, {
        decision,
        reviewer_name: reviewerName.trim() || "Compliance Analyst",
        notes: reviewNotes.trim(),
      });
      setReviewNotes("");
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete verification record '${doc.filename}'?`)) return;
    await api.deleteDocument(doc.id);
    onDeleted(doc.id);
  }

  const riskColor =
    (outcome?.risk_score ?? 0) >= 60
      ? "text-rose-400"
      : (outcome?.risk_score ?? 0) >= 20
        ? "text-amber-400"
        : "text-emerald-400";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
        <div className="flex items-start gap-4">
          <button
            onClick={onBack}
            className="mt-0.5 rounded-lg border border-slate-700 bg-slate-800/80 p-2 text-slate-300 hover:bg-slate-800 hover:text-white"
            title="Back to list"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold text-white">{doc.filename}</h2>
              <StatusBadge status={doc.status} size="md" />
            </div>
            <p className="mt-1 font-mono text-xs text-slate-400">
              ID: {doc.id} &middot; SHA-256: {doc.file_hash.slice(0, 14)}&hellip; &middot;{" "}
              {doc.processing_time_ms ?? 0} ms
            </p>
          </div>
        </div>
        <button
          onClick={handleDelete}
          className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/20"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete Record
        </button>
      </div>

      {/* Pipeline stage strip */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <StageCard
          icon={<FileSearch className="h-4 w-4 text-sky-400" />}
          title="1. OCR Engine"
          value={doc.ocr_engine || "n/a"}
          sub={
            doc.ocr_confidence != null
              ? `${Math.round(doc.ocr_confidence * 100)}% OCR confidence`
              : "Completed"
          }
        />
        <StageCard
          icon={<Cpu className="h-4 w-4 text-indigo-400" />}
          title="2. Structured Extraction"
          value={doc.extraction_engine || "n/a"}
          sub={
            fields ? `${Math.round(fields.confidence_score * 100)}% extraction confidence` : "Pending"
          }
        />
        <StageCard
          icon={<ShieldAlert className="h-4 w-4 text-amber-400" />}
          title="3. Validation Flags"
          value={`${outcome?.validation_flags.length ?? 0} flag(s)`}
          sub={`${
            outcome?.validation_flags.filter((f) => f.severity === "CRITICAL").length ?? 0
          } critical / ${
            outcome?.validation_flags.filter((f) => f.severity === "WARNING").length ?? 0
          } warning`}
        />
        <StageCard
          icon={<ShieldCheck className="h-4 w-4 text-emerald-400" />}
          title="4. Risk Score"
          value={`${outcome?.risk_score ?? 0} / 100`}
          valueClass={riskColor}
          sub={`Initial: ${outcome?.initial_decision ?? "N/A"}`}
        />
      </div>

      {/* Outcome Banner */}
      {outcome && (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-white">Decision Summary</h3>
            {outcome.reviewed_by && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-500/15 px-3 py-1 text-xs text-indigo-300 ring-1 ring-indigo-500/30">
                <UserCheck className="h-3.5 w-3.5" />
                Reviewed by {outcome.reviewed_by}
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-slate-300">{outcome.summary_reason}</p>
          {outcome.review_notes && (
            <div className="mt-3 rounded-xl border border-indigo-500/20 bg-indigo-950/30 px-4 py-3 text-xs text-indigo-200">
              <span className="font-semibold">Analyst Notes:</span> {outcome.review_notes}
            </div>
          )}
        </div>
      )}

      {/* Main 2-column inspector */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Extracted Fields & OCR text */}
        <div className="space-y-6 lg:col-span-7">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white">
                <FileText className="h-4 w-4 text-indigo-400" />
                Extracted Structured Fields
              </h3>
              <button
                onClick={() => setShowRawOcr((v) => !v)}
                className="text-xs font-medium text-sky-400 hover:text-sky-300"
              >
                {showRawOcr ? "Hide Raw OCR Text" : "Show Raw OCR Text"}
              </button>
            </div>

            {fields ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {FIELD_LABELS.map(([key, label]) => {
                  const val = (fields as unknown as Record<string, unknown>)[key];
                  if (val === null || val === undefined || val === "") return null;
                  const formatted =
                    key === "total_amount" && typeof val === "number"
                      ? val.toLocaleString(undefined, { minimumFractionDigits: 2 })
                      : String(val);
                  return (
                    <div
                      key={key}
                      className="rounded-xl border border-slate-800/80 bg-slate-950/60 px-3.5 py-2.5"
                    >
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        {label}
                      </div>
                      <div className="mt-0.5 break-words text-sm font-medium text-slate-100">
                        {formatted}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-slate-400">No structured fields extracted.</p>
            )}

            {(doc.applicant_name || doc.applicant_dob || doc.applicant_id_number) && (
              <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/50 p-3.5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Applicant Cross-Check Reference
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-300">
                  {doc.applicant_name && (
                    <span>
                      Name: <strong className="text-white">{doc.applicant_name}</strong>
                    </span>
                  )}
                  {doc.applicant_dob && (
                    <span>
                      DOB: <strong className="text-white">{doc.applicant_dob}</strong>
                    </span>
                  )}
                  {doc.applicant_id_number && (
                    <span>
                      ID: <strong className="text-white">{doc.applicant_id_number}</strong>
                    </span>
                  )}
                </div>
              </div>
            )}

            {showRawOcr && (
              <div className="mt-4">
                <div className="mb-1.5 text-xs font-medium text-slate-400">Raw OCR Output</div>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-xs text-slate-300">
                  {doc.raw_ocr_text || "(empty)"}
                </pre>
              </div>
            )}
          </div>

          {/* Audit Trail */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
              <History className="h-4 w-4 text-sky-400" />
              Immutable Audit Log ({doc.audit_logs.length})
            </h3>
            <ol className="relative space-y-4 border-l border-slate-800 pl-5">
              {doc.audit_logs.map((entry) => (
                <li key={entry.id} className="relative">
                  <span className="absolute -left-[25px] top-1.5 h-2.5 w-2.5 rounded-full bg-indigo-500 ring-4 ring-slate-900" />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold text-indigo-300">
                      {entry.event_type}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {new Date(entry.created_at).toLocaleString()} &middot; {entry.actor}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-300">{entry.message}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Right: Validation Flags & Manual Review Action */}
        <div className="space-y-6 lg:col-span-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
              <AlertOctagon className="h-4 w-4 text-amber-400" />
              Validation Checks &amp; Flags
            </h3>
            {outcome && outcome.validation_flags.length > 0 ? (
              <div className="space-y-3">
                {outcome.validation_flags.map((flag, idx) => (
                  <div
                    key={`${flag.rule_code}-${idx}`}
                    className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-slate-200">
                        {flag.rule_code}
                      </span>
                      <SeverityBadge severity={flag.severity} />
                    </div>
                    <p className="mt-1.5 text-xs text-slate-300">{flag.message}</p>
                    {flag.field && (
                      <div className="mt-1.5 text-[11px] text-slate-500">
                        Field: <span className="font-mono text-slate-400">{flag.field}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-300">
                <CheckCircle2 className="h-5 w-5 shrink-0" />
                <span>All automated validation rules passed with zero discrepancies.</span>
              </div>
            )}
          </div>

          {/* Analyst Override / Manual Review Box */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
            <h3 className="text-sm font-semibold text-white">Analyst Review Action</h3>
            <p className="mt-1 text-xs text-slate-400">
              Approve or reject this document. Every manual review is permanently recorded in the SQL
              audit log.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-400">Reviewer Name</label>
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400">Review Notes</label>
                <textarea
                  rows={3}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Document rationale for approving or rejecting..."
                  className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>
              {error && <p className="text-xs text-rose-400">{error}</p>}
              <div className="grid grid-cols-2 gap-3 pt-1">
                <button
                  disabled={submitting}
                  onClick={() => handleReview("PASS")}
                  className="rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  Approve (PASS)
                </button>
                <button
                  disabled={submitting}
                  onClick={() => handleReview("FAIL")}
                  className="rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
                >
                  Reject (FAIL)
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StageCard({
  icon,
  title,
  value,
  sub,
  valueClass = "text-white",
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
        {icon}
        {title}
      </div>
      <div className={`mt-2 truncate text-sm font-semibold ${valueClass}`}>{value}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}
