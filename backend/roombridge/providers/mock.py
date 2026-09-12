"""Deterministic mock provider: runs the entire pipeline with zero API cost.

It is not a stub that returns fixed strings. It does genuine, deterministic work keyed
off the step marker and the structured content in the prompt, so that:
  * baseline agreements (no needs ledger, or first-pass generation) silently drop
    low-salience, non-boundary needs -- the phenomenon RoomBridge studies;
  * the auditor genuinely grounds each verdict in a quote from the agreement text, so
    a dropped need audits to not_addressed with no evidence quote;
  * condition D's revision loop, given the failing need ids, recovers them.

This lets the demo and the safeguard tests run offline and reproducibly.
"""
from __future__ import annotations

import json
import re

from .base import CallResult, Message

_STEP = re.compile(r"ROOMBRIDGE_STEP:\s*(\w+)")
_STOPWORDS = {
    "i", "the", "a", "an", "to", "of", "and", "or", "but", "in", "on", "at", "for", "my",
    "me", "is", "it", "be", "have", "has", "need", "want", "would", "like", "can", "get",
    "because", "so", "that", "this", "with", "from", "am", "are", "do", "when", "during",
}


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _find_blocks(text: str) -> list:
    """Extract every top-level JSON array/object appearing in the prompt."""
    blocks, depth, start, instr, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
            continue
        if ch == '"':
            instr = True
        elif ch in "[{":
            if depth == 0:
                start = i
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0 and start is not None:
                frag = text[start : i + 1]
                try:
                    blocks.append(json.loads(frag))
                except json.JSONDecodeError:
                    pass
                start = None
    return blocks


def _collect_needs(text: str) -> list[dict]:
    needs = []
    for block in _find_blocks(text):
        items = block if isinstance(block, list) else [block]
        for it in items:
            if isinstance(it, dict) and "need_id" in it and ("verbatim" in it or "normalized" in it):
                needs.append(it)
    return needs


def _need_text(n: dict) -> str:
    parts = [n.get("verbatim", ""), n.get("normalized", "")]
    for c in n.get("constraints", []) or []:
        if isinstance(c, dict):
            parts.append(str(c.get("value", "")))
    return " ".join(parts)


def _is_droppable(n: dict) -> bool:
    """Low-salience, non-boundary needs are the ones a plausible compromise silently drops."""
    imp = n.get("stated_importance")
    boundary = n.get("stated_as_boundary", False)
    return (not boundary) and (imp is not None and imp <= 2)


