#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Stos technologiczny i organizacja kodu <sec:stos-technologiczny>

Realizację zaprojektowanej architektury rozpoczyna dobór technologii oraz ustalenie ogólnej
organizacji kodu. System zaimplementowano w~języku Python w~wersji 3.12. Wybór ten wynika przede
wszystkim z~dostępności dojrzałego ekosystemu narzędzi do przetwarzania języka naturalnego, na
którym opiera się kluczowy dla projektu moduł wykrywania danych osobowych (zob. @sec:impl-wykrywanie).
Pozostałe komponenty, od warstwy sieciowej po szyfrowanie, również mają w~tym ekosystemie
ugruntowane i~aktywnie utrzymywane biblioteki, co pozwoliło ograniczyć całość do jednego środowiska
uruchomieniowego.

Warstwę sieciową zbudowano na frameworku FastAPI, uruchamianym na serwerze uvicorn zgodnym ze
standardem ASGI @fastapi. FastAPI opiera obsługę żądań na asynchronicznym modelu wykonania
(ang. _async/await_), co ma istotne uzasadnienie w~samym charakterze zadania. Gateway jest usługą
ograniczoną operacjami wejścia-wyjścia (ang. _I/O-bound_): podczas obsługi pojedynczego żądania
spędza większość czasu, oczekując na odpowiedź zewnętrznego modelu językowego, a~nie na obliczeniach
lokalnych. W~klasycznym modelu „wątek na żądanie" każde takie oczekiwanie wiązałoby pełny wątek
systemowy, a~przy rosnącej liczbie równoczesnych połączeń narzuty związane z~obsługą wielu wątków,
w~tym przełączanie kontekstu oraz rywalizacja o~blokady, prowadzą do poważnego spadku wydajności
@Welsh2001. Model asynchroniczny, w~którym pojedynczy wątek obsługuje wiele oczekujących żądań,
znacznie lepiej odpowiada profilowi tej usługi. Dodatkowym argumentem za FastAPI była zgodność
udostępnianego interfejsu z~konwencją API OpenAI (zob. @sec:impl-api), która upraszcza integrację po
stronie klienta.

Konfigurację oraz dane wejściowe poddano walidacji opartej na typach, realizowanej biblioteką
pydantic @pydantic. Parametry pochodzące ze środowiska wczytywane są do typowanego obiektu
konfiguracji, a~ich niepoprawność, na przykład nieprawidłowy klucz szyfrujący, jest wykrywana już
przy starcie aplikacji, zanim obsłużone zostanie jakiekolwiek żądanie. Ta strategia szybkiego
zawodzenia (ang. _fail-fast_) jest spójna z~przyjętym wymaganiem bezpieczeństwa: usługa, która nie
jest w~stanie poprawnie chronić danych, nie powinna w~ogóle wystartować (zob. @sec:impl-srodowisko).

Kod zorganizowano w~ramach repozytorium monolitycznego (ang. _monorepo_) zarządzanego narzędziem
Nx, co pozwala utrzymywać usługę backendową wraz z~towarzyszącą jej infrastrukturą w~jednym, spójnie
konfigurowanym środowisku. Sama usługa tworzy pakiet `gateway_api`, którego podział na moduły
odpowiada komponentom architektury z~rozdziału @ch:projekt. Organizację kodu podporządkowano przy
tym jednej nadrzędnej zasadzie, wywodzącej się z~klasycznej reguły ukrywania informacji @Parnas1972,
to jest oddzieleniu logiki czystej od warstwy odpowiedzialnej za wejście i~wyjście. Moduły
realizujące logikę czystą, czyli wykrywanie danych, generowanie wartości zastępczych oraz obliczanie
sum kontrolnych, nie sięgają bezpośrednio do zasobów zewnętrznych, takich jak magazyn danych czy
interfejsy dostawców. Komunikację z~tymi zasobami skupiono w~osobnej warstwie wejścia-wyjścia.
Podział ten pokazano na rysunku @rys:organizacja-kodu.

