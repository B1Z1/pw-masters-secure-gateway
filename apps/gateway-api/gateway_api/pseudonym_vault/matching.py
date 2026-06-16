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
    cset = candidate_lemma.lower().split()
    sset = stored_lemma.lower().split()
    if not cset or not sset:
        return False
    cs, ss = set(cset), set(sset)
    return cs <= ss or ss <= cs


def aligned_fake(candidate_lemma: str, stored_lemma: str, fake_base: str) -> str:
    """Project a shorter mention onto the matching token(s) of the stored fake.

    "Kowalski" against stored ("jan kowalski" → fake "Marek Nowak") → "Nowak".
    Falls back to the whole fake when alignment is not possible.
    """
    stored_tokens = stored_lemma.lower().split()
    fake_tokens = fake_base.split()
    cand_tokens = candidate_lemma.lower().split()
    idxs = [stored_tokens.index(t) for t in cand_tokens if t in stored_tokens]
    picked = [fake_tokens[i] for i in idxs if i < len(fake_tokens)]
    return " ".join(picked) if picked else fake_base


def bounded_levenshtein(a: str, b: str, max_dist: int = 2) -> int | None:
    """Edit distance if ``<= max_dist``, else None (early-exit band)."""
    a, b = a.lower(), b.lower()
    if abs(len(a) - len(b)) > max_dist:
        return None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            val = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(val)
            row_min = min(row_min, val)
        if row_min > max_dist:
            return None
        prev = cur
    return prev[-1] if prev[-1] <= max_dist else None
