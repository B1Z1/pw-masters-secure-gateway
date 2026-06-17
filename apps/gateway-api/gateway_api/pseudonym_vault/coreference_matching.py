"""Coreference + bounded fuzzy matching (research D7/D8). Pure Python.

- ``lemma_overlap``: whole-token containment, scoped to one entity type, for
  PERSON/LOCATION coreference ("Jan Kowalski" ⊃ "Kowalski"; "Anna Kowalska" and
  "Jan Kowalski" share no token → stay distinct).
- ``bounded_levenshtein``: edit distance with an early-exit band, to absorb a
  fake that resurfaces in an unforeseen inflected form on the restore path.
"""

from __future__ import annotations


def lemma_overlap(candidate_lemma: str, stored_lemma: str) -> bool:
    """True if one lemma's whole tokens are a subset of the other's (same name)."""
    candidate_tokens = candidate_lemma.lower().split()
    stored_tokens = stored_lemma.lower().split()

    if not candidate_tokens or not stored_tokens:
        return False

    candidate_set, stored_set = set(candidate_tokens), set(stored_tokens)

    return candidate_set <= stored_set or stored_set <= candidate_set


def aligned_fake(candidate_lemma: str, stored_lemma: str, fake_base: str) -> str | None:
    """Project a shorter mention onto the matching token(s) of the stored fake.

    "Kowalski" against stored ("jan kowalski" → fake "Marek Nowak") → "Nowak".
    Returns ``None`` when no token aligns (e.g. a hyphen-split surname): the caller
    must then mint a fresh DISTINCT fake rather than reuse the full name's fake,
    which would collide and break reversibility.
    """
    stored_tokens = stored_lemma.lower().split()
    fake_tokens = fake_base.split()
    candidate_tokens = candidate_lemma.lower().split()
    matched_indices = [
        stored_tokens.index(token)
        for token in candidate_tokens
        if token in stored_tokens
    ]
    aligned_tokens = [
        fake_tokens[index] for index in matched_indices if index < len(fake_tokens)
    ]

    return " ".join(aligned_tokens) if aligned_tokens else None


def bounded_levenshtein(source: str, target: str, max_distance: int = 2) -> int | None:
    """Edit distance if ``<= max_distance``, else None (early-exit band)."""
    source, target = source.lower(), target.lower()

    if abs(len(source) - len(target)) > max_distance:
        return None

    previous_row = list(range(len(target) + 1))

    for source_index, source_char in enumerate(source, 1):
        current_row = [source_index]
        row_minimum = source_index
        for target_index, target_char in enumerate(target, 1):
            substitution_cost = 0 if source_char == target_char else 1
            edit_distance = min(
                previous_row[target_index] + 1,
                current_row[target_index - 1] + 1,
                previous_row[target_index - 1] + substitution_cost,
            )

            current_row.append(edit_distance)

            row_minimum = min(row_minimum, edit_distance)

        if row_minimum > max_distance:
            return None

        previous_row = current_row

    return previous_row[-1] if previous_row[-1] <= max_distance else None


class CoreferenceResolver:
    """Decide whether a name mention reuses an existing person's fake (research D7).

    Pure: the caller loads coref records from storage and acts on the decision.
    Returns the aligned fake base to reuse, or ``None`` to mint a fresh person
    (0 matches → new; ≥2 distinct matches → ambiguous, also new; an unalignable
    surname → new).
    """

    def resolve(
            self, entity_type: str, normalized_key: str, coref_records: list[dict]
    ) -> str | None:
        matches = [
            record
            for record in coref_records
            if record["entity_type"] == entity_type
               and lemma_overlap(normalized_key, record["lemma"])
        ]
        distinct_fake_bases = {record["fake_base"] for record in matches}

        if len(distinct_fake_bases) != 1:
            return None

        matched = matches[0]

        return aligned_fake(normalized_key, matched["lemma"], matched["fake_base"])
