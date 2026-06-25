#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Integracja z dostawcami modeli językowych <sec:dostawcy-llm>

#todo[
  Projekt warstwy komunikacji z~modelami: port dostawcy (jednolity interfejs) + wymienne adaptery
  (lokalny i~hostowani dostawcy); router modeli wybierający dostawcę per żądanie (np. po prefiksie
  modelu); realizacja niezależności od dostawcy (nowy dostawca = adapter + konfiguracja, bez zmian
  potoku); synchroniczność (brak streamingu); projektowa taksonomia błędów dostawcy. Gwarancja:
  do~każdego dostawcy trafiają wyłącznie dane syntetyczne. Opcjonalny diagram port + adaptery +
  router (rys:dostawcy).
]
