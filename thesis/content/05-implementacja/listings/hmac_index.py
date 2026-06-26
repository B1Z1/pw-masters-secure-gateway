def mapping_key(entity_type: str, text: str, lemma: str | None = None) -> str:
    """Klucz znormalizowany encji: osoby/miejsca -> lemat, identyfikatory -> same cyfry."""
    if entity_type in _NAME_TYPES:
        return (lemma or text).strip().lower()

    if entity_type in _DIGIT_TYPES:
        return digits_only(text)

    return " ".join(text.split()).casefold()


def fwd_field(key_bytes: bytes, entity_type: str, normalized_key: str) -> str:
    """Nazwa pola indeksu = „fwd:" + HMAC-SHA256(klucz, typ|klucz_znormalizowany)."""
    hmac_digest = hmac.new(
        key_bytes, f"{entity_type}|{normalized_key}".encode(), hashlib.sha256
    ).hexdigest()

    return f"fwd:{hmac_digest}"
