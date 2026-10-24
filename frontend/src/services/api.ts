export interface Rule {
  id: string;
  title: string;
  level: string;
  logsource: Record<string, string>;
  techniques: string[];
  enabled: boolean;
  version: number;
  updated_at: string;
  validation_status: string;
  yaml_content?: string;
  latest_test: {
    id: string;
    passed: boolean;
    mode: string;
    dataset_id: string;
  } | null;
}
export interface Metrics {
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  precision: number | null;
  recall: number | null;
}
export interface Run {
  id: string;
  rule_id: string;
  rule_version: number;
  dataset_id: string;
  category: string;
  mode: string;
  passed: boolean;
  duration_ms: number;
  created_at: string;
  scope: string;
  metrics: Metrics;
  expected_event_ids: string[];
  actual_event_ids: string[];
  missing_event_ids: string[];
  unexpected_event_ids: string[];
  expected_detection: boolean;
  actual_detection: boolean;
  matched_events: {
    id: string;
    timestamp: string;
    fields: Record<string, string | number | boolean>;
  }[];
}
export interface Overview {
  total_rules: number;
  valid_rules: number;
  invalid_rules: number;
  tested_detections: number;
  untested_detections: number;
  passing_tests: number;
  failing_tests: number;
  test_pass_rate: number | null;
  note: string;
  recent_runs: Run[];
}
export interface Dataset {
  id: string;
  rule_id: string;
  category: string;
  technique: string;
  event_count: number;
  expected_detection: boolean;
}
export interface Conversion {
  queries: string[];
  warning: string;
  profile: string;
  executed: boolean;
}
export interface Version {
  version: number;
  yaml_content: string;
  created_at: string;
}

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: data ? { "Content-Type": "application/json" } : undefined,
    body: data ? JSON.stringify(data) : undefined,
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const details = Array.isArray(result.detail)
      ? result.detail.map((d: { msg: string }) => d.msg).join("; ")
      : result.detail;
    throw new Error(
      result.error?.message || details || `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}
