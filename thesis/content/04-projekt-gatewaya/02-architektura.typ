#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Architektura wysokopoziomowa systemu <sec:architektura>

Określenie wymagań pozwala przejść do zaprojektowania ogólnej struktury systemu. Wraz ze wzrostem
złożoności oprogramowania samo dobranie algorytmów i~struktur danych przestaje wystarczać,
a~odrębnym problemem staje się zaprojektowanie ogólnej organizacji systemu, podziału na elementy
oraz sposobu ich współdziałania. Ten poziom projektowania określa się mianem architektury
oprogramowania @Garlan1993. Niniejszy podrozdział przedstawia architekturę gatewaya właśnie na tym
poziomie: wyróżnione komponenty, ich odpowiedzialności oraz zależności między nimi. Strukturę
systemu przedstawiono na rysunku @rys:architektura.

Z~punktu widzenia ogólnej organizacji projektowane rozwiązanie jest warstwą pośrednią między
klientem a~zewnętrznym modelem językowym. Pełni ono rolę zbliżoną do wzorca _API gateway_, w~którym
pojedynczy punkt wejścia przyjmuje żądania, kieruje je dalej i~przekształca @Taibi2018. W~typowym
zastosowaniu gateway agreguje wywołania wielu mikrousług, natomiast tutaj jego zadaniem jest
dołożenie przekrojowej funkcji ochrony danych: każde żądanie, zanim opuści infrastrukturę
organizacji, przechodzi przez pseudonimizację, a~każda odpowiedź, zanim trafi do klienta, przez
przywrócenie danych. Klient komunikuje się wyłącznie z~gatewayem i~nie łączy się bezpośrednio
z~dostawcą modelu. Warto przy tym zaznaczyć, że system zaprojektowano jako usługę backendową,
udostępniającą interfejs programistyczny. Nie obejmuje on warstwy interfejsu użytkownika, którą
organizacja może dostarczyć we własnym zakresie.

Architektura jest zorganizowana wokół granicy zaufania omówionej w~rozdziale @ch:prywatnosc
(zob. @sec:granica-zaufania). Wszystkie komponenty gatewaya, wraz z~klientem, znajdują się
w~infrastrukturze kontrolowanej przez organizację, po wewnętrznej stronie tej granicy. Poza nią
pozostają jedynie zewnętrzni dostawcy modeli, do których trafiają wyłącznie dane syntetyczne.
Tablica wiążąca dane oryginalne z~syntetycznymi oraz klucz służący do ich szyfrowania nigdy nie
opuszczają strony wewnętrznej.

#figure(
  diagram(
    spacing: (13mm, 10mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node-inset: 7pt,
    node((1, 0), [Klient\ #text(size: 0.72em, fill: gray.darken(40%))[konsument API]], name: <klient>),
    node((1, 1), [Potok anonimizacji\ #text(size: 0.72em, fill: gray.darken(40%))[orkiestracja]], name: <potok>),
    node((0, 2), [Wykrywanie\ danych osobowych], name: <detect>),
    node((2, 2), [Magazyn mapowań\ #text(size: 0.72em, fill: gray.darken(40%))[szyfrowany]], name: <vault>),
    node((2, 3), [Generowanie\ danych zastępczych], name: <gen>),
    node((1, 3), [Warstwa dostawców\ #text(size: 0.72em, fill: gray.darken(40%))[port · adaptery · router]], name: <prov>),
    node(
      enclose: (<klient>, <potok>, <detect>, <vault>, <gen>, <prov>),
      stroke: (paint: gray, dash: "dashed"), inset: 9pt, name: <tb>,
    ),
    node((2.3, -0.2), text(size: 0.74em, fill: gray.darken(40%))[granica\ zaufania], stroke: none),
    node((1, 4.2), [Zewnętrzne modele językowe\ #text(size: 0.72em, fill: gray.darken(40%))[dostawcy poza granicą zaufania]], name: <llm>),
    edge(<klient>, <potok>, "<->", [żądanie / odpowiedź]),
    edge(<potok>, <detect>, "->"),
    edge(<potok>, <vault>, "->"),
    edge(<vault>, <gen>, "->"),
    edge(<potok>, <prov>, "->"),
    edge(<prov>, <llm>, "->", [#box(fill: white, inset: (x: 3pt, y: 1pt))[tylko dane\ syntetyczne]]),
  ),
  caption: flex-caption(
    [Komponenty systemu oraz granica zaufania oddzielająca infrastrukturę organizacji od dostawców.],
    [Architektura komponentów systemu],
  ),
) <rys:architektura>

W~ramach gatewaya wyróżniono pięć głównych komponentów, przy czym podstawą podziału jest zasada,
zgodnie z~którą każdy z~nich odpowiada za jedną, jasno określoną funkcję:

- *Potok anonimizacji* — komponent orkiestrujący, spinający pozostałe elementy: dla żądania
  przychodzącego uruchamia wykrywanie oraz podstawianie danych, a~dla odpowiedzi modelu ich
  przywracanie. Sam nie komunikuje się z~modelem ani nie przechowuje danych, lecz koordynuje
  przepływ.
- *Moduł wykrywania danych osobowych* — lokalizuje w~tekście fragmenty stanowiące dane osobowe
  (zob. @sec:ner) i~zwraca je w~ujednoliconej postaci, niezależnej od użytej biblioteki
  rozpoznawania encji.
- *Moduł generowania danych zastępczych* — wytwarza realistyczne wartości syntetyczne dla wykrytych
  danych, zachowując ich istotne własności, a~jego strategię omówiono w~podrozdziale
  @sec:dane-zastepcze.
- *Magazyn odwracalnych mapowań sesji* — przechowuje w~postaci zaszyfrowanej powiązania między
  danymi oryginalnymi a~syntetycznymi w~obrębie sesji i~udostępnia je na potrzeby przywracania.
  Jest to jedyny komponent trwale przechowujący dane.
- *Warstwa komunikacji z~dostawcami* — wysyła pseudonimizowane zapytanie do wybranego dostawcy
  modelu i~odbiera odpowiedź, a~jej projekt, wraz z~mechanizmem wyboru dostawcy, omówiono
  w~podrozdziale @sec:dostawcy-llm.

Podział ten opiera się na klasycznej zasadzie ukrywania informacji, zgodnie z~którą każdy moduł kryje
przed pozostałymi pewną decyzję projektową, a~jego interfejs ujawnia możliwie najmniej o~wewnętrznym
działaniu @Parnas1972. Dzięki temu komponenty można rozwijać i~testować niezależnie, a~zmiana
wewnątrz jednego z~nich nie wymusza zmian w~pozostałych. Zasada ta przekłada się na dwa konkretne
rozwiązania projektowe. Po pierwsze, moduł wykrywania udostępnia wynik w~postaci niezależnej od
konkretnej biblioteki, dzięki czemu reszta systemu nie zależy od jej wewnętrznej reprezentacji.
Po drugie, logika czysta, taka jak generowanie wartości czy obliczanie sum kontrolnych, jest
oddzielona od warstwy odpowiedzialnej za wejście i~wyjście, czyli za komunikację z~magazynem danych
oraz z~modelem. Oddzielenie to, poza większą testowalnością, ogranicza również powierzchnię, na
której rzeczywiste dane osobowe stykają się z~zasobami zewnętrznymi.

Tak zarysowana struktura statyczna nie pokazuje jeszcze, w~jakiej kolejności komponenty są
uruchamiane podczas obsługi pojedynczego żądania. Dynamikę tę, czyli przepływ danych od zapytania
aż po przywróconą odpowiedź, omówiono w~kolejnym podrozdziale.
