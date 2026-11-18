export type DecisionType = "PASS" | "FAIL" | "MANUAL_REVIEW";
export type SeverityType = "CRITICAL" | "WARNING" | "INFO";

export interface ValidationFlag {
  rule_code: string;
  severity: SeverityType;
  field: string | null;
  message: string;
}

export interface ExtractedFields {
  document_category: string;
  document_type: string;
  full_name: string | null;
  document_number: string | null;
  date_of_birth: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  issuing_authority: string | null;
  country: string | null;
  address: string | null;
  institution_name: string | null;
  account_number: string | null;
  statement_period: string | null;
  currency: string | null;
  total_amount: number | null;
  tax_id: string | null;
  confidence_score: number;
  extraction_notes: string | null;
  raw_json: Record<string, unknown>;
}

export interface VerificationOutcome {
  initial_decision: DecisionType;
  final_decision: DecisionType;
  risk_score: number;
  confidence_score: number;
  validation_flags: ValidationFlag[];
  summary_reason: string;
  reviewed_by: string | null;
  review_notes: string | null;
  reviewed_at: string | null;
}

export interface AuditLogEntry {
  id: number;
  document_id: string;
  event_type: string;
  stage: string;
  actor: string;
  message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface DocumentSummary {
  id: string;
  filename: string;
  content_type: string;
  file_size: number;
  requested_doc_type: string;
  detected_doc_type: string | null;
  applicant_name: string | null;
  status: string;
  ocr_engine: string | null;
  extraction_engine: string | null;
  processing_time_ms: number | null;
  created_at: string;
  updated_at: string;
  outcome: VerificationOutcome | null;
}

export interface DocumentDetail extends DocumentSummary {
  file_hash: string;
  applicant_dob: string | null;
  applicant_id_number: string | null;
  raw_ocr_text: string | null;
  ocr_confidence: number | null;
  extracted_fields: ExtractedFields | null;
  audit_logs: AuditLogEntry[];
}

export interface PipelineStats {
  total_documents: number;
  passed: number;
  failed: number;
  manual_review: number;
  pass_rate: number;
  avg_processing_time_ms: number;
  groq_configured: boolean;
  tesseract_available: boolean;
  groq_model: string;
}

export interface SampleScenario {
  id: string;
  title: string;
  doc_type: string;
  category: string;
  expected_outcome: DecisionType;
  description: string;
  applicant_name: string | null;
  applicant_dob: string | null;
  applicant_id_number: string | null;
}
