import { useRef, useState } from "react";
import { FileUp, Loader2, Play, Sparkles, Type, UploadCloud } from "lucide-react";

import { api } from "../lib/api";
import type { DocumentDetail, SampleScenario } from "../types/api";
import { StatusBadge } from "./StatusBadge";

interface UploadPanelProps {
  samples: SampleScenario[];
  onVerified: (doc: DocumentDetail) => void;
}

const DOC_TYPES = [
  { value: "auto", label: "Auto-detect Document Type" },
  { value: "passport", label: "Passport (Identity)" },
  { value: "drivers_license", label: "Driver's License (Identity)" },
  { value: "national_id", label: "National ID / PAN / Aadhaar" },
  { value: "bank_statement", label: "Bank Statement (Financial)" },
  { value: "tax_document", label: "Tax Document / W-2 / ITR" },
  { value: "utility_bill", label: "Utility Bill (Proof of Address)" },
  { value: "pay_stub", label: "Pay Stub (Financial)" },
  { value: "invoice", label: "Invoice (Financial)" },
];

export function UploadPanel({ samples, onVerified }: UploadPanelProps) {
  const [mode, setMode] = useState<"file" | "text">("file");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [rawText, setRawText] = useState("");
  const [textFilename, setTextFilename] = useState("pasted_document.txt");
  const [docType, setDocType] = useState("auto");
  const [applicantName, setApplicantName] = useState("");
  const [applicantDob, setApplicantDob] = useState("");
  const [applicantIdNumber, setApplicantIdNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [runningSampleId, setRunningSampleId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (mode === "file" && !selectedFile) {
      setError("Please select an image, PDF, or text file to verify.");
      return;
    }
    if (mode === "text" && rawText.trim().length < 10) {
      setError("Please paste at least 10 characters of document text.");
      return;
    }

    setBusy(true);
    try {
      let result: DocumentDetail;
      if (mode === "file" && selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        formData.append("doc_type", docType);
        if (applicantName.trim()) formData.append("applicant_name", applicantName.trim());
        if (applicantDob.trim()) formData.append("applicant_dob", applicantDob.trim());
        if (applicantIdNumber.trim()) formData.append("applicant_id_number", applicantIdNumber.trim());
        result = await api.verifyFile(formData);
      } else {
        result = await api.verifyText({
          filename: textFilename.trim() || "pasted_document.txt",
          raw_text: rawText.trim(),
          doc_type: docType,
          applicant_name: applicantName.trim() || undefined,
          applicant_dob: applicantDob.trim() || undefined,
          applicant_id_number: applicantIdNumber.trim() || undefined,
        });
      }
      setSelectedFile(null);
      setRawText("");
      onVerified(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification pipeline failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRunSample(sampleId: string) {
    setError(null);
    setRunningSampleId(sampleId);
    try {
      const result = await api.runSample(sampleId);
      onVerified(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run sample scenario.");
    } finally {
      setRunningSampleId(null);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      {/* Main Upload / Text Form */}
      <form
        onSubmit={handleSubmit}
        className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:col-span-7"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-white">Submit Document to Pipeline</h2>
            <p className="mt-0.5 text-xs text-slate-400">
              Runs Tesseract OCR &rarr; Groq Llama extraction &rarr; Python validation &rarr; Decision routing.
            </p>
          </div>
          <div className="inline-flex rounded-xl border border-slate-800 bg-slate-950 p-1 text-xs">
            <button
              type="button"
              onClick={() => setMode("file")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition ${
                mode === "file" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <FileUp className="h-3.5 w-3.5" />
              File Upload
            </button>
            <button
              type="button"
              onClick={() => setMode("text")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition ${
                mode === "text" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <Type className="h-3.5 w-3.5" />
              Paste OCR Text
            </button>
          </div>
        </div>

        {mode === "file" ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const dropped = e.dataTransfer.files?.[0];
              if (dropped) setSelectedFile(dropped);
            }}
            className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-700 bg-slate-950/60 px-6 py-10 text-center transition hover:border-indigo-500/70 hover:bg-slate-950"
          >
            <UploadCloud className="h-10 w-10 text-indigo-400" />
            <p className="mt-3 text-sm font-medium text-slate-200">
              {selectedFile ? selectedFile.name : "Drop a document here or click to browse"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Supports PNG, JPG, WEBP, TIFF, PDF, or TXT (max 10 MB)
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.tiff,.tif,.bmp,.pdf,.txt"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-slate-400">Document Label</label>
              <input
                type="text"
                value={textFilename}
                onChange={(e) => setTextFilename(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400">Raw Document Text</label>
              <textarea
                rows={7}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder={"PASSPORT\nFull Name: Priya Patel\nPassport No: M7829104\nDate of Birth: 1995-08-21\nDate of Expiry: 2031-08-20\nCountry: India"}
                className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-100 placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Document type & optional applicant cross-check */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-slate-400">Document Type Hint</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
            >
              {DOC_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400">
              Applicant Name <span className="text-slate-600">(optional cross-check)</span>
            </label>
            <input
              type="text"
              value={applicantName}
              onChange={(e) => setApplicantName(e.target.value)}
              placeholder="e.g. Aarav Mehta"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400">
              Applicant DOB <span className="text-slate-600">(YYYY-MM-DD)</span>
            </label>
            <input
              type="text"
              value={applicantDob}
              onChange={(e) => setApplicantDob(e.target.value)}
              placeholder="1994-06-18"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400">
              Expected ID / Tax Number <span className="text-slate-600">(optional)</span>
            </label>
            <input
              type="text"
              value={applicantIdNumber}
              onChange={(e) => setApplicantIdNumber(e.target.value)}
              placeholder="Z8492014"
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Running Verification Pipeline...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Run AI Verification Pipeline
            </>
          )}
        </button>
      </form>

      {/* One-Click Demo Scenarios */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 lg:col-span-5">
        <h3 className="text-base font-semibold text-white">Interactive Test Scenarios</h3>
        <p className="mt-1 text-xs text-slate-400">
          Trigger realistic financial and identity documents to test PASS, MANUAL REVIEW, and FAIL
          routing paths immediately.
        </p>

        <div className="mt-4 space-y-3">
          {samples.map((sample) => {
            const isRunning = runningSampleId === sample.id;
            return (
              <div
                key={sample.id}
                className="rounded-xl border border-slate-800 bg-slate-950/70 p-4 transition hover:border-slate-700"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-slate-100">{sample.title}</div>
                    <div className="mt-0.5 text-[11px] uppercase tracking-wider text-slate-500">
                      {sample.category} &middot; {sample.doc_type.replace("_", " ")}
                    </div>
                  </div>
                  <StatusBadge status={sample.expected_outcome} />
                </div>
                <p className="mt-2 text-xs text-slate-400">{sample.description}</p>
                <button
                  type="button"
                  disabled={runningSampleId !== null}
                  onClick={() => handleRunSample(sample.id)}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/15 px-3 py-1.5 text-xs font-medium text-indigo-300 hover:bg-indigo-500/25 disabled:opacity-50"
                >
                  {isRunning ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3.5 w-3.5" />
                  )}
                  {isRunning ? "Running..." : "Run Scenario"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
