class PolishBankAccountRecognizer(ChecksumPatternRecognizer):
    ENTITY = "POLISH_BANK_ACCOUNT"
    PATTERNS = [
        # z przedrostkiem PL lub bez, 26 cyfr pod rząd
        Pattern("nrb_plain", r"\b(?:PL)?\d{26}\b", S_INVALID),
        # zapis pogrupowany 2+4×6, opcjonalny przedrostek PL
        Pattern("nrb_spaced", r"\b(?:PL[ ]?)?\d{2}(?:[ ]\d{4}){6}\b", S_INVALID),
    ]
    CONTEXT = ["rachunek", "konto", "iban", "nr"]

    def __init__(self) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=self.PATTERNS,
            context=self.CONTEXT,
            supported_language="pl",
            name="PolishBankAccountRecognizer",
        )

    def validate_checksum(self, normalized: str) -> tuple[bool, dict]:
        fmt = "IBAN" if normalized.upper().startswith("PL") else "NRB"
        digits = digits_only(normalized)
        valid = nrb_is_valid(digits)
        return valid, {"format": fmt, "normalized": digits, "mod97_valid": valid}
