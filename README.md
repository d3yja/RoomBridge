# RoomBridge

A research prototype that tests one question:

> When an LLM mediates between roommates with conflicting needs, it can produce a
> *plausible* agreement while one person's stated requirement has silently vanished.
> Does an explicit **needs-preservation workflow** — needs as persistent objects,
> agreements audited against those objects by an independent checker — detect and reduce
> that loss, compared with ordinary LLM / multi-agent deliberation?

It is an **evaluation instrument**, not a product. Everything serves one of three jobs:
make the loss *happen* under baseline conditions, make it *measurable*, and make it
*visible in 30 seconds* at a symposium demo.

## The four conditions

The same scenario runs through all four; the comparison is the experiment.

|   | Condition                         | What its generator sees                                                                                   |
| - | --------------------------------- | --------------------------------------------------------------------------------------------------------- |
| A | Generic LLM                       | raw statements only                                                                                       |
| B | Context-informed                  | statements + an explanatory context block                                                                 |
| C | Ordinary multi-agent deliberation | perspective agents + mediator, multi-round, no needs objects, no audit loop                               |
| D | **RoomBridge**              | needs → conflicts → context → K candidates → select →**independent audit** → bounded revision |

Two invariants make the comparison valid:

1. the **gold need set is fixed per scenario**, outside the condition, so all four are audited against the same needs;
2. the **auditor is identical** for all four and sees only `(need, agreement_text)` — never the mediator's rationale, the transcript, or which condition produced the agreement.

The audit is *measurement infrastructure*, not D's advantage. D's advantage comes from the
revision loop the audit feeds.

## Quick start

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn roombridge.api.app:app --port 8000        # loads scenarios + DB on startup

# Frontend (Node 18+), in another terminal
cd frontend
npm install
npm run dev                                        # http://localhost:3000
```

Everything runs on the **mock provider** by default — the full pipeline, demo, and tests
work offline at zero API cost. To use real models, put an OpenRouter key in a gitignored
`.env` (see `backend/.env.example`) and pass `--provider openrouter`.

## Headless experiment harness

```bash
cd backend && source .venv/bin/activate
python -m roombridge.runner --provider mock                 # scenario x condition sweep, resumable
python -m roombridge.runner --scenario sc_001_quiet_vs_social --conditions A,D --seeds 1,2,3
python -m roombridge.export --tag run1                      # -> data/exports/{runs,metrics}_run1.{jsonl,csv}
pytest                                                      # structural safeguard tests
```

## What the reference repositories contributed

- **MultiAgent-Diversity** (`evaluate.py`): `compute_pairwise` and `compute_mst_span` are
  adapted near-verbatim for *candidate spread* (metrics/pairwise.py, structural.py); the
  multi-round social-exposure shape (`sec6_*`) informs *position drift*; the resumable
  JSONL runner idiom (`sec5_infer_api.py`) informs `runner.py`.
- **CultureSPA** (`data_process/3.CRQPC.py`): the culture-aware / culture-unaware
  *differential* is inverted into a stereotype tripwire (pipeline/assumptions.py).
- **Explicitly rejected**: nationality-persona prompting (`sec5_infer_api.py:138`,
  `utils.py:35`), Cross-Culture Thinking, population priors as preference priors, and the
  Value Alignment metric — all conflict with the research question. A unit test
  (`tests/test_banned_prompts.py`) fails the build if a persona prompt reappears.

## Metrics (see plan §7 for the honest adaptation notes)

- **Needs-Retention Rate (NRR)**, per-person NRR, **Retention Asymmetry**, **Silent Loss
  Rate** — primary, derived from MAD's construction but reported under their own names.
- **Candidate Spread** (pairwise + MST) — adapted from MAD; secondary; meaningful only for K≥3.
- **Position Drift** — adapted from MAD's ΔD; does a perspective agent abandon its principal under peer exposure?
- **`gold_status_match`** — match against the scenario's pre-registered *expected baseline*
  statuses. This is phenomenon-confirmation, **not** pure auditor accuracy (which needs
  per-agreement human labels — the held-out κ described in the plan). `gold_audit` encodes
  what a naive agreement is predicted to drop, so D is *expected* to diverge from it.

## Safeguards against stereotype / hallucination (plan §10)

- Culture is never a field the generator can reach (`PromptContext` allowlist).
- `ContextNote` has no preference field and requires a `need_id` — it structurally cannot
  originate a preference.
- A deterministic rule layer flags demographic→preference constructions with no false
  negatives on the blatant form.
- The auditor must ground preserved/partial verdicts in a **verbatim quote** from the
  agreement, or the status is forced down — the anti-rationalization guard.

## Privacy

Synthetic data by default, local-only, no auth, no telemetry. The SQLite DB and exports are
gitignored. Live booth entry is possible but flagged non-synthetic and excluded from exports.

## Layout

```
backend/roombridge/   config, domain (models/contracts/enums/db), providers, prompts,
                      pipeline (steps + audit + rules + safety), conditions, metrics,
                      scenarios, runner.py, export.py, api/
frontend/             Next.js App Router: /demo (four-column compare), /workbench (live SSE)
data/                 runs.db + exports/ (gitignored)
```
