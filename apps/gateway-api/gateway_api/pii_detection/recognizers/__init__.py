"""Recognizer registry assembly (FR-004).

Base recognizers: spaCy NER (PERSON/LOCATION/DATE_TIME via the NKJP label
mapping in nlp.py), Email, and Phone (PL region). Everything Poland-specific is
a custom recognizer. ``ALL_ENTITIES`` is the closed set the engine surfaces
(ORGANIZATION/NRP from spaCy are intentionally excluded).
"""

from __future__ import annotations

import phonenumbers
from presidio_analyzer import RecognizerRegistry
from presidio_analyzer.predefined_recognizers import (
    EmailRecognizer,
    PhoneRecognizer,
    SpacyRecognizer,
)

from .address import PolishAddressRecognizer
from .bank_account import PolishBankAccountRecognizer
from .date_pl import DateRecognizer
from .nip import NipRecognizer
from .pesel import PeselRecognizer
from .regon import RegonRecognizer

ALL_ENTITIES = (
    "PERSON",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "DATE_TIME",
    "PESEL",
    "NIP",
    "REGON",
    "POLISH_BANK_ACCOUNT",
    "POLISH_ADDRESS",
)


def build_registry() -> RecognizerRegistry:
    """Assemble the recognizer registry for Polish detection."""
    registry = RecognizerRegistry(supported_languages=["pl"])
    # Base (model + generic patterns), all bound to Polish.
    registry.add_recognizer(SpacyRecognizer(supported_language="pl"))
    registry.add_recognizer(EmailRecognizer(supported_language="pl"))
    registry.add_recognizer(
        PhoneRecognizer(
            supported_language="pl",
            supported_regions=["PL"],
            context=["tel", "telefon", "kom"],
            # Recall over precision (Constitution II): accept "possible" numbers, not
            # only phonenumbers-"valid" ones, so realistic-but-unassigned Polish
            # formats (e.g. the +48 702/809/802 ranges) are masked instead of leaking.
            leniency=phonenumbers.Leniency.POSSIBLE,
        )
    )
    # Custom Polish recognizers (one module each).
    for recognizer in (
        DateRecognizer(),
        PeselRecognizer(),
        NipRecognizer(),
        RegonRecognizer(),
        PolishBankAccountRecognizer(),
        PolishAddressRecognizer(),
    ):
        registry.add_recognizer(recognizer)
    return registry
