#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Integracja z dostawcami modeli językowych <sec:dostawcy-llm>

Ostatnim elementem projektu jest warstwa odpowiedzialna za przekazanie pseudonimizowanego zapytania
do zewnętrznego modelu językowego. Wymaganie obsługi wielu dostawców (zob. @sec:wymagania) oznacza,
że system powinien współpracować z~różnymi modelami, a~dodanie kolejnego nie powinno wymuszać zmian
w~pozostałych komponentach. Warstwa ta jest więc miejscem, w~którym wprost realizowana jest
niefunkcjonalna własność niezależności od dostawcy.

Rozwiązaniem przyjętym w~projekcie jest wzorzec portów i~adapterów, znany również jako architektura
heksagonalna. Zgodnie z~nim rdzeń aplikacji komunikuje się ze światem zewnętrznym wyłącznie przez
porty, czyli jednolite interfejsy, a~konkretne zależności zewnętrzne realizują wymienne adaptery
@Nunkesser2022. W~projektowanym systemie wprowadzono pojedynczy port dostawcy, definiujący jednolity
sposób wysłania zapytania i~odebrania odpowiedzi, niezależny od tego, z~którym modelem prowadzona
jest komunikacja. Każdy obsługiwany dostawca, zarówno model uruchamiany lokalnie, jak i~dostawcy
hostowani, otrzymuje własny adapter, który tłumaczy ten jednolity interfejs na konkretne wywołania
danego API. Dzięki temu reszta systemu, w~tym potok anonimizacji, nie zależy od żadnego konkretnego
dostawcy, a~dodanie nowego sprowadza się do dostarczenia kolejnego adaptera oraz uzupełnienia
konfiguracji. Jest to bezpośrednie zastosowanie omówionej wcześniej zasady ukrywania informacji
i~modułowości (zob. @sec:architektura).

Ponieważ system obsługuje wielu dostawców jednocześnie, potrzebny jest mechanizm decydujący, do
którego z~nich skierować dane żądanie. Rolę tę pełni router modeli. Kierowanie żądań do modeli (ang.
_LLM routing_) jest uznaną strategią, polegającą na dynamicznym wyborze usługi spośród różnych
dostawców modeli @Wu2026. W~projektowanym rozwiązaniu wyboru dokonuje się na podstawie identyfikatora
modelu wskazanego w~żądaniu, a~router, sam udostępniając ten sam port dostawcy, pozostaje dla reszty
systemu nieodróżnialny od pojedynczego adaptera. Strukturę warstwy dostawców przedstawiono na rysunku
@rys:dostawcy.

#figure(
  diagram(
    spacing: (16mm, 12mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 6pt,
    node((1, 0), [Router modeli\ #text(size: 0.72em, fill: gray.darken(40%))[wybór dostawcy po modelu]], name: <r>),
    node((0, 1.4), [Adapter\ #text(size: 0.72em, fill: gray.darken(40%))[model lokalny]], name: <a1>),
    node((1, 1.4), [Adapter\ #text(size: 0.72em, fill: gray.darken(40%))[dostawca A]], name: <a2>),
    node((2, 1.4), [Adapter\ #text(size: 0.72em, fill: gray.darken(40%))[dostawca B]], name: <a3>),
    node((0, 2.8), [Model lokalny], name: <p1>),
    node((1, 2.8), [Dostawca A], name: <p2>),
    node((2, 2.8), [Dostawca B], name: <p3>),
    edge((-0.55, 2.1), (2.55, 2.1), stroke: (dash: "dashed", paint: gray)),
    node((2.55, 1.7), text(size: 0.72em, fill: gray.darken(40%))[granica\ zaufania], stroke: none),
    edge(<r>, <a1>, "->"),
    edge(<r>, <a2>, "->"),
    edge(<r>, <a3>, "->"),
    edge(<a1>, <p1>, "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[#text(size: 0.78em)[dane syntetyczne]]]),
    edge(<a2>, <p2>, "->"),
    edge(<a3>, <p3>, "->"),
  ),
  caption: flex-caption(
    [Warstwa dostawców: router kieruje żądanie do jednego z~wymiennych adapterów realizujących wspólny port.],
    [Warstwa komunikacji z~dostawcami modeli],
  ),
) <rys:dostawcy>

Niezależnie od wybranego dostawcy obowiązują dwie zasady ustalone wcześniej. Po pierwsze, komunikacja
jest synchroniczna, a~adapter oczekuje na kompletną odpowiedź modelu, co~stanowi warunek późniejszego
przywrócenia danych (zob. @sec:przeplyw). Po drugie, do dowolnego dostawcy trafiają wyłącznie dane
syntetyczne. Warto zauważyć, że wprowadzenie warstwy pośredniej wybierającej dostawcę samo
w~sobie bywa źródłem nowych zagrożeń dla prywatności, ponieważ warstwa taka uzyskuje wgląd
w~kierowane przez nią dane @Wu2026. W~projektowanym systemie ryzyko to nie występuje, gdyż routing
odbywa się już po pseudonimizacji, a~zatem ani router, ani żaden adapter nie operują na danych
rzeczywistych.

Komunikacja z~zewnętrznym dostawcą jest z~natury zawodna, dlatego projekt przewiduje rozróżnienie
typowych sytuacji błędnych, takich jak niedostępność dostawcy, przekroczenie czasu odpowiedzi czy
odrzucenie żądania, oraz ich odwzorowanie na czytelne dla klienta komunikaty. Dzięki jednolitemu
portowi obsługa błędów może być wspólna dla wszystkich dostawców, niezależnie od tego, w~jaki sposób
sygnalizuje je konkretne API.

Przedstawiona warstwa zamyka projekt architektury systemu. Określono wymagania, zarysowano strukturę
komponentów oraz przepływ danych, omówiono strategię generowania danych zastępczych, a~także sposób
komunikacji z~dostawcami modeli. Tak zaprojektowany system stanowi podstawę implementacji, której
poświęcono kolejny rozdział.
