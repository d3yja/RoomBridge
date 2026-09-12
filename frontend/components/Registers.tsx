import { NeedStatus, STATUS_META } from "@/lib/api";

/** Explicitly STATED content. Solid, dark, quote mark. Never used for AI output. */
export function Stated({ children }: { children: React.ReactNode }) {
  return (
    <div className="reg-stated p-3">
      <span className="chip bg-blue-50 text-stated border border-blue-200">stated</span>
      <div className="mt-1.5 text-[13px] leading-snug text-ink">{children}</div>
    </div>
  );
}

/** AI-GENERATED content. Dashed, muted, "AI" chip. Never used for stated content. */
export function Inferred({ children, kind = "AI-inferred" }:
  { children: React.ReactNode; kind?: string }) {
  return (
    <div className="reg-inferred p-3">
      <span className="chip bg-purple-100 text-inferred border border-purple-200">{kind}</span>
      <div className="mt-1.5 text-[13px] leading-snug text-[#3b2e57]">{children}</div>
    </div>
  );
}

export function StatusDot({ status, hollow }: { status?: NeedStatus; hollow?: boolean }) {
  if (!status || hollow) {
    return <span className="dot" style={{ border: "2px solid #c9c4b6", background: "transparent" }} />;
  }
  const m = STATUS_META[status];
  const filled = status === "preserved" || status === "partially_preserved";
  return (
    <span className="dot" style={{
      background: filled ? m.color : "transparent",
      border: `2px solid ${m.ring}`,
    }} title={m.label} />
  );
}

export function StatusPill({ status }: { status: NeedStatus }) {
  const m = STATUS_META[status];
  return (
    <span className="chip" style={{
      color: m.color, background: `${m.color}14`, border: `1px solid ${m.color}44`,
    }}>{m.label}</span>
  );
}
