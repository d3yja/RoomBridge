"use client";
import { useEffect, useRef, useState } from "react";
import {
  listScenarios, getScenario, latestRun, Need, RunView, ScenarioView, NeedStatus, Provider,
} from "@/lib/api";
import { NeedLedger } from "@/components/NeedLedger";
import { Stated, Inferred, StatusPill } from "@/components/Registers";
import { AgreementCard } from "@/components/AgreementCard";

const CONDS = [
  { key: "A", label: "A · Generic" }, { key: "B", label: "B · Context" },
  { key: "C", label: "C · Multi-agent" }, { key: "D", label: "D · RoomBridge" },
];

export default function Workbench() {
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [sid, setSid] = useState("sc_001_quiet_vs_social");
  const [cond, setCond] = useState("D");
  const [scenario, setScenario] = useState<ScenarioView | null>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [run, setRun] = useState<RunView | null>(null);
  const [running, setRunning] = useState(false);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<Record<string, NeedStatus>>({});
  const [provider, setProvider] = useState<Provider>("mock");
  const [note, setNote] = useState<string>("");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => { listScenarios().then(setScenarios); }, []);
  useEffect(() => { getScenario(sid).then(setScenario); }, [sid]);

  // View an existing cached run for this scenario+condition+provider (no streaming, no spend).
  async function loadCached() {
    esRef.current?.close();
    setEvents([]); setRun(null); setLiveStatus({}); setNote("");
    const r = await latestRun(sid, cond, provider);
    if (r) { setRun(r); setEvents([`loaded cached ${provider} run`]); }
    else setNote(`No cached ${provider} run for ${sid} / ${cond}. Run it via the CLI, or use ▶ Run to stream a fresh one.`);
  }

  function start() {
    esRef.current?.close();
    setEvents([]); setRun(null); setLiveStatus({}); setRunning(true); setNote("");
    const es = new EventSource(`/api/runs/stream/${sid}/${cond}?provider=${provider}`);
    esRef.current = es;
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.kind === "final") { setRun(ev.run); setRunning(false); es.close(); return; }
      if (ev.kind === "error") { setEvents((e) => [...e, `error: ${ev.message}`]); setRunning(false); es.close(); return; }
      if (ev.kind === "audit" && ev.phase === "final") {
        setLiveStatus((s) => ({ ...s, [ev.need_id]: ev.status as NeedStatus }));
      }
      setEvents((e) => [...e, label(ev)]);
    };
    es.onerror = () => { setRunning(false); es.close(); };
  }

  const needs: Need[] = scenario?.needs ?? [];
  const finalStatus: Record<string, NeedStatus> = {};
  run?.audits.filter((a) => a.phase === "final").forEach((a) => (finalStatus[a.need_id] = a.status));
  const statusByNeed = run ? finalStatus : liveStatus;

  return (
    <div className="px-4 py-4">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select value={sid} onChange={(e) => setSid(e.target.value)}
          className="border border-[#d4d0c4] rounded-md px-3 py-1.5 text-sm bg-white">
          {scenarios.map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.title}</option>)}
        </select>
        <div className="flex rounded-md overflow-hidden border border-[#d4d0c4]">
          {CONDS.map((c) => (
            <button key={c.key} onClick={() => setCond(c.key)}
              className={`px-3 py-1.5 text-sm ${cond === c.key ? "bg-ink text-white" : "bg-white text-neutral-600"}`}>
              {c.label}
            </button>
          ))}
        </div>
        <div className="flex rounded-md overflow-hidden border border-[#d4d0c4]">
          {(["mock", "openrouter"] as Provider[]).map((p) => (
            <button key={p} onClick={() => setProvider(p)}
              className={`px-3 py-1.5 text-sm ${provider === p ? "bg-ink text-white" : "bg-white text-neutral-600"}`}>
              {p === "mock" ? "Mock" : "OpenRouter"}
            </button>
          ))}
        </div>
        <button onClick={loadCached} disabled={running}
          className="rounded-md border border-[#d4d0c4] bg-white px-3 py-1.5 text-sm font-medium disabled:opacity-50">
          View cached
        </button>
        <button onClick={start} disabled={running}
          className="rounded-md bg-stated text-white px-4 py-1.5 text-sm font-medium disabled:opacity-50"
          title={provider === "openrouter" ? "streams a fresh run — calls the model (costs money)" : "streams a fresh mock run"}>
          {running ? "Running…" : "▶ Run"}
        </button>
        {note && <span className="text-[12px] text-lost">{note}</span>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_360px] gap-4">
        {/* LEFT: persistent needs ledger */}
        <aside className="rounded-lg border border-[#e5e2d8] bg-paper p-3 h-fit">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500 mb-3">
            Needs ledger
          </h2>
          {scenario && (
            <NeedLedger needs={needs} participants={scenario.participants}
              statusByNeed={statusByNeed} highlightNeed={highlight} onHighlight={setHighlight} />
          )}
        </aside>

        {/* CENTRE: mediation */}
        <section className="space-y-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Mediation</h2>
          <div className="rounded-lg border border-[#e5e2d8] bg-white p-3 font-mono text-[11px] text-neutral-600 max-h-40 overflow-auto">
            {events.length === 0 && <span className="text-neutral-400">Pipeline events stream here…</span>}
            {events.map((e, i) => <div key={i}>{e}</div>)}
          </div>
          {run && (
            <div>
              <h3 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500 mb-1.5">
                Final agreement
              </h3>
              <AgreementCard run={run} highlightNeed={highlight} dimUnhighlighted={false} />
              {run.chosen_agreement?.rationale && (
                <details className="mt-1.5">
                  <summary className="text-[11px] text-neutral-500 cursor-pointer">why this agreement?</summary>
                  <p className="mt-1 text-[12px] text-neutral-600">{run.chosen_agreement.rationale}</p>
                </details>
              )}
            </div>
          )}
        </section>

        {/* RIGHT: preservation audit */}
        <aside className="space-y-3">
          <h2 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Preservation audit
          </h2>
          {run ? (
            <>
              {needs.map((n) => {
                const a = run.audits.find((x) => x.phase === "final" && x.need_id === n.need_id);
                if (!a) return null;
                return (
                  <div key={n.need_id}
                    className={`rounded-md border p-2.5 ${highlight === n.need_id ? "border-ink" : "border-[#e5e2d8]"} bg-white`}>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[10px] text-neutral-400">{n.need_id}</span>
                      <StatusPill status={a.status} />
                      <span className="ml-auto text-[10px] text-neutral-400">
                        consistency {Math.round(a.self_consistency * 100)}%
                      </span>
                    </div>
                    {a.evidence_quote ? (
                      <p className="mt-1 text-[12px] text-preserved">“{a.evidence_quote}”</p>
                    ) : (
                      <p className="mt-1 text-[12px] text-lost">no supporting text found in the agreement</p>
                    )}
                  </div>
                );
              })}
              {run.assumptions.length > 0 && (
                <div className="rounded-md border border-purple-200 bg-purple-50 p-2.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-inferred mb-1">
                    Assumptions detected
                  </div>
                  {run.assumptions.map((as, i) => (
                    <p key={i} className="text-[12px] text-[#3b2e57]">⚠ {as.type}: {as.text}</p>
                  ))}
                </div>
              )}
              <div className="rounded-md border border-[#e5e2d8] bg-white p-2.5 text-[12px]">
                <b>Escalation:</b> {run.escalated ? run.escalation?.category : "none"}
                {run.culture_diff_rate != null && (
                  <div className="text-neutral-500 mt-1">
                    culture diff rate: {Math.round(run.culture_diff_rate * 100)}%
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-[12px] text-neutral-400">Audit verdicts appear here after the run.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function label(ev: any): string {
  if (ev.kind === "llm_call") return `· ${ev.step}`;
  if (ev.kind === "audit") return `  audit[${ev.phase}] ${ev.need_id} → ${ev.status}`;
  if (ev.kind === "assumptions") return `  ⚠ ${ev.count} assumption(s) via ${ev.detected_by}`;
  if (ev.kind === "escalation") return `  ⛔ escalation: ${ev.category}`;
  if (ev.kind === "done") return `done (${ev.status})`;
  return ev.kind;
}
