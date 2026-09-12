=== SYSTEM ===
You are a helpful assistant giving roommate advice. Provide a concrete agreement the roommates could adopt, as a numbered list of terms.

=== USER ===
Here is what the roommates said:
{statements}

Propose an agreement as a numbered list of specific terms.
Return ONLY a JSON object {terms:[{text, addresses_need_ids}], rationale}. Leave addresses_need_ids empty.
