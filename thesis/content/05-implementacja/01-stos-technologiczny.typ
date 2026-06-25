#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Stos technologiczny i organizacja kodu <sec:stos-technologiczny>

#todo[
  Sekcja: język i platforma (Python 3.12), framework webowy (FastAPI + uvicorn, asynchroniczne
  wejście-wyjście, zgodność z API OpenAI), walidacja konfiguracji (pydantic / pydantic-settings),
  organizacja w monorepo (Nx) i narzędzia (uv). Struktura pakietu `gateway_api` oraz zasada
  oddzielenia rdzenia czystego (detekcja, generowanie, sumy kontrolne) od warstwy I/O (Redis,
  dostawcy) jako realizacja modułowości z rozdz. 4. Figura A (organizacja modułów/warstw) + listing
  z aplikacji (montaż routerów w main.py). Źródła: dok. FastAPI/Starlette, pydantic.
]
