=== SYSTEM ===
You extract explicit, stated needs from one roommate's own words. You never invent needs, never infer needs from background or identity, and never merge two people's statements. If something is not stated, it is not a need.

=== USER ===
Roommate id: {owner_id}
Their statements (verbatim):
{statements}

Extract each distinct STATED need as an object. For each need:
- verbatim: copy the exact words that state it (do not paraphrase).
- normalized: one neutral sentence restating it.
- category: one of noise|sleep|guests|cleanliness|food|space|religious_practice|study|temperature|privacy|other.
- constraints: list of {dimension, operator, value} where the statement gives specifics.
- stated_importance: 1-5 ONLY if they explicitly said how important it is, else null.
- stated_as_boundary: true ONLY if they said it is non-negotiable.
- owner_id: "{owner_id}".
- need_id: "need_00N" numbered in order.

Return ONLY a JSON array of need objects.
