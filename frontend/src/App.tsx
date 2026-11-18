import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCheck2,
  History,
  LayoutDashboard,
  RefreshCw,
  Search,
  Shield,
  Upload,
  XCircle,
} from "lucide-react";

import { AuditLogView } from "./components/AuditLogView";
import { DocumentInspector } from "./components/DocumentInspector";
import { StatusBadge } from "./components/StatusBadge";
import { UploadPanel } from "./components/UploadPanel";
import { api } from "./lib/api";
import type {
  DocumentDetail,
  DocumentSummary,
  PipelineStats,
  SampleScenario,
} from "./types/api";

type TabId = "overview" | "verify" | "review" | "audit";

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [samples, setSamples] = useState<SampleScenario[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsRes, docsRes, samplesRes] = await Promise.all([
        api.getStats(),
        api.listDocuments({
          status: statusFilter,
          search: searchQuery,
        }),
        api.getSamples(),
      ]);
      setStats(statsRes);
      setDocuments(docsRes);
      setSamples(samplesRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to connect to verification API.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchQuery]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  async function openDocument(id: string) {
    try {
      const detail = await api.getDocument(id);
      setSelectedDoc(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document.");
    }
  }

  function handleVerified(doc: DocumentDetail) {
    setSelectedDoc(doc);
    void loadDashboard();
  }

  function handleUpdated(doc: DocumentDetail) {
    setSelectedDoc(doc);
    void loadDashboard();
  }

  function handleDeleted(_id: string) {
    setSelectedDoc(null);
    void loadDashboard();
  }

  const reviewQueueDocs = documents.filter((d) => d.status === "MANUAL_REVIEW");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top Navigation */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-sky-500 shadow-lg shadow-indigo-500/20">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-bold tracking-tight text-white">
                VeriFlow <span className="font-normal text-slate-400">| Document Verification Pipeline</span>
              </h1>
              <p className="text-[11px] text-slate-400">
                FastAPI &middot; Tesseract OCR &middot; Groq Llama &middot; SQL Audit Trail
              </p>
            </div>
          </div>

          {/* Runtime status pills */}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ring-1 ${
                stats?.groq_configured
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30"
                  : "bg-amber-500/10 text-amber-300 ring-amber-500/30"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  stats?.groq_configured ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              {stats?.groq_configured ? `Groq: ${stats.groq_model}` : "LLM: Fallback Mode"}
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ring-1 ${
                stats?.tesseract_available
                  ? "bg-sky-500/10 text-sky-300 ring-sky-500/30"
                  : "bg-slate-800 text-slate-300 ring-slate-700"
              }`}
            >
              <Database className="h-3 w-3" />
              {stats?.tesseract_available ? "Tesseract OCR Ready" : "PDF/Text + Sample OCR"}
            </span>
          </div>
        </div>

        {/* Tab Bar */}
        <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto px-4 sm:px-6">
          <NavTab
            active={!selectedDoc && activeTab === "overview"}
            onClick={() => {
              setSelectedDoc(null);
              setActiveTab("overview");
            }}
            icon={<LayoutDashboard className="h-4 w-4" />}
            label="Overview"
          />
          <NavTab
            active={!selectedDoc && activeTab === "verify"}
            onClick={() => {
              setSelectedDoc(null);
              setActiveTab("verify");
            }}
            icon={<Upload className="h-4 w-4" />}
            label="Verify Document"
          />
          <NavTab
            active={!selectedDoc && activeTab === "review"}
            onClick={() => {
              setSelectedDoc(null);
              setActiveTab("review");
            }}
            icon={<ClipboardList className="h-4 w-4" />}
            label="Manual Review Queue"
            badge={stats?.manual_review}
          />
          <NavTab
            active={!selectedDoc && activeTab === "audit"}
            onClick={() => {
              setSelectedDoc(null);
              setActiveTab("audit");
            }}
            icon={<History className="h-4 w-4" />}
            label="Audit Logs"
          />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {error && (
          <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {selectedDoc ? (
          <DocumentInspector
            document={selectedDoc}
            onBack={() => setSelectedDoc(null)}
            onUpdated={handleUpdated}
            onDeleted={handleDeleted}
          />
        ) : activeTab === "verify" ? (
          <UploadPanel samples={samples} onVerified={handleVerified} />
        ) : activeTab === "audit" ? (
          <AuditLogView onSelectDocument={openDocument} />
        ) : activeTab === "review" ? (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-white">Manual Review Queue</h2>
                <p className="mt-0.5 text-xs text-slate-400">
                  Documents flagged with warnings, discrepancies, or moderate confidence awaiting
                  compliance analyst sign-off.
                </p>
              </div>
              <button
                onClick={() => setActiveTab("verify")}
                className="rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
              >
                + Verify New Document
              </button>
            </div>
            <div className="mt-5">
              {reviewQueueDocs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-800 py-12 text-center">
                  <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-400" />
                  <p className="mt-2 text-sm font-medium text-slate-200">Review queue is clear</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Try running the &ldquo;Bank Statement (Name Discrepancy)&rdquo; scenario to test
                    analyst review routing.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {reviewQueueDocs.map((doc) => (
                    <div
                      key={doc.id}
                      onClick={() => void openDocument(doc.id)}
                      className="flex cursor-pointer flex-wrap items-center justify-between gap-4 rounded-xl border border-amber-500/20 bg-slate-950/80 p-4 transition hover:border-amber-500/50"
                    >
                      <div>
                        <div className="flex items-center gap-2.5">
                          <span className="text-sm font-semibold text-white">{doc.filename}</span>
                          <StatusBadge status={doc.status} />
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          {doc.outcome?.summary_reason}
                        </p>
                      </div>
                      <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-300">
                        Inspect &amp; Decide &rarr;
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Overview Dashboard */
          <div className="space-y-6">
            {/* KPI Strip */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <KpiCard
                icon={<FileCheck2 className="h-4 w-4 text-indigo-400" />}
                label="Total Processed"
                value={String(stats?.total_documents ?? 0)}
                sub={`Avg ${stats?.avg_processing_time_ms ?? 0} ms`}
              />
              <KpiCard
                icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}
                label="Passed"
                value={String(stats?.passed ?? 0)}
                sub={`${stats?.pass_rate ?? 0}% pass rate`}
                accent="text-emerald-400"
              />
              <KpiCard
                icon={<AlertTriangle className="h-4 w-4 text-amber-400" />}
                label="Manual Review"
                value={String(stats?.manual_review ?? 0)}
                sub="Pending analyst action"
                accent="text-amber-400"
              />
              <KpiCard
                icon={<XCircle className="h-4 w-4 text-rose-400" />}
                label="Failed"
                value={String(stats?.failed ?? 0)}
                sub="Critical violations"
                accent="text-rose-400"
              />
              <KpiCard
                icon={<Activity className="h-4 w-4 text-sky-400" />}
                label="Pipeline Health"
                value="Operational"
                sub="4-stage deterministic flow"
                accent="text-sky-400"
              />
            </div>

            {/* Quick Action Callout when empty */}
            {!loading && documents.length === 0 && (
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 p-6">
                <div>
                  <h2 className="text-base font-semibold text-white">
                    Ready to verify your first document
                  </h2>
                  <p className="mt-1 text-xs text-slate-300">
                    Upload an identity or financial document, paste OCR text, or run one of the 4
                    built-in test scenarios to see PASS, FAIL, and MANUAL REVIEW routing in action.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab("verify")}
                  className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-500"
                >
                  Open Verification Pipeline &rarr;
                </button>
              </div>
            )}

            {/* Recent Documents Table */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-white">Verification History</h2>
                  <p className="mt-0.5 text-xs text-slate-400">
                    Click any record to inspect extracted fields, validation flags, and SQL audit logs.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search filename or applicant..."
                      className="rounded-lg border border-slate-800 bg-slate-950 py-2 pl-8 pr-3 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                    />
                  </div>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="ALL">All Decisions</option>
                    <option value="PASS">PASS</option>
                    <option value="MANUAL_REVIEW">MANUAL REVIEW</option>
                    <option value="FAIL">FAIL</option>
                  </select>
                  <button
                    onClick={() => void loadDashboard()}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Refresh
                  </button>
                </div>
              </div>

              <div className="mt-5 overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-500">
                      <th className="py-3 pr-4">Document</th>
                      <th className="py-3 pr-4">Detected Type</th>
                      <th className="py-3 pr-4">Applicant</th>
                      <th className="py-3 pr-4">Decision</th>
                      <th className="py-3 pr-4">Risk</th>
                      <th className="py-3 pr-4">Flags</th>
                      <th className="py-3 text-right">Processed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {loading ? (
                      <tr>
                        <td colSpan={7} className="py-10 text-center text-slate-500">
                          Loading verification records...
                        </td>
                      </tr>
                    ) : documents.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-10 text-center text-slate-500">
                          No documents match the current filters.
                        </td>
                      </tr>
                    ) : (
                      documents.map((doc) => (
                        <tr
                          key={doc.id}
                          onClick={() => void openDocument(doc.id)}
                          className="cursor-pointer transition hover:bg-slate-800/40"
                        >
                          <td className="py-3.5 pr-4">
                            <div className="font-medium text-white">{doc.filename}</div>
                            <div className="font-mono text-[10px] text-slate-500">
                              {doc.extraction_engine || "n/a"}
                            </div>
                          </td>
                          <td className="py-3.5 pr-4 capitalize text-slate-300">
                            {(doc.detected_doc_type || "unknown").replace("_", " ")}
                          </td>
                          <td className="py-3.5 pr-4 text-slate-300">
                            {doc.applicant_name || <span className="text-slate-600">—</span>}
                          </td>
                          <td className="py-3.5 pr-4">
                            <StatusBadge status={doc.status} />
                          </td>
                          <td className="py-3.5 pr-4 font-mono text-slate-300">
                            {doc.outcome ? `${doc.outcome.risk_score}/100` : "—"}
                          </td>
                          <td className="py-3.5 pr-4 text-slate-300">
                            {doc.outcome ? doc.outcome.validation_flags.length : 0}
                          </td>
                          <td className="whitespace-nowrap py-3.5 text-right text-slate-400">
                            {new Date(doc.created_at).toLocaleString()}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function NavTab({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-xs font-medium transition ${
        active
          ? "border-indigo-500 text-white"
          : "border-transparent text-slate-400 hover:border-slate-700 hover:text-slate-200"
      }`}
    >
      {icon}
      {label}
      {badge != null && badge > 0 && (
        <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300">
          {badge}
        </span>
      )}
    </button>
  );
}

function KpiCard({
  icon,
  label,
  value,
  sub,
  accent = "text-white",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{label}</span>
        {icon}
      </div>
      <div className={`mt-2 text-2xl font-bold tracking-tight ${accent}`}>{value}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}

export default App;
