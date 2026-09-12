"use client";
import { useEffect, useState } from "react";
import {
  listScenarios, runDemo, getAvailability, Need, RunView, ScenarioView, NeedStatus,
  Provider, Availability,
} from "@/lib/api";
import { StatusDot } from "@/components/Registers";
import { AgreementCard } from "@/components/AgreementCard";

const COND_LABEL: Record<string, string> = {
  A: "Generic LLM", B: "Context-informed", C: "Multi-agent", D: "RoomBridge",
};

function finalStatuses(run: RunView): Record<string, NeedStatus> {
  const out: Record<string, NeedStatus> = {};
  run.audits.filter((a) => a.phase === "final").forEach((a) => (out[a.need_id] = a.status));
  return out;
}
function silentLoss(run: RunView): number {
  return Object.values(finalStatuses(run)).filter(
    (s) => s === "not_addressed" || s === "violated").length;
}
function nrr(run: RunView): number | null {
  const v = run.metrics?.nrr;
  return typeof v === "number" ? v : null;
}

export default function DemoPage() {
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [sid, setSid] = useState("sc_001_quiet_vs_social");
  const [scenario, setScenario] = useState<ScenarioView | null>(null);
  const [conditions, setConditions] = useState<Record<string, RunView> | null>(null);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [provider, setProvider] = useState<Provider>("mock");
  const [avail, setAvail] = useState<Availability | null>(null);

  useEffect(() => { listScenarios().then(setScenarios); }, []);
  useEffect(() => { getAvailability(sid).then(setAvail); }, [sid, conditions]);

  async function run() {
    setLoading(true); setConditions(null); setHighlight(null);
    // View-only by default: shows cached runs for the chosen provider, never spends.
    const res = await runDemo(sid, provider, false);
    setScenario(res.scenario); setConditions(res.conditions);
    setLoading(false);
  }

  const order = ["A", "B", "C", "D"];
  const needs: Need[] = scenario?.needs ?? [];

  return (
    <div className="px-6 py-6">
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <select value={sid} onChange={(e) => setSid(e.target.value)}
          className="border border-[#d4d0c4] rounded-md px-3 py-1.5 text-sm bg-white">
          {scenarios.map((s) => (
            <option key={s.scenario_id} value={s.scenario_id}>{s.title}</option>
          ))}
        </select>
        <div className="flex rounded-md overflow-hidden border border-[#d4d0c4]">
          {(["mock", "openrouter"] as Provider[]).map((p) => {
            const has = p === "mock" ? avail?.has_mock : avail?.has_openrouter;
            return (
              <button key={p} onClick={() => { setProvider(p); setConditions(null); }}
                className={`px-3 py-1.5 text-sm ${provider === p ? "bg-ink text-white" : "bg-white text-neutral-600"}`}
                title={has ? "cached runs available" : "no cached runs for this provider yet"}>
                {p === "mock" ? "Mock" : "OpenRouter"}
                {avail && !has && <span className="ml-1 text-[10px] opacity-60">∅</span>}
              </button>
            );
          })}
        </div>
        <button onClick={run} disabled={loading}
          className="rounded-md bg-ink text-white px-4 py-1.5 text-sm font-medium disabled:opacity-50">
          {loading ? "Loading…" : "View results"}
        </button>
        {avail && (
          <span className="text-[11px] text-neutral-400">
            {avail.n_runs} run{avail.n_runs === 1 ? "" : "s"} cached
            {avail.models.length > 0 && ` · ${avail.models.filter((m) => m !== "mock").join(", ") || "mock"}`}
          </span>
        )}
        {conditions && needs.length > 0 && (
          <div className="flex items-center gap-2 ml-2">
            <span className="text-xs text-neutral-500">Reveal the loss:</span>
            {needs.map((n) => (
              <button key={n.need_id}
                onClick={() => setHighlight(highlight === n.need_id ? null : n.need_id)}
                className={`font-mono text-[11px] px-2 py-0.5 rounded border
                  ${highlight === n.need_id ? "bg-yellow-200 border-yellow-500" : "border-[#d4d0c4] bg-white"}`}>
                {n.need_id}
              </button>
            ))}
          </div>
        )}
      </div>

      {conditions && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-3">
            {order.map((letter) => {
              const run = conditions[letter];
              const statuses = finalStatuses(run);
              const loss = silentLoss(run);
              const r = nrr(run);
              const isD = letter === "D";
              if (run.no_run) {
                return (
                  <div key={letter} className="rounded-lg border border-dashed border-[#d4d0c4] bg-white p-3">
                    <div className="font-semibold text-sm">
                      <span className="font-mono text-neutral-400">{letter}</span> {COND_LABEL[letter]}
                    </div>
                    <p className="mt-6 text-[12px] text-neutral-400 text-center">
                      no cached {provider === "openrouter" ? "OpenRouter" : "mock"} run
                    </p>
                  </div>
                );
              }
              return (
                <div key={letter} className={`rounded-lg border bg-white p-3
                  ${isD ? "border-preserved ring-1 ring-preserved/30" : "border-[#e5e2d8]"}`}>
                  <div className="flex items-baseline justify-between">
                    <div className="font-semibold text-sm">
                      <span className="font-mono text-neutral-400">{letter}</span> {COND_LABEL[letter]}
                    </div>
                    {!run.escalated && (
                      <div className="text-sm font-mono" style={{
                        color: r === 1 ? "#1a7f37" : r != null && r < 0.7 ? "#cf222e" : "#bf8700" }}>
                        {r != null ? `${Math.round(r * 100)}%` : "—"}
                      </div>
                    )}
                  </div>
                  {!run.escalated && (
                    <div className="flex gap-1 mt-2 mb-2">
                      {needs.map((n) => (
                        <span key={n.need_id} className={highlight && highlight !== n.need_id ? "opacity-20" : ""}>
                          <StatusDot status={statuses[n.need_id]} />
                        </span>
                      ))}
                    </div>
                  )}
                  <AgreementCard run={run} highlightNeed={highlight} dimUnhighlighted />
                  {!run.escalated && (
                    <div className={`mt-2 text-[12px] font-medium ${loss > 0 ? "text-lost" : "text-preserved"}`}>
                      {loss > 0 ? `⚠ ${loss} need${loss > 1 ? "s" : ""} silently dropped`
                                : "✓ all needs preserved"}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-4 flex items-center gap-6 text-sm">
            <span className="text-neutral-500">Silent loss:</span>
            {order.map((l) => {
              const run = conditions[l];
              const val = run.no_run ? "–" : run.escalated ? "esc" : silentLoss(run);
              return (
                <span key={l} className="font-mono">
                  {l} <b style={{ color: !run.no_run && !run.escalated && silentLoss(run) > 0 ? "#cf222e" : "#1a7f37" }}>
                    {val}
                  </b>
                </span>
              );
            })}
          </div>

          {highlight && (
            <p className="mt-3 text-[13px] text-neutral-600 max-w-3xl">
              Following <span className="font-mono">{highlight}</span> —{" "}
              {needs.find((n) => n.need_id === highlight)?.verbatim} — across the four
              agreements. Where a column is dimmed, no term addresses it: the need is present
              in the residents&apos; words but absent from the compromise.
            </p>
          )}
        </>
      )}

      {!conditions && !loading && (
        <p className="text-sm text-neutral-500 max-w-2xl">
          Pick a scenario and run. Baseline conditions keep the loud boundaries and silently
          drop a low-salience need; RoomBridge&apos;s audit catches the loss and its revision
          step recovers it.
        </p>
      )}
    </div>
  );
}
