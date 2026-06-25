#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Magazyn odwracalnych mapowań i szyfrowanie <sec:impl-magazyn>

#todo[
  Sekcja: implementacja magazynu na bazie Redis (jedna struktura HASH na sesję); schemat pól
  (`fwd:` jako HMAC-SHA256 umożliwiający deterministyczne wyszukanie bez ujawniania oryginału,
  `rev:`, `forms:`, `corefs`, `meta`); szyfrowanie AES-256-GCM wyłącznie danych oryginalnych
  (koperta nonce‖szyfrogram‖znacznik); klucz pobierany ze środowiska i walidowany na starcie
  (fail-fast); resolver koreferencji (zawieranie lematu, podejście zachowawcze); fabryka unikalnych
  zamienników (obsługa kolizji); przywracanie literalne z odmianą lematu jako uzupełnieniem;
  blokada per-sesja (`asyncio.Lock`); przesuwający się TTL. Figura B (schemat HASH sesji + zakres
  szyfrowania) + listing z aplikacji. Źródła: NIST SP 800-38D (GCM), RFC 2104 / Krawczyk (HMAC),
  dok. Redis.
]