#figure(
  diagram(
    spacing: (11mm, 9mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 7pt,
    node((1, 0), [Warstwa API\ #text(size: 0.72em, fill: gray.darken(40%))[FastAPI: routery, walidacja, _middleware_]], name: <api>),
    node((1, 1), [Potok anonimizacji\ #text(size: 0.72em, fill: gray.darken(40%))[orkiestracja]], name: <pipe>),
    node((0, 2), [Logika czysta\ #text(size: 0.72em, fill: gray.darken(40%))[wykrywanie · generowanie\ · sumy kontrolne]], name: <core>),
    node((2, 2), [Warstwa wejścia-wyjścia\ #text(size: 0.72em, fill: gray.darken(40%))[magazyn mapowań · dostawcy]], name: <io>),
    node((2, 3), [Redis · API dostawców\ #text(size: 0.72em, fill: gray.darken(40%))[zasoby zewnętrzne]], name: <ext>),
    edge(<api>, <pipe>, "->"),
    edge(<pipe>, <core>, "->"),
    edge(<pipe>, <io>, "->"),
    edge(<io>, <ext>, "->"),
  ),
  caption: flex-caption(
    [Organizacja kodu pakietu `gateway_api`: warstwa API i~potok nad rozdzielonymi warstwami logiki czystej oraz wejścia-wyjścia.],
    [Organizacja kodu systemu],
  ),
) <rys:organizacja-kodu>

Podział na logikę czystą i~warstwę wejścia-wyjścia przynosi dwie korzyści zapowiedziane w~rozdziale
@ch:projekt (zob. @sec:architektura). Po pierwsze, logikę czystą można testować w~izolacji, bez
uruchamiania bazy danych czy łączenia się z~modelem (zob. @sec:impl-testy). Po drugie, ogranicza on
powierzchnię, na której rzeczywiste dane osobowe stykają się z~zasobami zewnętrznymi.

Punktem, w~którym wszystkie moduły łączą się w~działającą aplikację, jest plik główny pakietu. Pełni
on rolę korzenia kompozycji: tworzy obiekt aplikacji FastAPI, dołącza poszczególne routery
odpowiadające obszarom API oraz rejestruje oprogramowanie pośredniczące (ang. _middleware_) wspólne
dla wszystkich tras. Uproszczony fragment tego pliku przedstawiono na rysunku @rys:kompozycja.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", "app = FastAPI(title=\"LLM Anonymization Gateway\", version=\"0.1.0\", lifespan=lifespan)
app.include_router(health_router)
app.include_router(detect_router)
app.include_router(pseudonymize_router)
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(providers_router)


@app.middleware(\"http\")
async def redis_availability_gate(request: Request, call_next):
    if request.url.path in _GATE_EXEMPT_PATHS:
        return await call_next(request)
    if await check_redis() != \"ok\":
        return JSONResponse(status_code=503, content={\"detail\": \"Redis unavailable\"})
    return await call_next(request)


app.add_middleware(RequestLoggingMiddleware)"))),
  ),
  caption: flex-caption(
    [Korzeń kompozycji w~pliku głównym: utworzenie aplikacji, dołączenie routerów i~rejestracja oprogramowania pośredniczącego (fragment).],
    [Korzeń kompozycji aplikacji],
  ),
  kind: image,
) <rys:kompozycja>

Każdy router grupuje trasy jednego obszaru funkcjonalnego, na przykład wykrywanie danych albo obsługę
rozmowy, dzięki czemu warstwa API pozostaje czytelnie podzielona. Z~kolei oprogramowanie pośredniczące
realizuje funkcje przekrojowe, działające jednakowo dla wszystkich żądań, w~tym kontrolę dostępności
magazynu sesji oraz rejestrowanie zdarzeń. Mechanizmy te omówiono szczegółowo w~podrozdziałach
@sec:impl-api oraz @sec:impl-srodowisko.

Tak zorganizowany szkielet aplikacji stanowi ramę dla właściwej logiki pseudonimizacji. Jej pierwszym
ogniwem jest moduł wykrywania danych osobowych, któremu poświęcono kolejny podrozdział.
