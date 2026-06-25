#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Konfiguracja, uruchomienie i obserwowalność <sec:impl-srodowisko>

#todo[
  Sekcja: konfiguracja przez zmienne środowiskowe (pydantic-settings / `.env`, metodyka
  twelve-factor); konteneryzacja i uruchomienie przez Docker Compose (redis + gateway-api,
  opcjonalny dodatek z modelem Ollama); odporny start (działanie bez Redis, brama 503);
  strukturalne logowanie żądań w formacie JSON bez danych osobowych (privacy by design, reuse
  @Hoepman2014); metryki czasowe zasilające ewaluację w rozdz. 6. Listing z aplikacji
  (`Settings` / fragment docker-compose / middleware logujące). Źródła: twelve-factor (Wiggins),
  konteneryzacja, structured logging.
]
