#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Przepływ danych w procesie pseudonimizacji <sec:przeplyw>

Architektura przedstawiona w~poprzednim podrozdziale opisuje statyczną strukturę systemu, nie
pokazuje jednak, w~jaki sposób dane przemieszczają się przez jego komponenty podczas obsługi
pojedynczego żądania. Opis tej dynamiki wygodnie jest oprzeć na perspektywie przepływu danych,
w~której system traktuje się jako zbiór komponentów połączonych przepływami i~analizuje, gdzie dane
przekraczają granice między zaufanymi a~niezaufanymi częściami systemu. Takie zorientowane na
przepływ informacji ujęcie leży u~podstaw metod analizy prywatności @Deng2011, a~w~kontekście
systemów generatywnej sztucznej inteligencji pytanie o~to, jak obsługiwane są przepływy danych
osobowych, nabiera szczególnego znaczenia @Liao2026. Pełny obieg danych w~projektowanym gatewayu,
od zapytania użytkownika po przywróconą odpowiedź, przedstawiono na rysunku @rys:przeplyw.

#figure(
  diagram(
    spacing: (12mm, 9mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 6pt,
    node((0, 0), [Klient], name: <k>),
    node((2, 0), [Gateway], name: <g>),
    node((4, 0), [Model językowy\ #text(size: 0.72em, fill: gray.darken(40%))[dostawca]], name: <m>),
    edge((0, 0.4), (0, 6.5), stroke: (dash: "dotted", paint: gray)),
    edge((2, 0.4), (2, 6.5), stroke: (dash: "dotted", paint: gray)),
    edge((4, 0.4), (4, 6.5), stroke: (dash: "dotted", paint: gray)),
    edge((3, -0.5), (3, 6.8), stroke: (dash: "dashed", paint: gray)),
    node((3, -0.75), text(size: 0.74em, fill: gray.darken(40%))[granica zaufania], stroke: none),
    node((2, 1.7), [#text(size: 0.76em)[wykrywanie\ i~podstawienie PII]], fill: luma(240)),
    node((2, 5.0), [#text(size: 0.76em)[przywrócenie\ danych]], fill: luma(240)),
    edge((0, 1), (2, 1), "->", [#text(size: 0.82em)[1.~dane osobowe]]),
    edge((2, 2.9), (4, 2.9), "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[#text(size: 0.82em)[2.~dane syntetyczne]]]),
    edge((4, 3.9), (2, 3.9), "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[#text(size: 0.82em)[3.~dane syntetyczne]]]),
    edge((2, 6.1), (0, 6.1), "->", [#text(size: 0.82em)[4.~dane oryginalne]]),
  ),
  caption: flex-caption(
    [Sekwencja przepływu danych w~obiegu żądanie–odpowiedź z~podwójnym przekroczeniem granicy zaufania.],
    [Przepływ danych w~obiegu żądanie–odpowiedź],
  ),
) <rys:przeplyw>

Przepływ rozpoczyna się od żądania skierowanego przez klienta do gatewaya. Żądanie zawiera treść
zapytania wraz z~ewentualnymi dołączonymi dokumentami, w~których mogą znajdować się dane osobowe.
Po jego odebraniu potok anonimizacji uruchamia moduł wykrywania, który lokalizuje w~tekście
fragmenty stanowiące dane osobowe. Następnie dla każdego wykrytego fragmentu potok zwraca się do
magazynu mapowań o~odpowiadającą mu wartość syntetyczną. Jeśli dana wystąpiła już wcześniej w~tej
samej sesji, magazyn udostępnia zapamiętany zamiennik, w~przeciwnym razie zleca jego wygenerowanie
modułowi generowania danych zastępczych i~zapisuje nowe powiązanie. W~rezultacie wykryte dane
zostają zastąpione w~treści zapytania, a~odwzorowanie między wartościami oryginalnymi
a~syntetycznymi zostaje utrwalone w~magazynie.

Tak przygotowane zapytanie, pozbawione rzeczywistych danych identyfikujących, jest jedynym, co
przekracza granicę zaufania w~drodze do modelu. Warstwa komunikacji z~dostawcami przesyła je do
wybranego modelu językowego, natomiast tablica mapująca oraz klucz służący do jej szyfrowania
pozostają po wewnętrznej stronie granicy (zob. @sec:granica-zaufania). Z~perspektywy dostawcy
przekazany tekst zawiera wyłącznie dane syntetyczne, więc ich ewentualne zarejestrowanie czy
zapamiętanie nie ujawnia informacji o~rzeczywistych osobach.

Odpowiedź wygenerowana przez model odnosi się do danych syntetycznych, które ten otrzymał,
a~zatem również ona zawiera wartości zastępcze, a~nie oryginalne. Po jej odebraniu potok
anonimizacji uruchamia proces odwrotny. Na podstawie odwzorowania przechowywanego w~magazynie
odnajduje w~odpowiedzi wartości syntetyczne i~zastępuje je pierwotnymi danymi. Dopiero tak
przywrócona odpowiedź trafia do klienta, który otrzymuje wynik odnoszący się do rzeczywistych osób
i~dokumentów, nie wiedząc, że w~komunikacji z~modelem posłużono się danymi zastępczymi.

Przywrócenie danych wymaga kompletnej odpowiedzi modelu, ponieważ wartość syntetyczna może pojawić
się w~dowolnym jej miejscu, a~jej rozpoznanie wymaga dostępu do całego tekstu. Z~tego powodu obieg
jest synchroniczny: gateway czeka na pełną odpowiedź, zanim rozpocznie przywracanie, i~nie przekazuje
jej klientowi w~postaci strumieniowej (zob. @sec:wymagania).

Dodatkowego rozważenia wymaga praca w~trybie konwersacyjnym, w~którym do modelu w~każdej turze
przesyłana jest cała dotychczasowa historia rozmowy. Ponieważ wcześniejsze odpowiedzi zostały
przywrócone na potrzeby wyświetlenia klientowi, zawierają one ponownie dane oryginalne. Aby żadne
z~nich nie opuściło granicy zaufania, pseudonimizacji w~każdej turze podlega cała historia, a~nie
tylko najnowsze zapytanie. Dzięki spójności mapowań w~obrębie sesji te same dane otrzymują przy tym
te same zamienniki, co pozwala modelowi zachować ciągłość kontekstu rozmowy.

Przedstawiony przepływ zakłada, że dla każdej danej istnieje spójny, odwracalny zamiennik. Sposób,
w~jaki takie zamienniki są dobierane i~jak utrzymywana jest ich spójność w~obrębie sesji, omówiono
w~kolejnym podrozdziale.
