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

== Warstwa API i integracja z dostawcami modeli <sec:impl-api>

Omówione dotąd komponenty silnika pseudonimizacji spina warstwa API, udostępniająca system jako
usługę sieciową. Głównym jej elementem jest endpoint `/v1/chat/completions`, którego kształt jest
zgodny z~konwencją API OpenAI: żądanie zawiera tablicę komunikatów, z~których każdy ma rolę oraz
treść, a~także opcjonalny identyfikator modelu. Dzięki tej zgodności po stronie klienta można
korzystać z~istniejących narzędzi przeznaczonych dla API OpenAI bez ich modyfikacji. Endpoint nie
jest zwolniony z~bramy dostępności magazynu sesji (zob. @sec:stos-technologiczny): gdy magazyn jest
niedostępny, żądanie kończy się odpowiedzią o~kodzie 503, zanim dojdzie do jakiejkolwiek komunikacji
z~modelem.

Obsługa żądania przebiega według ustalonej sekwencji etapów, przedstawionej na rysunku
@rys:cykl-zadania. Po przejściu bramy oraz walidacji potok pseudonimizacji przetwarza całą historię
rozmowy, a~nie tylko ostatnie zapytanie. Jest to istotne, ponieważ w~trybie konwersacyjnym do modelu
w~każdej turze trafia pełna historia, a~pominięcie wcześniejszych wiadomości pozwoliłoby danym
przywróconym w~poprzedniej turze ponownie opuścić granicę zaufania (zob. @sec:przeplyw). Tak
przygotowane, pozbawione danych rzeczywistych komunikaty trafiają do wybranego dostawcy, a~otrzymana
odpowiedź przechodzi proces odwrotny, w~którym wartości syntetyczne zastępowane są oryginałami.
Komunikacja jest synchroniczna, gdyż przywrócenie wymaga kompletnej odpowiedzi modelu
(zob. @sec:wymagania).

