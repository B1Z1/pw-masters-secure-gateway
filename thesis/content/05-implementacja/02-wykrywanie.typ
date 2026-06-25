#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Wykrywanie danych osobowych <sec:impl-wykrywanie>

#todo[
  Sekcja: implementacja modułu wykrywania na bazie Presidio (`AnalyzerEngine`) i spaCy
  (`pl_core_news_lg`); mapowanie etykiet NKJP→Presidio; własne rozpoznawacze identyfikatorów
  (PESEL, NIP, REGON, rachunek, adres, data) oparte na wyrażeniach regularnych i sumach kontrolnych
  (suma steruje oceną, nie odrzuca); progi per-typ w pliku YAML (przewaga czułości nad precyzją,
  przeładowanie na żywo); deterministyczne rozwiązywanie nakładania się encji; DTO `DetectedEntity`
  niezależne od biblioteki; jednokrotne ładowanie modelu w wątku tła. Listing z aplikacji
  (rozpoznawacz z sumą kontrolną / DTO). Źródła: @presidio, @spacy, źródło na strukturę PESEL.
]
