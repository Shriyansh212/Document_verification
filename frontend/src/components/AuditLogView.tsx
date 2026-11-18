import { useEffect, useState } from "react";
import { Filter, RefreshCw } from "lucide-react";

import { api } from "../lib/api";
import type { AuditLogEntry } from "../types/api";

interface AuditLogViewProps {
  onSelectDocument: (id: string) => void;
}

const STAGES = ["all", "ingestion", "ocr", "extraction", "validation", "decision", "review"];

export function AuditLogView({ onSelectDocument }: AuditLogViewProps) {
  const [stage, setStage] = useState("all");
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchLogs(selectedStage: string) {
    setLoading(true);
    try {
      const data = await api.listAuditLogs({ stage: selectedStage });
      setLogs(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchLogs(stage);
  }, [stage]);

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-white">SQL Audit Ledger</h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Immutable event history across OCR, Groq Llama extraction, validation, routing, and manual reviews.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1.5 text-xs text-slate-400">
            <Filter className="h-3.5 w-3.5" />
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none"
            >
              {STAGES.map((s) => (
                <option key={s} value={s} className="bg-slate-900">
                  Stage: {s.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => void fetchLogs(stage)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
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
              <th className="py-3 pr-4">Timestamp</th>
              <th className="py-3 pr-4">Event</th>
              <th className="py-3 pr-4">Stage</th>
              <th className="py-3 pr-4">Actor</th>
              <th className="py-3 pr-4">Details</th>
              <th className="py-3 text-right">Document</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  Loading audit logs...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500">
                  No audit events recorded yet. Run a verification to populate the ledger.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/30">
                  <td className="whitespace-nowrap py-3 pr-4 font-mono text-[11px] text-slate-400">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-4 font-mono font-semibold text-indigo-300">
                    {log.event_type}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-4">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-300">
                      {log.stage}
                    </span>
                  </td>
                  <td className="whitespace-nowrap py-3 pr-4 text-slate-300">{log.actor}</td>
                  <td className="max-w-md py-3 pr-4 text-slate-300">{log.message}</td>
                  <td className="whitespace-nowrap py-3 text-right">
                    <button
                      onClick={() => onSelectDocument(log.document_id)}
                      className="font-mono text-sky-400 hover:text-sky-300 hover:underline"
                    >
                      {log.document_id.slice(0, 8)}&hellip;
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
