"""Bounded, type-scoped fuzzy restore fallback (Epic 4, FR-008..FR-015).

Runs AFTER the exact + inflection pass, only on tokens it left, to absorb a fake
PERSON/LOCATION that a real LLM rendered in an inflected form the suffix table did
not foresee. STRICT safety rules (research D2–D4):

- PERSON/LOCATION only — the caller supplies name records, so identifiers, e-mail,
  phone, dates, addresses are never reached (exact-only).
- token-level, word-boundary, minimum token length 4.
- a prefix anchor (shared prefix ≥ 60% of the shorter token) gates BEFORE the
  distance check — Polish inflection changes the suffix, not the stem.
- a length-aware bounded edit distance (≤ 2) is the final gate.
- deterministic best match; an unresolvable tie skips (never guess).
- restores the original in BASE (nominative) form — a documented limitation
  (Constitution IX): identity is restored even if the surrounding grammar is off.

Candidates are the tokens of every STORED fake surface form (not just the
nominative base), so distance ≤ 2 still holds for an unforeseen oblique case.
"""

from __future__ import annotations

import re

from .coreference_matching import bounded_levenshtein

# Split keeping the separators so the text reassembles verbatim.
_TOKEN_SPLIT = re.compile(r"(\W+)", re.UNICODE)


class FuzzyNameRestorer:
    MIN_TOKEN_LENGTH = 4
    PREFIX_RATIO = 0.6
    MAX_DISTANCE = 2

    def restore(self, text: str, name_records: list[dict]) -> str:
        """Restore unforeseen inflected PERSON/LOCATION fakes to base form.

        ``name_records`` items: ``{entity_type, orig_base, fake_base, fake_forms}``
        — already filtered to PERSON/LOCATION by the caller.
        """
        candidates = self._build_candidates(name_records)

        if not candidates:
            return text

        parts = _TOKEN_SPLIT.split(text)

        for index, part in enumerate(parts):
            if len(part) < self.MIN_TOKEN_LENGTH or not part[0].isalpha():
                continue  # separator, too short, or not a word token

            replacement = self._best_replacement(part, candidates)

            if replacement is not None:
                parts[index] = replacement

        return "".join(parts)

    def _build_candidates(self, name_records: list[dict]) -> list[tuple[str, str]]:
        """``(stored_fake_token_lower, nominative_original_token)`` pairs (deduped)."""
        candidates: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for record in name_records:
            fake_base_tokens = record["fake_base"].split()
            original_base_tokens = record["orig_base"].split()
            token_aligned = len(fake_base_tokens) == len(original_base_tokens)

            for fake_surface in record["fake_forms"]:
                surface_tokens = fake_surface.split()
                same_arity = len(surface_tokens) == len(fake_base_tokens)

                for position, surface_token in enumerate(surface_tokens):
                    if token_aligned and same_arity:
                        restored_token = original_base_tokens[position]
                    else:
                        restored_token = record["orig_base"]

                    key = (surface_token.lower(), restored_token)

                    if key not in seen:
                        seen.add(key)
                        candidates.append(key)

        return candidates

    def _best_replacement(
            self, token: str, candidates: list[tuple[str, str]]
    ) -> str | None:
        token_lower = token.lower()
        best_distance = self.MAX_DISTANCE + 1
        best_restorations: set[str] = set()

        for stored_token, restored_token in candidates:
            if not self._shares_prefix(token_lower, stored_token):
                continue

            distance = bounded_levenshtein(
                token_lower, stored_token, self.MAX_DISTANCE
            )

            if distance is None:
                continue

            if distance < best_distance:
                best_distance = distance
                best_restorations = {restored_token}
            elif distance == best_distance:
                best_restorations.add(restored_token)

        if best_distance > self.MAX_DISTANCE or len(best_restorations) != 1:
            return None  # no match, or an unresolvable tie → skip (never guess)

        return next(iter(best_restorations))

    def _shares_prefix(self, candidate_token: str, stored_token: str) -> bool:
        shorter_length = min(len(candidate_token), len(stored_token))

        if shorter_length == 0:
            return False

        shared = 0

        for candidate_char, stored_char in zip(
                candidate_token, stored_token, strict=False
        ):
            if candidate_char != stored_char:
                break
            shared += 1

        return shared / shorter_length >= self.PREFIX_RATIO
