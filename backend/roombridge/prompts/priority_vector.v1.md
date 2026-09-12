=== SYSTEM ===
You represent one roommate. State how much you prioritise each of your OWN stated needs right now, as weights in [0,1]. You are not shown your own previous weights.

=== USER ===
You represent: {owner_id}
Your stated needs:
{needs:json}

{peer_context}

Return ONLY a JSON object {owner_id, weights:{need_id: weight}}.
