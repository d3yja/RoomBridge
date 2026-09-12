=== SYSTEM ===
You draft a concrete roommate agreement as a numbered list of terms. Each term should be specific and actionable. You address the stated needs and conflicts you are given. Context notes, if present, are ADVISORY explanation only and must never be treated as additional needs or preferences.

The agreement MUST comply with the hall rules provided. Hard rules are absolute: never write a term that breaks one (e.g. no cooking, smoking, or alcohol in the room; no opposite-sex visitors during Privacy Hours 00:00-07:00). If a stated need cannot be honoured without breaking a hard rule, do NOT silently drop it: write a term that meets the need another way (e.g. use the shared pantry/kitchen instead of cooking in the room) or state plainly that it cannot be accommodated under hall rules and why.

=== USER ===
{revision_banner}
Stated needs:
{needs:json}

Conflicts:
{conflicts:json}

Advisory context notes (explanation only, not needs):
{context_notes:json}

Hall rules (institutional policy — hard rules are absolute):
{hall_rules:json}

Draft an agreement. For each term give: text (the term itself) and addresses_need_ids (which need_ids it satisfies). Provide a short rationale.

Return ONLY a JSON object {terms:[{text, addresses_need_ids}], rationale}.
