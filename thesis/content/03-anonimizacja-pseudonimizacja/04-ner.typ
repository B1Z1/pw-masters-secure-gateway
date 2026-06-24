#import "../../utils.typ": todo, silentheading, flex-caption

== Rozpoznawanie encji nazwanych (NER) <sec:ner>

Rozpoznawanie encji nazwanych (NER, ang. _Named Entity Recognition_) to zadanie polegające na
wskazaniu w~tekście fragmentów odnoszących się do obiektów świata rzeczywistego i~przypisaniu ich
do z~góry określonych typów semantycznych, takich jak osoba, lokalizacja czy organizacja
@Li2022. W~projektowanym systemie NER pełni rolę mechanizmu wykrywania, czyli odpowiada za
zlokalizowanie w~zapytaniu tych fragmentów, które stanowią dane osobowe i~wymagają zastąpienia.
Zadanie ochrony tekstu sprowadza się wówczas do etykietowania sekwencji, w~którym model zaznacza
ciągi słów należące do predefiniowanych kategorii @Lison2021.

Metody rozpoznawania encji rozwijały się przez kilka pokoleń. Najstarsze podejścia opierały się
na ręcznie tworzonych regułach i~słownikach, zwanych gazeterami, które nie wymagają danych
uczących, lecz są pracochłonne i~trudne w~utrzymaniu @Li2022. Kolejne metody sięgnęły po uczenie
maszynowe: w~podejściu nadzorowanym opartym na cechach zadanie sprowadza się do klasyfikacji lub
etykietowania sekwencji, często z~użyciem warunkowych pól losowych (CRF, ang.
_Conditional Random Fields_), wymagających starannego doboru cech @Li2022. Najnowsze rozwiązania
należą do nurtu uczenia głębokiego, w~którym reprezentacje potrzebne do rozpoznania encji są
wyznaczane automatycznie, a~najlepsze wyniki osiągają modele oparte na architekturze transformera
@Li2022.

Typy encji rozpoznawanych przez NER w~naturalny sposób odpowiadają kategoriom danych osobowych:
osoby to imiona i~nazwiska, lokalizacje to adresy, a~organizacje to nazwy stron umowy. Oprócz
tych ogólnych kategorii dane wrażliwe obejmują również identyfikatory o~ściśle określonej
strukturze, takie jak numer PESEL czy NIP, które łatwiej wykryć regułami niż modelem
statystycznym. Połączenie obu podejść, modelu rozpoznającego encje oraz reguł dopasowujących
ustrukturyzowane identyfikatory, pozwala objąć ochroną szerszy zakres danych.

=== Wyzwania języka polskiego

Skuteczność rozpoznawania encji silnie zależy od języka przetwarzanego tekstu, a~język polski
stawia przed nią szczególne trudności. W~przeciwieństwie do izolującego języka angielskiego polski
jest językiem fleksyjnym @Mroczkowski2021, co oznacza, że to samo imię lub nazwisko przyjmuje
wiele form w~zależności od przypadka gramatycznego. Przykład takiej odmiany przedstawiono
w~tabeli @tab:deklinacja. Dla systemu wykrywającego dane osobowe wynika z~tego, że jeden byt może
wystąpić w~dokumencie pod kilkoma różnymi postaciami powierzchniowymi, które trzeba rozpoznać jako
odnoszące się do tej samej osoby i~zastąpić w~spójny sposób.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 9pt, y: 5pt),
    table.header([*Przypadek*], [*Imię „Jan"*], [*Nazwisko „Kowalski"*]),
    [Mianownik], [Jan], [Kowalski],
    [Dopełniacz], [Jana], [Kowalskiego],
    [Celownik], [Janowi], [Kowalskiemu],
    [Biernik], [Jana], [Kowalskiego],
    [Narzędnik], [Janem], [Kowalskim],
    [Miejscownik], [Janie], [Kowalskim],
    [Wołacz], [Janie], [Kowalski],
  ),
  caption: flex-caption(
    [Formy fleksyjne imienia i~nazwiska w~siedmiu przypadkach języka polskiego.],
    [Odmiana imienia i nazwiska przez przypadki],
  ),
) <tab:deklinacja>

Trudność potęgują swobodniejszy niż w~angielskim szyk zdania oraz mniejsza dostępność zasobów
anotowanych. Podstawowym zbiorem referencyjnym dla polszczyzny jest Narodowy Korpus Języka
Polskiego @Przepiorkowski2012, a~przegląd dostępnych korpusów oraz narzędzi do rozpoznawania
encji w~języku polskim przedstawili Marcińczuk i~Wawer @Marcinczuk2019. W~ostatnich latach
powstały także modele językowe trenowane specjalnie dla polszczyzny, takie jak HerBERT
@Mroczkowski2021, które stanowią punkt wyjścia dla skuteczniejszego rozpoznawania polskich encji.
Dostępność takich modeli i~narzędzi, a~także ich ograniczenia, omówiono w~kolejnym podrozdziale.
