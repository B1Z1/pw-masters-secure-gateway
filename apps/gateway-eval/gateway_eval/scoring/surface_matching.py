"""Polish surface-form matching helpers shared by the leak audit and restoration
scoring (research D4).

Normalization is NFC + lowercase + whitespace collapse, keeping diacritics (they are
meaningful in Polish). A diacritic-folded variant is offered as a defence-in-depth
backstop. The stem rule strips common Polish inflectional endings so a case-inflected
surface (``Kowalskiego``) is recognized as the same identity as its base (``Kowalski``)
without a full morphological analyzer (Constitution IX — documented simplification).
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_WORD = re.compile(r"\w+", re.UNICODE)

# Longest-first so e.g. "ego" is tried before "go"; covers the common Polish noun /
# adjective case endings seen on names and places.
_INFLECTION_ENDINGS = (
    "ami",
    "ach",
    "owi",
    "ego",
    "emu",
    "ich",
    "ymi",
    "iej",
    "ą",
    "ę",
    "em",
    "om",
    "ie",
    "im",
    "ym",
    "y",
    "i",
    "a",
    "e",
    "u",
    "o",
)

_DIACRITIC_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")

_MIN_STEM_LENGTH = 4


def normalize(text: str) -> str:
    """NFC + lowercase + collapse internal whitespace (diacritics kept)."""
    folded = unicodedata.normalize("NFC", text).lower().strip()
    return _WHITESPACE.sub(" ", folded)


def fold_diacritics(text: str) -> str:
    """Strip Polish diacritics — a secondary, more permissive comparison pass."""
    return normalize(text).translate(_DIACRITIC_MAP)


def tokens(text: str) -> list[str]:
    return _WORD.findall(text)


def stem(token: str) -> str:
    """Strip one common Polish inflectional ending; never shorten below the floor."""
    lowered = normalize(token)
    for ending in _INFLECTION_ENDINGS:
        if lowered.endswith(ending) and len(lowered) - len(ending) >= _MIN_STEM_LENGTH:
            return lowered[: -len(ending)]
    return lowered


def shares_stem(left: str, right: str) -> bool:
    """True when two surfaces share a stem of at least the minimum length."""
    left_stem = stem(left)
    right_stem = stem(right)
    if len(left_stem) < _MIN_STEM_LENGTH or len(right_stem) < _MIN_STEM_LENGTH:
        return normalize(left) == normalize(right)
    shorter, longer = sorted((left_stem, right_stem), key=len)
    return longer.startswith(shorter)


def levenshtein_ratio(left: str, right: str) -> float:
    """Similarity in [0, 1] from edit distance on normalized surfaces."""
    source = normalize(left)
    target = normalize(right)
    if not source and not target:
        return 1.0
    distance = _edit_distance(source, target)
    longest = max(len(source), len(target))
    return 1.0 - distance / longest if longest else 1.0


def _edit_distance(source: str, target: str) -> int:
    previous_row = list(range(len(target) + 1))
    for source_index, source_char in enumerate(source, start=1):
        current_row = [source_index]
        for target_index, target_char in enumerate(target, start=1):
            insertion = current_row[target_index - 1] + 1
            deletion = previous_row[target_index] + 1
            substitution = previous_row[target_index - 1] + (source_char != target_char)
            current_row.append(min(insertion, deletion, substitution))
        previous_row = current_row
    return previous_row[-1]
