#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

#let codefig(file, long, short) = figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read(file)))),
  ),
  caption: flex-caption(long, short),
  kind: image,
)

== Konfiguracja, uruchomienie i obserwowalność <sec:impl-srodowisko>

Działający system wymaga jeszcze określenia sposobu jego konfiguracji, uruchomienia oraz
obserwowania. Całość konfiguracji wczytywana jest jednorazowo przy starcie ze zmiennych
środowiskowych, z~wykorzystaniem biblioteki pydantic-settings. Oddzielenie konfiguracji od kodu
pozwala uruchamiać tę samą aplikację w~różnych środowiskach bez jej modyfikacji, a~dane wrażliwe,
takie jak hasła czy klucze, nie trafiają do repozytorium. Parametry wczytywane są do typowanego
obiektu konfiguracji, co umożliwia ich walidację już na etapie startu. Szczególnie istotny jest
klucz szyfrujący magazyn: jego poprawność sprawdzana jest natychmiast, a~błędna wartość przerywa
uruchomienie, zanim obsłużone zostanie jakiekolwiek żądanie. Realizuje to omawianą wcześniej zasadę
szybkiego zawodzenia (zob. @sec:stos-technologiczny). Obiekt konfiguracji wraz z~tą walidacją
przedstawiono na rysunku @rys:settings.

#codefig(
  "listings/config_settings.py",
  [Obiekt konfiguracji wczytywany ze zmiennych środowiskowych, z~walidacją klucza szyfrującego przerywającą start przy błędnej wartości (wybrane pola).],
  [Konfiguracja ze zmiennych środowiskowych],
) <rys:settings>

System uruchamiany jest w~kontenerach za pomocą narzędzia Docker Compose. Konteneryzacja zapewnia
powtarzalne, przenośne i~odizolowane środowisko uruchomieniowe, łączące wirtualizację na poziomie
systemu operacyjnego z~przenośnością między platformami @Boettiger2014. Podstawowy zestaw usług
obejmuje magazyn sesji Redis oraz właściwą usługę gatewaya, połączone w~wydzielonej sieci kontenerów.
Co istotne dla bezpieczeństwa, Redis nie jest udostępniany na zewnątrz, na hosta, lecz pozostaje
osiągalny wyłącznie wewnątrz tej sieci, dzięki czemu zaszyfrowany magazyn mapowań nie jest dostępny
spoza infrastruktury. Na zewnątrz wystawiony jest jedynie port usługi gatewaya. Sam model językowy
nie należy do podstawowego zestawu, zgodnie z~przyjętą niezależnością od dostawcy
(zob. @sec:impl-api): model lokalny można dołączyć jako opcjonalny dodatek. Strukturę wdrożenia
zaprezentowano na rysunku @rys:wdrozenie.

#figure(
  diagram(
    spacing: (14mm, 10mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 7pt,
    node((0, 1.1), [Klient], name: <client>),
    node((1.7, 0.6), [`gateway-api`\ #text(size: 0.72em, fill: gray.darken(40%))[port 8000]], name: <api>),
    node((1.7, 1.7), [`redis`\ #text(size: 0.72em, fill: gray.darken(40%))[niepublikowany na hosta]], name: <redis>),
    node(
      enclose: (<api>, <redis>),
      stroke: (paint: gray, dash: "dashed"), inset: 10pt, name: <net>,
    ),
    node((1.7, 2.55), text(size: 0.72em, fill: gray.darken(40%))[sieć kontenerów], stroke: none),
    node((3.5, 0.6), [Model (Ollama)\ #text(size: 0.72em, fill: gray.darken(40%))[opcjonalny dodatek]], name: <ollama>),
    edge(<client>, <api>, "->", [#text(size: 0.78em)[:8000]]),
    edge(<api>, <redis>, "->"),
    edge(<api>, <ollama>, "-->", [#text(size: 0.76em)[opcjonalnie]]),
  ),
  caption: flex-caption(
    [Wdrożenie przez Docker Compose: kontenery `gateway-api` i~`redis` w~sieci wewnętrznej, z~Redisem niepublikowanym na hosta oraz opcjonalnym modelem lokalnym.],
    [Wdrożenie systemu w~kontenerach],
  ),
) <rys:wdrozenie>

Uruchomienie zaprojektowano jako odporne na brak zależności. Usługa startuje nawet wtedy, gdy magazyn
sesji jest niedostępny, przy czym do czasu jego przywrócenia każde żądanie wymagające stanu kończy
się odpowiedzią o~kodzie 503 (zob. @sec:stos-technologiczny). Stan systemu można sprawdzić endpointem
`/health`, który zawsze zwraca kod 200 i~raportuje dostępność poszczególnych zależności, w~tym
magazynu sesji oraz modelu rozpoznającego encje. Gdy którakolwiek z~nich jest niedostępna, ogólny
stan opisywany jest jako obniżony. Endpoint ten pokazano na rysunku @rys:health.

#codefig(
  "listings/health.py",
  [Endpoint `/health` zawsze zwraca kod 200 i~raportuje status zależności, a~stan ogólny jest obniżony, gdy którakolwiek z~nich jest niedostępna.],
  [Endpoint kontroli stanu],
) <rys:health>

Obserwowalność systemu opiera się na strukturalnym logowaniu zdarzeń. Dla każdego żądania emitowana
jest dokładnie jedna linia dziennika w~formacie JSON, zawierająca metadane operacji: znacznik czasu,
identyfikator sesji, wywołany endpoint, użytego dostawcę i~model, liczbę wykrytych encji według typu
oraz pomiary czasu poszczególnych etapów. Zgodnie z~zasadą minimalizacji danych w~dzienniku nie
zapisuje się żadnych danych osobowych ani treści wiadomości, a~jako endpoint rejestrowany jest
jedynie wzorzec ścieżki, bez wartości jej parametrów @Hoepman2014. Sam identyfikator sesji jest
losowym ciągiem, niezwiązanym z~tożsamością użytkownika. Sposób tworzenia linii dziennika
przedstawiono na rysunku @rys:log.

#codefig(
  "listings/log_emit.py",
  [Tworzenie strukturalnej linii dziennika: wyłącznie metadane operacji, bez treści wiadomości i~danych osobowych.],
  [Strukturalne logowanie żądania],
) <rys:log>

Pomiary czasu gromadzone dla każdego żądania, obejmujące między innymi etap wykrywania, generowania
danych zastępczych, zapisu do magazynu oraz komunikacji z~modelem, posłużą również do oceny
wydajności systemu w~rozdziale @ch:ewaluacja.

Omówione rozwiązania domykają opis implementacji systemu od strony jego konfiguracji oraz działania
w~środowisku uruchomieniowym. Pozostaje przedstawić sposób, w~jaki poprawność tej implementacji była
weryfikowana, czemu poświęcono ostatni podrozdział.
