export const API = "/api";

export type NeedStatus =
  | "preserved" | "partially_preserved" | "unresolved" | "not_addressed" | "violated";

export interface Need {
  need_id: string; owner_id: string; verbatim: string; normalized: string;
  category: string; stated_importance: number | null; stated_as_boundary: boolean;
}
export interface ScenarioView {
  scenario_id: string; title: string; participants: { participant_id: string;
    display_name: string; background_context: string }[];
  needs: Need[]; notes: string; expected_observations: string[];
  gold_audit: Record<string, string>; should_escalate: boolean;
}
export interface Audit {
  need_id: string; phase: string; status: NeedStatus; evidence_quote: string | null;
  rationale: string; self_consistency: number; samples: any[];
}
export interface RunView {
  run_id: string; condition: string; status: string; escalated: boolean;
  final_agreement_text: string | null; culture_diff_rate: number | null;
  chosen_agreement: { terms: { text: string; addresses_need_ids: string[] }[];
    rationale: string } | null;
  audits: Audit[];
  assumptions: { text: string; type: string; detected_by: string; severity: string }[];
  policy_audits?: PolicyAudit[];
  escalation: { category: string; triggered_by: string; reason: string;
    triggering_span: string; not_attempted: string[]; suggested_support: string } | null;
  metrics: Record<string, number | Record<string, number>>;
  messages: { round: number; agent: string; content: string }[];
  cached?: boolean;
  no_run?: boolean;
}

export type Provider = "mock" | "openrouter";

export interface PolicyAudit {
  rule_id: string; status: "compliant" | "violated" | "not_applicable" | "advisory";
  type: "hard" | "guideline"; title: string; source: string;
  evidence_quote: string | null; detected_by: string;
}

export function policyViolations(run: RunView): PolicyAudit[] {
  return (run.policy_audits ?? []).filter((p) => p.status === "violated");
}
export function policyCompliance(run: RunView): number | null {
  const v = run.metrics?.policy_compliance_rate;
  return typeof v === "number" ? v : null;
}

export interface Availability {
  has_mock: boolean; has_openrouter: boolean; models: string[]; n_runs: number;
}

export async function listScenarios() {
  return (await fetch(`${API}/scenarios`)).json();
}
export async function getScenario(id: string): Promise<ScenarioView> {
  return (await fetch(`${API}/scenarios/${id}`)).json();
}
export async function getAvailability(id: string): Promise<Availability> {
  return (await fetch(`${API}/runs/available/${id}`)).json();
}
export async function runDemo(
  scenario_id: string, provider: Provider = "mock", live = false,
): Promise<{ scenario: ScenarioView; conditions: Record<string, RunView> }> {
  return (await fetch(`${API}/demo`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider, live }),
  })).json();
}
export async function latestRun(
  scenario_id: string, condition: string, provider: Provider,
): Promise<RunView | null> {
  const r = await fetch(`${API}/runs/latest/${scenario_id}/${condition}?provider=${provider}`);
  return r.ok ? r.json() : null;
}

export const STATUS_META: Record<NeedStatus, { label: string; color: string; ring: string }> = {
  preserved: { label: "preserved", color: "#1a7f37", ring: "#1a7f37" },
  partially_preserved: { label: "partial", color: "#bf8700", ring: "#bf8700" },
  unresolved: { label: "unresolved", color: "#8c6d1f", ring: "#8c6d1f" },
  not_addressed: { label: "not addressed", color: "#cf222e", ring: "#cf222e" },
  violated: { label: "violated", color: "#cf222e", ring: "#cf222e" },
};
