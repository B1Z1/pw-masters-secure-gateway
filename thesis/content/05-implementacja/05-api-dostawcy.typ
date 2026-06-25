#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Warstwa API i integracja z dostawcami modeli <sec:impl-api>

#todo[
  Sekcja: implementacja warstwy API w FastAPI; endpoint `/v1/chat/completions` zgodny z API OpenAI;
  orkiestracja potoku (`AnonymizationPipeline.run_inbound`: pseudonimizacja całej historii rozmowy →
  router → przywrócenie danych); realizacja wzorca portów i adapterów (interfejs `LLMProvider`,
  adaptery OpenAI / Anthropic / Ollama, adapter `EchoProvider` na potrzeby testów); router modeli
  (`LLMRouter`) kierujący żądania na podstawie prefiksu identyfikatora modelu; taksonomia błędów
  odwzorowana na kody HTTP; brama dostępności Redis (503) i trasy z niej zwolnione. Figura C (cykl
  życia żądania) + listing z aplikacji (port / router). Źródła: @Nunkesser2022 (porty i adaptery),
  @Wu2026 (kierowanie żądań), dok. zgodności z API OpenAI.
]
