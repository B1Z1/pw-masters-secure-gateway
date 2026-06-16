"""Deterministic, explainable score bands (data-model §5, research D6).

Pipeline: ``base pattern score -> checksum adjustment -> + context bonus
(LemmaContextAwareEnhancer) -> clamp to [0, SCORE_CEILING]``. The numbers below
are the *rule set* (FR-015/FR-016) — not per-value literals — so the thesis can
describe scoring as a method.

Resulting bands (with ``context_similarity_factor = 0.20``):

| Situation                                   | pre-context | + label |
|---------------------------------------------|-------------|---------|
| national-ID / bank — checksum **valid**     | 0.80        | 0.99    |
| national-ID / bank — checksum **invalid**   | 0.30        | 0.50    |
| address with street                         | 0.60        | 0.80    |
| address without street (postal code + city) | 0.40        | 0.60    |
| date — numeric                              | 0.60        | 0.80    |
| date — worded                               | 0.55        | 0.75    |
| PERSON / LOCATION (spaCy)                    | 0.85        | 0.99    |

EMAIL_ADDRESS / PHONE_NUMBER keep Presidio's own fixed default pattern scores
(deterministic), documented at runtime in the analyzer's decision process.
"""

from __future__ import annotations

# Checksum-bearing recognizers (PESEL/NIP/REGON/bank).
S_VALID = 0.80  # checksum passed
S_INVALID = 0.30  # checksum failed — kept (not dropped), low confidence (FR-014)

# Non-checksum custom recognizers.
S_ADDRESS_WITH_STREET = 0.60
S_ADDRESS_NO_STREET = 0.40
S_DATE_NUMERIC = 0.60
S_DATE_WORDED = 0.55

# Context enhancer (LemmaContextAwareEnhancer) — a *fixed* bonus when a context
# label sits near the entity. ``min`` floor disabled (0.0) so a label near a
# bad-checksum value raises it only modestly, keeping bands monotonic (D6).
CONTEXT_SIMILARITY_FACTOR = 0.20
CONTEXT_MIN_SCORE = 0.0

# Reserve 1.0 so a configured threshold of 1.0 reliably disables a type (FR-022)
# and "valid + labelled" lands at ~0.99.
SCORE_CEILING = 0.99


def clamp_score(score: float) -> float:
    """Clamp a raw score into ``[0.0, SCORE_CEILING]``."""
    if score < 0.0:
        return 0.0
    if score > SCORE_CEILING:
        return SCORE_CEILING
    return score
