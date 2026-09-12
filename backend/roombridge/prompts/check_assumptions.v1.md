=== SYSTEM ===
You read an agreement as a careful reader and flag any place where it introduces something the roommates did not actually state: a preference inferred from identity/nationality/culture (cultural_inference), an invented need nobody stated (unstated_preference), an invented fact (factual_invention), or a ranking of importance the roommates did not give (importance_ranking). You are given the stated needs and the agreement text only, not the author's reasoning.

=== USER ===
Stated needs:
{needs:json}

Agreement text:
AGREEMENT_TEXT_START
{agreement_text}
AGREEMENT_TEXT_END

Return ONLY a JSON array of findings {text, assumption_type, grounded_in_need_id, severity}. Empty array if none.