class MockProvider:
    name = "mock"

    def complete_text(
        self, messages: list[Message], *, model: str, seed: int | None, temperature: float
    ) -> CallResult:
        blob = "\n".join(m.get("content", "") for m in messages)
        m = _STEP.search(blob)
        step = m.group(1) if m else "unknown"
        handler = getattr(self, f"_step_{step}", self._step_unknown)
        return CallResult(raw=handler(blob, messages), usage={"mock": True}, model=model)

    # -- individual steps -------------------------------------------------------

    def _step_extract_needs(self, blob, messages):
        # Live mode only: echo any needs already present, else emit one generic need.
        needs = _collect_needs(blob)
        if needs:
            return json.dumps(needs)
        return json.dumps(
            [{"need_id": "need_001", "owner_id": "p_A",
              "verbatim": "(mock) extracted need", "normalized": "mock need",
              "category": "other", "constraints": []}]
        )

    def _step_context_note(self, blob, messages):
        needs = _collect_needs(blob)
        nid = needs[0]["need_id"] if needs else "need_001"
        return json.dumps({
            "need_id": nid,
            "possible_reasons": ["this need may relate to daily routine or study schedule"],
            "communication_considerations": ["confirm the specifics rather than assuming"],
            "confidence": "low",
        })

    def _step_identify_conflicts(self, blob, messages):
        needs = _collect_needs(blob)
        conflicts = []
        # Pair needs from different owners sharing a category => a conflict.
        by_cat: dict[str, list[dict]] = {}
        for n in needs:
            by_cat.setdefault(n.get("category", "other"), []).append(n)
        i = 0
        for cat, group in by_cat.items():
            owners = {g.get("owner_id") for g in group}
            if len(owners) > 1:
                i += 1
                conflicts.append({
                    "conflict_id": f"conf_{i:03d}",
                    "need_ids": [g["need_id"] for g in group],
                    "conflict_type": "schedule" if cat in {"noise", "sleep", "guests"} else "resource",
                    "negotiable": not any(g.get("stated_as_boundary") for g in group),
                    "missing_info": [],
                })
        return json.dumps(conflicts)

    def _step_generate_agreement(self, blob, messages):
        needs = _collect_needs(blob)
        revise = "REVISION" in blob
        failing = set(re.findall(r"need_\d+", blob.split("FAILING_NEED_IDS", 1)[1])) if "FAILING_NEED_IDS" in blob else set()

        if not needs:
            # Conditions A/B/C: no structured ledger, only raw statements. A plausible
            # generic agreement echoes the LOUD, imperatively-stated needs ("I need ...",
            # "have to", "must") and silently drops the soft, low-salience preferences
            # ("I'd like", "I'd prefer", "would be nice") -- the phenomenon under study.
            user_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
            loud = re.compile(r"\b(need|needs|must|have to|has to|can'?t|cannot)\b", re.I)
            soft = re.compile(r"\b(i'?d like|i'?d prefer|would like|would prefer|prefer|"
                              r"would be nice|it'?d be nice|would help|also like|sometimes|"
                              r"now and then|occasionally)\b", re.I)
            terms = []
            for raw in re.split(r"(?<=[.?!])\s+|\n", user_text):
                line = raw.strip(" -\t")
                if len(line) < 12 or ":" in line[:14]:
                    continue
                if soft.search(line):
                    continue  # low-salience preference -> silently dropped
                if re.search(r"context|may relate|explanatory|consideration", line, re.I):
                    continue  # advisory context is explanation, never an agreement term
                if loud.search(line):
                    terms.append({"text": f"The roommates agree: {line}", "addresses_need_ids": []})
            if not terms:
                terms = [{"text": "The roommates agree to be considerate of each other's schedules.",
                          "addresses_need_ids": []}]
            return json.dumps({"terms": terms,
                               "rationale": "General good-roommate advice from the stated concerns."})

        terms = []
        for n in needs:
            keep = True
            if not revise and _is_droppable(n):
                keep = False  # first pass silently drops the low-salience bait need
            if revise and n["need_id"] not in failing and _is_droppable(n):
                # keep previously-dropped only if it is now flagged failing
                keep = n["need_id"] in failing
            if keep or (revise and n["need_id"] in failing):
                cval = ""
                for c in n.get("constraints", []) or []:
                    if isinstance(c, dict) and c.get("value"):
                        cval = c["value"]
                        cval_txt = f" ({c.get('dimension','')}: {cval})"
                        cval = cval_txt
                        break
                summary = n.get("normalized") or n.get("verbatim")
                terms.append({
                    "text": f"The agreement provides for: {summary}{cval if isinstance(cval,str) else ''}.",
                    "addresses_need_ids": [n["need_id"]],
                })
        return json.dumps({
            "terms": terms,
            "rationale": "Addresses boundaries and higher-priority needs; "
                         + ("revised to restore flagged needs." if revise else "balances the schedule."),
        })

    def _step_select_agreement(self, blob, messages):
        return json.dumps({"chosen_index": 0, "reason": "widest need coverage among candidates"})

    def _step_audit_need(self, blob, messages):
        needs = _collect_needs(blob)
        agreement = self._agreement_text(blob)
        need = needs[0] if needs else {"need_id": "need_001", "verbatim": ""}
        nk = _keywords(_need_text(need))
        # Ground the verdict in an actual sentence of the agreement.
        best_line, best_overlap = None, 0
        for line in re.split(r"[\n.]+", agreement):
            ov = len(nk & _keywords(line))
            if ov > best_overlap:
                best_overlap, best_line = ov, line.strip()
        if best_overlap >= 2 and best_line:
            status = "preserved"
            quote = best_line
        elif best_overlap == 1 and best_line:
            status = "partially_preserved"
            quote = best_line
        else:
            status = "not_addressed"
            quote = None
        return json.dumps({
            "status": status,
            "evidence_quote": quote,
            "rationale": f"Keyword overlap {best_overlap} between need and agreement text.",
        })

    def _step_check_assumptions(self, blob, messages):
        return json.dumps([])  # deterministic-rule layer handles the blatant cases

    def _step_assess_escalation(self, blob, messages):
        # Scan ONLY the user-provided statements, never the system instructions (which
        # necessarily name the trigger words and would otherwise self-fire).
        user_text = "\n".join(m.get("content", "") for m in messages if m.get("role") == "user")
        danger = re.search(r"\b(threaten|threat|hurt|harm|kill|weapon|scared|unsafe|afraid|"
                           r"harass|coerc|suicid|violence|violent|blackmail|abuse)\w*",
                           user_text, re.I)
        if danger:
            return json.dumps({
                "escalate": True, "category": "safety",
                "triggering_span": danger.group(0),
                "reason": "Statement suggests a safety concern beyond AI mediation.",
                "not_attempted": ["assigning blame", "proposing an agreement"],
                "suggested_support": "hall tutor / warden / university counselling service",
                "confidence": "high",
            })
        return json.dumps({"escalate": False, "confidence": "low"})

    def _step_priority_vector(self, blob, messages):
        needs = _collect_needs(blob)
        owner = needs[0].get("owner_id", "p_A") if needs else "p_A"
        w = {n["need_id"]: (1.0 if n.get("stated_as_boundary") else 0.5) for n in needs}
        return json.dumps({"owner_id": owner, "weights": w})

    def _step_unknown(self, blob, messages):
        return "{}"

    @staticmethod
    def _agreement_text(blob: str) -> str:
        m = re.search(r"AGREEMENT_TEXT_START(.*?)AGREEMENT_TEXT_END", blob, re.DOTALL)
        return m.group(1).strip() if m else blob
