import type {
  AuditLogEntry,
  DocumentDetail,
  DocumentSummary,
  PipelineStats,
  SampleScenario,
} from "../types/api";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      // ignore non-JSON errors
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  getStats: () => request<PipelineStats>("/api/v1/stats"),

  getSamples: () => request<SampleScenario[]>("/api/v1/samples"),

  runSample: (sampleId: string) =>
    request<DocumentDetail>(`/api/v1/samples/${encodeURIComponent(sampleId)}/run`, {
      method: "POST",
    }),

  listDocuments: (params?: { status?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.status && params.status !== "ALL") query.set("status", params.status);
    if (params?.search?.trim()) query.set("search", params.search.trim());
    const qs = query.toString();
    return request<DocumentSummary[]>(`/api/v1/documents${qs ? `?${qs}` : ""}`);
  },

  getDocument: (id: string) => request<DocumentDetail>(`/api/v1/documents/${encodeURIComponent(id)}`),

  deleteDocument: (id: string) =>
    request<void>(`/api/v1/documents/${encodeURIComponent(id)}`, { method: "DELETE" }),

  verifyFile: (formData: FormData) =>
    request<DocumentDetail>("/api/v1/documents/verify", {
      method: "POST",
      body: formData,
    }),

  verifyText: (payload: {
    filename: string;
    raw_text: string;
    doc_type: string;
    applicant_name?: string;
    applicant_dob?: string;
    applicant_id_number?: string;
  }) =>
    request<DocumentDetail>("/api/v1/documents/verify-text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  submitReview: (
    documentId: string,
    payload: { decision: "PASS" | "FAIL"; reviewer_name: string; notes: string }
  ) =>
    request<DocumentDetail>(`/api/v1/documents/${encodeURIComponent(documentId)}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  listAuditLogs: (params?: { stage?: string; document_id?: string }) => {
    const query = new URLSearchParams();
    if (params?.stage && params.stage !== "all") query.set("stage", params.stage);
    if (params?.document_id) query.set("document_id", params.document_id);
    const qs = query.toString();
    return request<AuditLogEntry[]>(`/api/v1/audit-logs${qs ? `?${qs}` : ""}`);
  },
};
