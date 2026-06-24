#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Przekazywanie danych do zewnętrznych modeli językowych <sec:granica-zaufania>

Współczesne duże modele językowe udostępniane są najczęściej w~modelu usługowym
(ang. _machine learning as a service_), w~którym organizacja nie uruchamia modelu we własnej
infrastrukturze, lecz korzysta z~niego za pośrednictwem interfejsu programistycznego (API)
wystawionego przez zewnętrznego dostawcę. Aby uzyskać odpowiedź, użytkownik przesyła do
dostawcy pełną treść zapytania, obejmującą zarówno polecenie, jak i~dołączone dokumenty.
W~przypadku analizy umów cywilnoprawnych oznacza to, że poza organizację trafia cały tekst
dokumentu wraz ze wszystkimi zawartymi w~nim danymi osobowymi.

Moment przekazania danych do dostawcy wyznacza granicę zaufania, czyli punkt, w~którym dane
opuszczają środowisko kontrolowane przez organizację i~trafiają do systemu zarządzanego przez
podmiot trzeci. Po przekroczeniu tej granicy organizacja traci bezpośrednią kontrolę nad tym,
w~jaki sposób dane są przechowywane, przetwarzane i~wykorzystywane. Nawet jeśli dostawca
deklaruje określone zasady ochrony, ich faktyczne przestrzeganie pozostaje poza możliwością
weryfikacji przez użytkownika, a~samo przekazanie danych jest nieodwracalne. Przepływ danych do
dostawcy wraz z~wynikającą z~niego granicą zaufania przedstawiono na rysunku @rys:granica-zaufania.

#figure(
  diagram(
    spacing: (16mm, 10mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node((0, 0), [Organizacja\ #text(size: 0.78em, fill: gray.darken(40%))[dokument z~danymi\ osobowymi]], name: <org>),
    node((3, 0.6), [Model językowy\ #text(size: 0.72em, fill: gray.darken(40%))[zapamiętywanie]], name: <model>),
    node((3, -0.6), [Infrastruktura i~API\ #text(size: 0.72em, fill: gray.darken(40%))[logowanie · retencja · trenowanie]], name: <api>),
    node(enclose: (<model>, <api>), stroke: (paint: gray, dash: "dashed"), inset: 12pt, name: <prov>),
    node((3, -1.55), text(size: 0.82em, fill: gray.darken(40%))[Dostawca usługi — poza granicą zaufania], stroke: none),
    edge(<org>, <prov>, "->", [pełny prompt\ z~danymi osobowymi]),
  ),
  caption: flex-caption(
    [Przekazanie danych do zewnętrznego modelu językowego i~granica zaufania.],
    [Przepływ danych i granica zaufania],
  ),
) <rys:granica-zaufania>

Z~perspektywy ochrony prywatności przekazanie danych do zewnętrznego modelu rodzi dwie odrębne
powierzchnie narażenia. Pierwszą stanowi sam model językowy, który może utrwalić fragmenty
przekazanych lub treningowych danych i~później je ujawnić (zob. @sec:memorization). Drugą jest
infrastruktura i~interfejs API dostawcy, gdzie dane mogą być rejestrowane, przechowywane oraz
wykorzystywane do dalszego rozwoju modeli (zob. @sec:ryzyka-api). Rozróżnienie to porządkuje
analizę zagrożeń prowadzoną w~dalszej części rozdziału.
