import Link from "next/link";
import { headers } from "next/headers";

async function getScenarios() {
  const h = headers();
  const host = h.get("host");
  const proto = h.get("x-forwarded-proto") || "http";
  try {
    const res = await fetch(`${proto}://${host}/api/scenarios`, { cache: "no-store" });
    return (await res.json()) as any[];
  } catch { return []; }
}

export default async function Home() {
  const scenarios = await getScenarios();
  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">
        Does an explicit needs-preservation workflow stop AI mediation from silently
        dropping one roommate&apos;s requirement?
      </h1>
      <p className="mt-3 text-[15px] text-neutral-600 max-w-3xl leading-relaxed">
        RoomBridge represents every stated need as a persistent object, generates a
        compromise, then audits that compromise against each original need with an
        independent checker. A plausible agreement can look complete while one person&apos;s
        need has quietly disappeared — the audit is what reveals the loss.
      </p>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link href="/demo" className="block rounded-lg border border-[#e5e2d8] bg-white p-5 hover:shadow-sm transition">
          <div className="text-lg font-semibold">Demo mode →</div>
          <p className="mt-1 text-sm text-neutral-600">
            Run one scenario through all four conditions side by side. Reveal the need that
            three of them silently drop.
          </p>
        </Link>
        <Link href="/workbench" className="block rounded-lg border border-[#e5e2d8] bg-white p-5 hover:shadow-sm transition">
          <div className="text-lg font-semibold">Workbench →</div>
          <p className="mt-1 text-sm text-neutral-600">
            Watch the RoomBridge pipeline run live: needs ledger, mediation, and the
            preservation audit streaming step by step.
          </p>
        </Link>
      </div>

      <h2 className="mt-10 mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Scenarios
      </h2>
      <div className="rounded-lg border border-[#e5e2d8] bg-white divide-y divide-[#f0eee6]">
        {scenarios.map((s) => (
          <div key={s.scenario_id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="font-mono text-[11px] text-neutral-400">{s.scenario_id}</span>
            <span className="text-ink">{s.title}</span>
            {s.should_escalate && (
              <span className="chip bg-red-50 text-lost border border-red-200">escalation</span>
            )}
            <span className="ml-auto text-neutral-400 text-xs">{s.n_participants} people</span>
          </div>
        ))}
        {scenarios.length === 0 && (
          <div className="px-4 py-3 text-sm text-neutral-500">
            No scenarios loaded — is the API running on :8000?
          </div>
        )}
      </div>
    </div>
  );
}
