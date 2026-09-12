"use client";
import { RunView, PolicyAudit } from "@/lib/api";

/** Hall policy compliance panel (plan addendum). Shows each applicable rule with its
 *  status and handbook citation; violations quote the offending term. */
export function PolicyPanel({ run }: { run: RunView }) {
  const rows = (run.policy_audits ?? []).filter((p) => p.status !== "not_applicable");
  const violations = rows.filter((p) => p.status === "violated");
  const compliance = typeof run.metrics?.policy_compliance_rate === "number"
    ? (run.metrics.policy_compliance_rate as number) : null;
  if (rows.length === 0) return null;

  return (
    <div className="rounded-md border border-[#e5e2d8] bg-white p-2.5">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
          Hall policy
        </span>
        {compliance != null && (
          <span className="ml-auto text-[11px] font-mono"
            style={{ color: violations.length ? "#cf222e" : "#1a7f37" }}>
            {Math.round(compliance * 100)}% compliant
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        {rows.map((p) => <PolicyRow key={p.rule_id} p={p} />)}
      </div>
    </div>
  );
}

function PolicyRow({ p }: { p: PolicyAudit }) {
  const violated = p.status === "violated";
  return (
    <div className={`rounded border p-1.5 ${violated ? "border-lost bg-red-50" : "border-[#eee] bg-[#fafafa]"}`}>
      <div className="flex items-center gap-1.5">
        <span className="text-[11px]" style={{ color: violated ? "#cf222e" : "#1a7f37" }}>
          {violated ? "✗" : "✓"}
        </span>
        <span className="text-[12px] text-ink">{p.title}</span>
        {p.type === "hard" && (
          <span className="chip bg-neutral-100 text-neutral-600 border border-neutral-200">hard</span>
        )}
      </div>
      {violated && p.evidence_quote && (
        <p className="mt-0.5 text-[11px] text-lost pl-4">breaks it: “{p.evidence_quote}”</p>
      )}
      <p className="mt-0.5 text-[10px] text-neutral-400 pl-4">{p.source}</p>
    </div>
  );
}
