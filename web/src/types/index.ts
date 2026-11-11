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

export interface RadarExampleDecision {
  action: FindingDecision;
  user_id: string;
  reason?: string | null;
}

export interface RadarExampleFinding {
  finding_id: string;
  revision_id: string;
  type: string;
  severity: FindingSeverity;
  confidence: number;
  abstained: boolean;
  status: string;
  quote: string;
  explanation: string;
  is_synthetic: boolean;
  decisions: RadarExampleDecision[];
}

export interface RadarSignalMetrics {
  total_findings: number;
  accepted_count: number;
  overridden_count: number;
  disputed_count: number;
  abstained_count: number;
  low_confidence_count: number;
  disagreement_count: number;
  collision_count: number;
  collisions: string[];
  lint_flags: string[];
  missing_owner: boolean;
  missing_examples: boolean;
  synthetic_count: number;
  live_count: number;
  override_dispute_rate: number;
  abstain_rate: number;
  low_confidence_rate: number;
  disagreement_rate: number;
}

export interface RadarRuleEntry {
  rule_id: string;
  rule_name: string;
  rule_body: string;
  current_version: number;
  flagged: boolean;
  ambiguity_score: number;
  flag_reasons: string[];
  is_control: boolean;
  is_synthetic: boolean;
  data_origin: "live" | "synthetic" | "mixed";
  signals: RadarSignalMetrics;
  example_findings: RadarExampleFinding[];
}

export interface RadarSummary {
  total_rules_evaluated: number;
  flagged_count: number;
  seeded_ambiguous_flagged_count: number;
  seeded_ambiguous_total: number;
  control_rules_evaluated: number;
  false_flags: number;
  false_flagged_rule_ids: string[];
  false_flag_rate: number;
  total_synthetic_findings: number;
  total_live_findings: number;
  contains_synthetic: boolean;
  data_origin: "live" | "synthetic" | "mixed";
}

export interface RadarData {
  tenant_id: string;
  summary: RadarSummary;
  thresholds: {
    min_sample_size: number;
    override_dispute_rate: number;
    abstain_rate: number;
    low_confidence_floor: number;
    low_confidence_rate: number;
    disagreement_rate: number;
    collision_count: number;
  };
  rules: RadarRuleEntry[];
}

export interface ImpactItem {
  content_id: string;
  title: string;
  file_type: string;
  revision_id: string;
  version_num: number;
  revision_status: string;
  approval_status: string;
  sensitivity: SensitivityLevel;
  latest_run_id: string;
  latest_run_status: string;
  matched_via: "supported_claim" | "finding_evidence";
  findings_for_source_count: number;
  last_checked_at: string;
}

export interface ImpactAnalysisData {
  source_id: string;
  source_name?: string;
  source_kind?: string;
  current_version?: number;
  affected_count: number;
  affected_items: ImpactItem[];
}

export interface RecurringRuleItem {
  rule_id: string;
  rule_name: string;
  total_count: number;
  open_count: number;
  accepted_count: number;
  overridden_count: number;
  disputed_count: number;
  synthetic_count: number;
  live_count: number;
  avg_confidence: number;
  is_synthetic: boolean;
}

export interface RecurringTypeItem {
  type: string;
  count: number;
  share: number;
}

export interface RecurringSeverityItem {
  severity: FindingSeverity;
  count: number;
}

export interface AffectedContentHotspot {
  content_id: string;
  title: string;
  total_findings: number;
  open_findings: number;
  is_synthetic: boolean;
}

export interface RecurringInsightsData {
  tenant_id: string;
  summary: {
    total_findings: number;
    open_findings: number;
    resolved_findings: number;
    resolution_rate: number;
    accepted_count: number;
    overridden_count: number;
    disputed_count: number;
    rejected_count: number;
    synthetic_findings: number;
    live_findings: number;
    contains_synthetic: boolean;
  };
  top_violated_rules: RecurringRuleItem[];
  by_type: RecurringTypeItem[];
  by_severity: RecurringSeverityItem[];
  top_affected_content: AffectedContentHotspot[];
}


