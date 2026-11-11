export type UserRole = "admin" | "creator" | "reviewer" | "legal_reviewer";

export type SensitivityLevel = "public" | "internal" | "confidential" | "restricted";

export type FindingType =
  | "violation"
  | "contradicted"
  | "outdated"
  | "unsupported"
  | "needs_judgment"
  | "visual"
  | "accessibility";

export type FindingSeverity = "low" | "medium" | "high" | "critical";

export type FindingDecision = "accept" | "reject" | "override" | "dispute";

export interface Span {
  unit_id: string;
  start: number;
  end: number;
  quote: string;
}

export interface EvidenceItem {
  source: string;
  version: number;
  status: "active" | "superseded" | "unverified";
  current_version?: number;
  current_value?: string;
  effective?: string;
  trace?: string;
}

export interface SuggestedFix {
  text: string;
  edit_budget?: "minimal" | "moderate" | "significant";
  rechecked?: boolean;
  intent_similarity?: number;
}

export interface FindingDisclosure {
  method: "deterministic_lookup" | "regex" | "temporal_ledger" | "ciede2000" | "wcag_contrast" | "llm_assisted";
  external_call: boolean;
  sensitivity: SensitivityLevel;
  assisted?: boolean;
}

export interface Finding {
  finding_id: string;
  revision_id: string;
  type: FindingType;
  severity: FindingSeverity;
  confidence: number;
  span: Span;
  evidence: EvidenceItem[];
  explanation: string;
  suggested_fix?: SuggestedFix;
  route_to: UserRole;
  disclosure: FindingDisclosure;
  status: "open" | "accepted" | "rejected" | "overridden" | "disputed";
  decision?: FindingDecision;
  decision_reason?: string;
}

export interface ContentUnit {
  unit_id: string;
  revision_id?: string;
  kind: "text" | "heading" | "image" | "table" | "ocr";
  text: string;
  offsets: [number, number];
  page: number;
  bbox?: [number, number, number, number, number]; // [page, x0, y0, x1, y1] normalized to 0.0 - 1.0
  style?: Record<string, any>;
  alt_text?: string;
}

export interface IntentCard {
  purpose: string;
  audience: string;
  key_message: string;
  cta: string;
}

export interface SourceVersion {
  version: number;
  content_hash: string;
  body: string;
  value?: string;
  unit?: string;
  valid_from: string;
  valid_until?: string | null;
  superseded_by?: number | null;
  created_at: string;
}

export interface Source {
  id: string;
  tenant_id: string;
  kind: "rule" | "fact" | "term" | "asset";
  name: string;
  current_version: number;
  status: "active" | "superseded" | "deprecated";
  versions: SourceVersion[];
  created_at: string;
}

export interface Revision {
  id: string;
  content_id: string;
  version: number;
  content_hash: string;
  file_name: string;
  file_type: "markdown" | "text" | "pdf" | "docx" | "image";
  file_url?: string;
  sensitivity: SensitivityLevel;
  approval_status: "draft" | "in_review" | "approved" | "invalidated" | "rejected";
  created_at: string;
}

export interface ContentItem {
  id: string;
  title: string;
  sensitivity: SensitivityLevel;
  current_revision: number;
  revisions: Revision[];
  created_at: string;
}

export interface ReviewRunProgress {
  status: "queued" | "running" | "done" | "partial" | "failed";
  progress: number;
  active_step?: string;
  findings_count: number;
  cached?: boolean;
}

