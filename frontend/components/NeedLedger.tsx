"use client";
import { Need, NeedStatus } from "@/lib/api";
import { StatusDot } from "./Registers";

/** The persistent needs ledger — the hero of the UI (plan section 12). Left rail, always
 *  visible; each dot turns from hollow (grey) to a status colour as the audit lands. */
export function NeedLedger({
  needs, participants, statusByNeed, highlightNeed, onHighlight,
}: {
  needs: Need[];
  participants: { participant_id: string; display_name: string }[];
  statusByNeed: Record<string, NeedStatus | undefined>;
  highlightNeed?: string | null;
  onHighlight?: (needId: string | null) => void;
}) {
  return (
    <div className="space-y-4">
      {participants.map((p) => {
        const owned = needs.filter((n) => n.owner_id === p.participant_id);
        return (
          <div key={p.participant_id}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500 mb-1.5">
              {p.display_name}
            </div>
            <div className="space-y-1.5">
              {owned.map((n) => {
                const active = highlightNeed === n.need_id;
                return (
                  <button
                    key={n.need_id}
                    onClick={() => onHighlight?.(active ? null : n.need_id)}
                    className={`w-full text-left flex gap-2 items-start p-2 rounded-md border transition
                      ${active ? "border-ink bg-white shadow-sm" : "border-transparent hover:bg-white/60"}`}
                  >
                    <span className="mt-0.5"><StatusDot status={statusByNeed[n.need_id]} /></span>
                    <span className="min-w-0">
                      <span className="font-mono text-[10px] text-neutral-400">{n.need_id}</span>
                      {n.stated_as_boundary && (
                        <span className="ml-1 chip bg-red-50 text-lost border border-red-200">boundary</span>
                      )}
                      <span className="block text-[12px] leading-tight text-ink truncate">
                        {n.normalized || n.verbatim}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
      <Legend />
    </div>
  );
}

function Legend() {
  return (
    <div className="pt-3 mt-2 border-t border-[#e5e2d8] space-y-1 text-[11px] text-neutral-500">
      <div className="flex items-center gap-2"><span className="dot" style={{background:"#1a7f37"}} /> preserved</div>
      <div className="flex items-center gap-2"><span className="dot" style={{background:"#bf8700"}} /> partial</div>
      <div className="flex items-center gap-2"><span className="dot" style={{border:"2px solid #cf222e",background:"transparent"}} /> lost / not addressed</div>
      <div className="flex items-center gap-2"><span className="dot" style={{border:"2px solid #c9c4b6",background:"transparent"}} /> not yet audited</div>
    </div>
  );
}
