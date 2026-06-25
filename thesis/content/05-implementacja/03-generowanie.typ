#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Generowanie danych zastępczych <sec:impl-generowanie>

Drugim ogniwem silnika pseudonimizacji jest generator danych zastępczych, wytwarzający dla każdej
wykrytej encji realistyczną wartość syntetyczną, zgodnie ze strategią uzasadnioną w~rozdziale
@ch:projekt (zob. @sec:dane-zastepcze). Zbudowano go na bibliotece Faker w~lokalizacji polskiej
(`pl_PL`), dzięki czemu zwracane imiona, nazwiska czy adresy są typowe dla polszczyzny @faker.
Generator jest bezstanowy i~dla pojedynczej encji zwraca jedną poprawną wartość, a~o~spójności
i~niepowtarzalności zamienników w~obrębie sesji decyduje magazyn mapowań (zob. @sec:impl-magazyn).
Zainicjowany ziarnem działa deterministycznie, co wykorzystują testy, a~bez ziarna losowo. Każdemu
typowi encji odpowiada osobny builder, do którego generator kieruje żądanie.

Dla identyfikatorów o~ustalonej strukturze, takich jak PESEL, NIP, REGON czy numer rachunku
bankowego, wartość zastępcza musi mieć poprawną sumę kontrolną, inaczej zdradziłaby swoją sztuczność
(zob. @sec:dane-zastepcze). Osiągnięto to przez ponowne wykorzystanie tej samej logiki sum
kontrolnych, która służy do wykrywania (zob. @sec:impl-wykrywanie), więc wygenerowany numer
przechodzi dokładnie tę samą weryfikację. Generator zachowuje przy tym istotne własności oryginału:
dla numeru PESEL odtwarza zakodowaną w~nim płeć @peselgov, a~dla numeru REGON jego wariant długości.
Builder numeru PESEL przedstawiono na rysunku @rys:build-pesel.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read("listings/build_pesel.py")))),
  ),
  caption: flex-caption(
    [Generowanie numeru PESEL: poprawną sumę kontrolną zapewnia `make_pesel` reużywane z~modułu wykrywania, a~płeć jest odtwarzana z~metadanych encji.],
    [Generowanie numeru PESEL],
  ),
  kind: image,
) <rys:build-pesel>

Generowanie imion i~nazwisk wymaga większej uwagi ze względu na fleksyjny charakter polszczyzny
(zob. @sec:ner). Dla każdej osoby losowana jest płeć, a~następnie zgodne z~nią imię oraz nazwisko,
przy czym płeć pozostaje niezależna od ewentualnego pobliskiego numeru PESEL, co stanowi świadome
uproszczenie. Nazwisko dobierane jest spośród odmienialnych, dzięki czemu zamiennik można przedstawić
w~formie zgodnej z~kontekstem zdania. Imię i~nazwisko są przy tym klasyfikowane oraz odmieniane
niezależnie, gdyż mogą podlegać różnym wzorcom odmiany. Builder osoby wraz z~funkcją wyprowadzającą
formy fleksyjne przedstawiono na rysunku @rys:build-person.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read("listings/build_person.py")))),
  ),
  caption: flex-caption(
    [Generowanie osoby: losowa płeć, dobór odmienialnego nazwiska oraz wyprowadzenie form fleksyjnych imienia i~nazwiska odmienianych niezależnie.],
    [Generowanie imienia i~nazwiska],
  ),
  kind: image,
) <rys:build-person>

Funkcja `person_forms` wyznacza w~ten sposób całą rodzinę form fleksyjnych imienia i~nazwiska,
przechowywaną w~obiekcie wynikowym generatora. Przykładowy paradygmat takiej odmiany przedstawiono
w~tabeli @tab:odmiana.

#figure(
  table(
    columns: 2,
    align: (left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Przypadek*], [*Forma zamiennika*]),
    [mianownik], [Magdalena Wiśniewska],
    [dopełniacz], [Magdaleny Wiśniewskiej],
    [celownik], [Magdalenie Wiśniewskiej],
    [biernik], [Magdalenę Wiśniewską],
    [narzędnik], [Magdaleną Wiśniewską],
    [miejscownik], [Magdalenie Wiśniewskiej],
  ),
  caption: flex-caption(
    [Formy fleksyjne wygenerowanego imienia i~nazwiska „Magdalena Wiśniewska" wytworzone przez mechanizm odmiany (dane fikcyjne).],
    [Paradygmat odmiany zamiennika],
  ),
) <tab:odmiana>

Samą odmianę, widoczną w~powyższym paradygmacie, zrealizowano własnym, lekkim mechanizmem opartym na
tablicach końcówek, bez zewnętrznego analizatora morfologicznego, zgodnie z~zasadą prostoty
i~jawnego dokumentowania ograniczeń (zob. @sec:wymagania). Mechanizm ten działa wyłącznie w~kierunku
generowania: z~formy podstawowej oraz rozpoznanego wzorca wytwarza formy we wszystkich przypadkach,
podczas gdy kierunek odwrotny, czyli sprowadzenie dowolnej formy do postaci podstawowej, pozostaje
zadaniem modelu statystycznego z~etapu wykrywania (zob. @sec:impl-wykrywanie). Analogicznie traktowane
są nazwy miejscowości, które podlegają odmianie, podczas gdy pełny adres pozostaje nierozdzielną
całością. Builder miejscowości przedstawiono na rysunku @rys:build-location.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read("listings/build_location.py")))),
  ),
  caption: flex-caption(
    [Generowanie miejscowości: dobór nazwy odmienialnej oraz wyprowadzenie jej form fleksyjnych.],
    [Generowanie miejscowości],
  ),
  kind: image,
) <rys:build-location>

Przyjęte podejście świadomie nie pokrywa wszystkich przypadków polskiej fleksji. Tokeny o~temacie
miękkim, formy z~tak zwanym e~ruchomym czy nazwy obcego pochodzenia odmieniane są jedynie
w~przybliżeniu, a~gdy żaden wzorzec nie pasuje, zamiennik pozostaje w~formie podstawowej. Ograniczenia
te uznano za akceptowalne, ponieważ dotyczą mniejszości przypadków, a~ich skutkiem jest co najwyżej
drobna niezgodność gramatyczna, nie zaś naruszenie ochrony danych.

Generator dostarcza zatem spójne, realistyczne i~odwracalne wartości zastępcze wraz z~ich formami
fleksyjnymi. Aby jednak te same dane otrzymywały konsekwentnie ten sam zamiennik, a~cały proces
pozostał odwracalny, potrzebny jest magazyn przechowujący powiązania między oryginałami
a~zamiennikami, któremu poświęcono kolejny podrozdział.
