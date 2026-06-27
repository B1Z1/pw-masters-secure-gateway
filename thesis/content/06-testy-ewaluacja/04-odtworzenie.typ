#import "../../utils.typ": todo, silentheading, flex-caption

== Odwracalność i odtworzenie danych <sec:eval-odtworzenie>

Odwracalność odróżnia pseudonimizację od trwałej anonimizacji: po otrzymaniu odpowiedzi modelu brama
musi przywrócić w~niej wartości oryginalne w~miejsce zastępczych. Ocena porównuje każdą przywróconą
wartość z~pierwowzorem i~zalicza wynik do jednej z~trzech kategorii, czyli odtworzenia dokładnego,
odtworzenia w~innej formie albo pominięcia. Na poziomie pojedynczych encji dokładnie odtworzono 1003
z~1150 wartości, czyli 87%, a~po wyłączeniu jednego typu, dat, wskaźnik ten sięga niemal 100%.

Rozkład wyników w~podziale na daty i~pozostałe typy przedstawiono w~tabeli @tab:eval-odtworzenie.
Niemal wszystkie niepowodzenia skupiają się w~datach. Spośród 1005 instancji pozostałych typów
dokładnie odtworzono 1003, a~tylko dwie wróciły w~innej formie lub nie wróciły wcale. Daty zachowują
się odwrotnie: żadnej ze~145 nie odtworzono dokładnie, 131 pominięto, a~14 wróciło jedynie jako
fragment, na przykład data „27.05.2003" wraca jako „2003".

#figure(
  table(
    columns: (1fr, auto, auto, auto),
    align: (left, right, right, right),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Wynik odtworzenia*], [*Daty*], [*Pozostałe typy*], [*Razem*]),
    [dokładny], [0], [1003], [1003],
    [w~innej formie], [14], [1], [15],
    [pominięty], [131], [1], [132],
    [*Razem*], [*145*], [*1005*], [*1150*],
  ),
  caption: flex-caption(
    [Wyniki odtworzenia danych na poziomie encji, w~podziale na daty i~pozostałe typy.],
    [Wyniki odtworzenia danych],
  ),
) <tab:eval-odtworzenie>

Przyczyna jest ta sama, którą opisano przy nadwykrywaniu dat (zob. @sec:eval-detekcja). Nakładające
się detekcje sprawiają, że wartość zastępcza przypisana nadmiarowemu fragmentowi nie zostaje
odwrócona, przez co pierwotna data nie wraca na swoje miejsce. Skutek ten widać również w~mierze
dokumentowej, w~której dokument liczy się dopiero wtedy, gdy wszystkie jego encje odtworzono dokładnie.
Ponieważ każda umowa zawiera co~najmniej jedną datę, miara ta wynosi 0. Jest to wskaźnik surowy,
w~całości zdominowany przez problem dat, dlatego jako nagłówkowy przyjęto wynik na poziomie encji,
bardziej informatywny, wynoszący 87% i~niemal 100% po pominięciu dat. Na tym zamyka się ocena
poprawności pseudonimizacji, a~kolejny podrozdział przechodzi do drugiej osi, czyli wpływu
pseudonimizacji na jakość odpowiedzi modelu.
