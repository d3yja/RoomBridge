"use client";
import { RunView } from "@/lib/api";
import { StatusPill } from "./Registers";

/** Renders one condition's agreement with each term highlightable by the need it addresses. */
export function AgreementCard({
  run, highlightNeed, dimUnhighlighted,
}: { run: RunView; highlightNeed?: string | null; dimUnhighlighted?: boolean }) {
  if (run.escalated) return <EscalationCard run={run} />;
  const terms = run.chosen_agreement?.terms ?? [];
  return (
    <div className="reg-inferred p-3">
      <span className="chip bg-purple-100 text-inferred border border-purple-200">
        AI agreement
      </span>
      <ol className="mt-2 space-y-1.5 list-decimal list-inside text-[13px] text-[#3b2e57]">
        {terms.map((t, i) => {
          const addresses = t.addresses_need_ids || [];
          const isHi = highlightNeed && addresses.includes(highlightNeed);
          const dim = dimUnhighlighted && highlightNeed && !isHi;
          return (
            <li key={i} className={`leading-snug ${dim ? "opacity-25" : ""}
              ${isHi ? "bg-yellow-100 rounded px-1" : ""}`}>
              {t.text}
              {addresses.length > 0 && (
                <span className="ml-1 font-mono text-[10px] text-neutral-400">
                  {addresses.join(" ")}
                </span>
              )}
            </li>
          );
        })}
        {terms.length === 0 && <li className="opacity-60">No agreement produced.</li>}
      </ol>
    </div>
  );
}

export function EscalationCard({ run }: { run: RunView }) {
  const e = run.escalation;
  return (
    <div className="rounded-md border-2 border-lost bg-red-50 p-4">
      <div className="flex items-center gap-2">
        <span className="chip bg-lost text-white">escalated to humans</span>
        {e?.category && <span className="text-sm font-semibold text-lost uppercase">{e.category}</span>}
      </div>
      <p className="mt-2 text-[13px] text-ink"><b>Why:</b> {e?.reason}</p>
      {e?.triggering_span && (
        <p className="mt-1 text-[13px] text-ink"><b>Triggered by:</b> “{e.triggering_span}”</p>
      )}
      {e?.not_attempted?.length ? (
        <p className="mt-1 text-[13px] text-neutral-600">
          <b>The AI did NOT attempt:</b> {e.not_attempted.join("; ")}
        </p>
      ) : null}
      <p className="mt-1 text-[13px] text-ink"><b>Suggested support:</b> {e?.suggested_support}</p>
    </div>
  );
}