#figure(
  diagram(
    spacing: (10mm, 7mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 6pt,
    node((0, 0), [Żądanie\ #text(size: 0.72em, fill: gray.darken(40%))[`/v1/chat/completions`]], name: <req>),
    node((0, 1), [Brama Redis\ #text(size: 0.72em, fill: gray.darken(40%))[503, gdy niedostępny]], name: <gate>),
    node((0, 2), [Walidacja żądania\ #text(size: 0.72em, fill: gray.darken(40%))[400]], name: <valid>),
    node((0, 3), [Pseudonimizacja\ całej historii], fill: luma(240), name: <pseudo>),
    node((0, 4), [Router → adapter], name: <route>),
    node((0, 5), [Przywrócenie danych], fill: luma(240), name: <restore>),
    node((0, 6), [Odpowiedź], name: <resp>),
    node((2, 4), [Model językowy\ #text(size: 0.72em, fill: gray.darken(40%))[dostawca]], name: <model>),
    edge((1.1, -0.5), (1.1, 6.6), stroke: (dash: "dashed", paint: gray)),
    node((1.1, -0.85), text(size: 0.72em, fill: gray.darken(40%))[granica\ zaufania], stroke: none),
    edge(<req>, <gate>, "->"),
    edge(<gate>, <valid>, "->"),
    edge(<valid>, <pseudo>, "->"),
    edge(<pseudo>, <route>, "->"),
    edge(<route>, <model>, "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[#text(size: 0.76em)[dane syntetyczne]]]),
    edge(<model>, (2, 5), "->"),
    edge((2, 5), <restore>, "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[#text(size: 0.76em)[dane syntetyczne]]]),
    edge(<restore>, <resp>, "->"),
  ),
  caption: flex-caption(
    [Cykl życia żądania `/v1/chat/completions`: brama i~walidacja, pseudonimizacja całej historii, wywołanie dostawcy przez router oraz przywrócenie danych w~odpowiedzi.],
    [Cykl życia żądania czatu],
  ),
) <rys:cykl-zadania>

Komunikację z~dostawcami zaimplementowano zgodnie z~zaprojektowanym wcześniej wzorcem portów
i~adapterów (zob. @sec:dostawcy-llm). Wprowadzony port dostawcy określa jedną operację, to jest wysłanie
tablicy komunikatów i~odebranie odpowiedzi, oraz ujednoliconą reprezentację wyniku i~błędu. Port ten
przedstawiono na rysunku @rys:port.

#codefig(
  "listings/port.py",
  [Port dostawcy: jednolity komunikat, wynik oraz błąd, od których zależą potok i~endpoint zamiast od konkretnego dostawcy.],
  [Port dostawcy modeli językowych],
) <rys:port>

Każdy adapter tłumaczy jednolity interfejs na wywołania konkretnego API. Dla modelu uruchamianego
lokalnie adapter
wysyła żądanie REST za pomocą biblioteki httpx, natomiast dla dostawców hostowanych korzysta z~ich
oficjalnych bibliotek klienckich. Część dostawców wymaga przy tym przekształcenia komunikatów:
adapter Anthropic wydziela treść systemową do osobnego pola oraz scala sąsiednie komunikaty tej samej
roli, co przedstawiono na rysunku @rys:adapter.

#codefig(
  "listings/anthropic_convert.py",
  [Adapter Anthropic: konwersja komunikatów z~kształtu OpenAI na format dostawcy, z~wydzieleniem treści systemowej i~scaleniem sąsiednich tur tej samej roli.],
  [Konwersja komunikatów w~adapterze Anthropic],
) <rys:adapter>

O~wyborze właściwego dostawcy dla danego żądania decyduje router modeli (zob. @sec:dostawcy-llm).
Wyboru dokonuje się na podstawie prefiksu
identyfikatora modelu: nazwy zaczynające się od `gpt-` kierowane są do dostawcy OpenAI, od `claude-`
do dostawcy Anthropic, a~od `ollama/` do modelu lokalnego, przy czym ten ostatni prefiks jest usuwany
przed przekazaniem nazwy dalej. Rejestrację adapterów wraz z~przypisaniem prefiksów przedstawiono na
rysunku @rys:wiring, a~samą logikę wyboru na rysunku @rys:router.

#codefig(
  "listings/wiring.py",
  [Rejestracja dostawców: każdy prefiks identyfikatora modelu wiązany jest z~fabryką budującą odpowiedni adapter.],
  [Rejestracja adapterów dostawców],
) <rys:wiring>

#codefig(
  "listings/router_resolve.py",
  [Logika routera: dopasowanie prefiksu modelu do dostawcy oraz błąd `unknown_model` przy braku dopasowania.],
  [Wybór dostawcy na podstawie prefiksu],
) <rys:router>

Nierozpoznany prefiks traktowany jest jako błąd po stronie
klienta i~kończy się odpowiedzią o~kodzie 400, jeszcze zanim dojdzie do wywołania któregokolwiek
adaptera. Adaptery budowane są leniwie i~zapamiętywane, dzięki czemu brak klucza dostępowego danego
dostawcy ujawnia się dopiero przy pierwszym jego użyciu, a~nie podczas uruchamiania usługi.

Zapowiedzianą w~projekcie wspólną obsługę błędów (zob. @sec:dostawcy-llm) zrealizowano, odwzorowując
typowe sytuacje błędne na ujednoliconą reprezentację błędu, niosącą rodzaj awarii. Rodzaje te tłumaczone są centralnie na
kody odpowiedzi HTTP, co przedstawiono w~tabeli @tab:bledy. Niezależnie od rodzaju błędu odpowiedź
zachowuje identyfikator sesji, aby klient mógł kontynuować rozmowę po ustąpieniu problemu.

#figure(
  table(
    columns: (auto, auto, 1fr),
    align: (left, center, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Rodzaj błędu*], [*Kod HTTP*], [*Przyczyna*]),
    [`unreachable`], [503], [dostawca nieosiągalny],
    [`missing_model`], [503], [model nieznany u~dostawcy],
    [`auth`], [503], [brak lub niepoprawny klucz API],
    [`timeout`], [504], [przekroczony czas odpowiedzi],
    [`rate_limit`], [429], [przekroczony limit zapytań],
    [`unknown_model`], [400], [nierozpoznany prefiks modelu],
  ),
  caption: flex-caption(
    [Odwzorowanie rodzajów błędów dostawcy na kody odpowiedzi HTTP.],
    [Taksonomia błędów dostawcy],
  ),
) <tab:bledy>

Dla zilustrowania całego obiegu rozważmy pojedyncze żądanie zawierające dane osobowe. Odpowiedź
endpointu, w~formacie zgodnym z~API OpenAI i~rozszerzoną o~informacje specyficzne dla systemu,
przedstawiono na rysunku @rys:przyklad. Pole `choices` zawiera odpowiedź modelu z~przywróconymi
danymi oryginalnymi, pole `anonymization_meta` podsumowuje liczbę wykrytych encji oraz czasy etapów,
natomiast pole `input_anonymization` pokazuje, co~w~istocie wytwarza pseudonimizacja: tekst faktycznie
wysłany do modelu, zawierający wyłącznie dane syntetyczne, wraz z~listą dokonanych zamian (każda z~nich
niesie również przesunięcia w~tekście oryginalnym). Dane oryginalne, widoczne w~polach `choices` oraz
`replacements`, trafiają wyłącznie do zaufanego klienta, podczas gdy do modelu wysłano jedynie
pseudonimizowaną treść.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "json", read("listings/chat_response.json")))),
  ),
  caption: flex-caption(
    [Przykładowa odpowiedź endpointu `/v1/chat/completions`: dane oryginalne w~`choices`, a~w~`input_anonymization` tekst wysłany do modelu i~zamiany (skrócony przykład, dane fikcyjne).],
    [Przykładowa odpowiedź endpointu czatu],
  ),
  kind: image,
) <rys:przyklad>

Warstwa API wraz z~routerem dopełnia obraz działającego systemu: od odebrania żądania, przez
pseudonimizację i~komunikację z~wybranym dostawcą, po przywrócenie danych w~odpowiedzi. Pozostaje
omówić sposób konfiguracji, uruchomienia oraz obserwowania tak złożonego systemu, czemu poświęcono
kolejny podrozdział.
