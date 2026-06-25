#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Testowanie i zapewnianie jakości <sec:impl-testy>

#todo[
  Sekcja (krótka): przyjęte podejście do testowania implementacji — testy jednostkowe i regresyjne
  uruchamiane bez dostępu do sieci (`fakeredis`, mockowane SDK dostawców, adapter `EchoProvider`);
  determinizm dzięki ziarnu; `pytest` / `pytest-asyncio`; pokrycie kodu; kontrakt regresyjny
  (zamrożony format danych „na drucie"). Wyraźne rozgraniczenie: są to testy implementacji, a~nie
  ewaluacja skuteczności pseudonimizacji, której poświęcono rozdz. @ch:ewaluacja. Źródła: dok.
  pytest, wzorce testów (Meszaros), fakeredis.
]
