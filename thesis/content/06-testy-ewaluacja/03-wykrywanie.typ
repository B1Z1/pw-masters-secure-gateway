#import "../../utils.typ": todo, silentheading, flex-caption

== Skuteczność wykrywania i pseudonimizacji <sec:eval-detekcja>

Skuteczność wykrywania ocenia się trzema standardowymi miarami. Precyzja to udział trafnych wskazań
wśród wszystkich wskazań bramy, a~czułość to udział wykrytych danych wśród wszystkich danych osobowych
obecnych w~dokumencie. Miarą łączną jest F1, czyli średnia harmoniczna precyzji i~czułości. Wartości
agreguje się na dwa sposoby: mikro, sumując trafienia i~pomyłki po wszystkich instancjach, oraz makro,
uśredniając wynik po typach encji z~równą wagą każdego z~nich.

Sposób zliczania trafień zależy od przyjętej polityki dopasowania granic. W~wariancie pokrycia
wskazanie uznaje się za trafne, gdy nachodzi na encję wzorcową, natomiast w~wariancie dokładnym
wymagane jest zgodne wyznaczenie obu jej granic. Jako podstawową przyjęto politykę pokrycia, ponieważ
zadaniem systemu jest zamaskowanie danej, a~do tego wystarcza objęcie jej wskazaniem. Wariant dokładny
pełni rolę pomocniczą i~ujawnia sytuacje, w~których encję wykryto jedynie częściowo. Warto przy tym
przypomnieć przyjętą wcześniej przewagę czułości nad precyzją (zob. @sec:wymagania). Pominięcie danej
oznacza jej wyciek, podczas gdy nadmiarowe wskazanie prowadzi najwyżej do zbędnego podstawienia,
dlatego system celowo wykrywa z~zapasem.

Wyniki w~podziale na typy encji przedstawiono w~tabeli @tab:eval-detekcja. Czułość mikro wynosi 1,0,
co~oznacza, że w~całym korpusie żadna dana osobowa nie umknęła wykryciu. Precyzja mikro wynosi 0,887,
a~jej obniżenie pochodzi niemal wyłącznie od jednego typu, daty, dla którego precyzja spada do 0,5.
Pozostałe dziewięć typów osiąga precyzję równą lub bliską jedności, co~widać po wyższej wartości makro,
równej 0,949. Rozkład ten jest bezpośrednim skutkiem opisanej decyzji projektowej, w~której czułość
ma pierwszeństwo przed precyzją.

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    align: (left, right, right, right, right, right),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 6pt, y: 5pt),
    table.header([*Typ encji*], [*Czułość*], [*Precyzja*], [*F1*], [*Czuł. dokł.*], [*Wsparcie*]),
    [`PERSON`], [1,0], [1,0], [1,0], [0,969], [224],
    [`EMAIL_ADDRESS`], [1,0], [1,0], [1,0], [1,0], [168],
    [`PHONE_NUMBER`], [1,0], [1,0], [1,0], [1,0], [168],
    [`DATE_TIME`], [1,0], [0,5], [0,667], [1,0], [145],
    [`ADDRESS`], [1,0], [1,0], [1,0], [0,992], [132],
    [`LOCATION`], [1,0], [0,989], [0,994], [1,0], [89],
    [`PESEL`], [1,0], [1,0], [1,0], [1,0], [89],
    [`BANK_ACCOUNT`], [1,0], [1,0], [1,0], [1,0], [76],
    [`NIP`], [1,0], [1,0], [1,0], [1,0], [36],
    [`REGON`], [1,0], [1,0], [1,0], [1,0], [23],
    [*mikro*], [*1,0*], [*0,887*], [*0,940*], [0,993], [*1150*],
    [*makro*], [*1,0*], [*0,949*], [*0,966*], [0,996], [—],
  ),
  caption: flex-caption(
    [Skuteczność wykrywania według typu encji w~polityce pokrycia (kolumna „Czuł. dokł." podaje czułość przy dokładnych granicach).],
    [Skuteczność wykrywania według typu encji],
  ),
) <tab:eval-detekcja>

=== Analiza błędów wykrywania

Wysokiemu wynikowi towarzyszą trzy konkretne uchybienia, z~których każde ma źródło w~innej warstwie
systemu.

Pierwsze dotyczy numerów telefonów i~pokazuje, jak ewaluacja prowadzi wprost do poprawy. W~pierwszym
przebiegu trzy numery ze~specjalnych zakresów (702, 802, 809) przetrwały w~tekście wychodzącym
w~oryginale, co~stanowi wyciek danych poza granicę zaufania (zob. @sec:wymagania). Przyczyną był tryb
walidacji w~rozpoznawaczu telefonów biblioteki Presidio (parametr `leniency`), który odrzucał numery
formalnie możliwe, lecz nieprzypisane, więc nie były one wykrywane ani podstawiane. Po złagodzeniu
walidacji wykrywane są wszystkie numery, a~precyzja pozostaje równa 1,0, co~przedstawia tabela
@tab:eval-telefon. Była to usterka konfiguracji, usunięta strojeniem istniejącego komponentu.

#figure(
  table(
    columns: (auto, auto, auto, auto),
    align: (left, right, right, right),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Konfiguracja*], [*Czułość*], [*Precyzja*], [*Wycieki*]),
    [Przed (`leniency=VALID`)], [0,9702], [1,0], [3],
    [Po (`leniency=POSSIBLE`)], [1,0], [1,0], [0],
  ),
  caption: flex-caption(
    [Wykrywanie numerów telefonów przed poprawką konfiguracji i~po niej.],
    [Wpływ poprawki na wykrywanie telefonów],
  ),
) <tab:eval-telefon>

Drugie dotyczy nazwisk i~ma inny charakter. Po poprawce telefonów pozostają dwa wycieki tego samego
rodzaju: w~linii podpisu nazwisko strony („Godzisz", „Potoczna") zostaje w~tekście, podczas gdy imię
jest podstawiane. Ta sama osoba jest poprawnie wykrywana z~pełnym imieniem i~nazwiskiem w~komparycji,
więc źródłem nie jest konfiguracja, lecz statystyczny model języka, który w~długim dokumencie skraca
wzmiankę do samego imienia. W~polityce pokrycia liczy się to jako trafienie (stąd czułość osób 1,0),
ale polityka dokładnych granic obniża ją do 0,969, a~audyt ujawnia ocalałe nazwisko. Naprawa
wymagałaby osobnego komponentu działającego po modelu, a~pryncypialnym kierunkiem jest uzupełnianie
uciętej wzmianki na podstawie koreferencji (zob. @sec:dane-zastepcze), skoro pełne nazwisko system zna
już z~komparycji. W~obecnej postaci jest to udokumentowane ograniczenie modelu.

Trzecie odpowiada za najniższą precyzję i~dotyczy dat. Czułość wynosi tu 1,0, lecz precyzja spada do
0,5, ponieważ obok każdej rzeczywistej daty brama wykrywa nakładający się fragment jako osobną datę:
z~frazy „zawarta w~dniu 01.12.1993" rozpoznawany jest także człon „dniu 01.". Nie jest to wyciek,
gdyż rzeczywista data zostaje wykryta i~podstawiona, lecz nadmiarowe detekcje obniżają precyzję oraz
psują odwracalność dat, omówioną w~następnym podrozdziale. Źródłem jest rozpoznawacz dat i~sposób
rozstrzygania nakładek, a~naprawa po stronie bramy stanowi kierunek dalszych prac.
