"""Case-aware reconstruction of an original surface from a reverse record.

Pure: declension via the suffix-table inflection module, no Redis. The facade
feeds it the stored reverse record (and, for the cached path, the forms map).
"""

from __future__ import annotations

from ..pseudonym_generation.inflection import classify, decline

_NAME_TYPES = frozenset({"PERSON", "LOCATION"})


class OriginalSurfaceRestorer:
    @staticmethod
    def titlecase(lemma: str) -> str:
        return " ".join(word[:1].upper() + word[1:] for word in lemma.split())

    def render_case(self, fake_base: str, forms: dict | None, case: str | None) -> str:
        """The fake's surface for ``case`` (falls back to the nominative base)."""
        if not case or case == "nom" or not forms:
            return fake_base

        return forms.get(case, fake_base)

    def restore_surface(self, reverse_record: dict) -> str:
        original_base = reverse_record["orig_base"]

        if reverse_record.get("exact"):
            return original_base  # exact surface captured at substitution time
        case = reverse_record.get("case")

        if reverse_record["entity_type"] in _NAME_TYPES and case and case != "nom":
            kind = "city" if reverse_record["entity_type"] == "LOCATION" else "person"

            return " ".join(
                decline(token, classify(token, None, kind=kind), case)
                for token in original_base.split()
            )

        return original_base
