#import "../../utils.typ": todo, silentheading, flex-caption

== Strategia generowania danych zastępczych i spójność mapowania <sec:dane-zastepcze>

W~rozdziale @ch:anonimizacja uzasadniono wybór podstawiania realistycznych danych syntetycznych jako
techniki maskowania. Niniejszy podrozdział uszczegóławia tę decyzję od strony projektowej
i~odpowiada na pytanie, w~jaki sposób dobierane są zamienniki oraz jak utrzymywana jest ich
spójność, tak aby dokument pozostał użyteczny dla modelu, a~cały proces był odwracalny.

Punktem wyjścia jest realizm zamienników. Zamiast usuwać dane lub zastępować je etykietami
kategorii, system wstawia w~ich miejsce inne, fikcyjne, lecz wyglądające wiarygodnie wartości.
Takie podejście, określane jako ukrywanie w~widoku publicznym (ang. _hiding in plain sight_), ma
dwie zalety. Po pierwsze, zachowuje strukturę i~kontekst dokumentu, dzięki czemu model językowy
interpretuje tekst tak samo jak oryginał. Po drugie, jak wykazano w~kontekście deidentyfikacji
dokumentów medycznych, realistyczne zamienniki utrudniają wykrycie danych, które ewentualnie umknęły
mechanizmowi wykrywania: nieusunięty rzeczywisty identyfikator ginie wśród wiarygodnych wartości
zastępczych i~przestaje wyróżniać się na ich tle @Carrell2013. Ta druga własność jest istotna,
ponieważ żaden mechanizm wykrywania nie jest doskonały, a~realizm zamienników ogranicza skutki jego
niedoskonałości.

Aby zamiennik był nieodróżnialny od danej rzeczywistej, musi zachowywać jej istotne własności
formalne. Dla identyfikatorów o~ustalonej strukturze, takich jak numer PESEL, NIP czy REGON, oznacza
to wygenerowanie wartości o~poprawnej budowie i~poprawnej sumie kontrolnej (zob.
@sec:techniki-maskowania), a~nie przypadkowego ciągu cyfr. Dla imion i~nazwisk istotna jest zgodność
rodzaju gramatycznego, a~dla adresów zgodność z~formatem adresu. Dzięki temu dokument po podstawieniu
pozostaje wewnętrznie spójny i~nie zdradza, że posłużono się w~nim danymi zastępczymi.

Realizm pojedynczego zamiennika nie wystarcza jednak, jeśli ta sama dana zostanie w~różnych miejscach
zastąpiona różnymi wartościami. Dana jest skutecznie ukryta tylko wtedy, gdy zamaskowano wszystkie
jej wystąpienia w~dokumencie @Pilan2022. Z~tego powodu kluczowym elementem strategii jest spójność:
każde wystąpienie tej samej danej w~obrębie sesji otrzymuje ten sam zamiennik. Wymaganie to obejmuje
również koreferencję, czyli rozpoznanie, że różne wzmianki odnoszą się do tego samego bytu.
W~dokumencie prawnym ta sama osoba bywa przywoływana raz pełnym imieniem i~nazwiskiem, a~innym razem
samym nazwiskiem, i~oba odwołania powinny prowadzić do tego samego zamiennika. Brak takiej spójności
nie tylko osłabiałby ochronę, lecz także wprowadzał model w~błąd, sugerując istnienie wielu różnych
osób tam, gdzie występuje jedna.

Dodatkową trudność wnosi fleksyjny charakter języka polskiego, omówiony w~rozdziale @ch:anonimizacja
(zob. @sec:ner). Ten sam byt pojawia się w~dokumencie w~różnych formach gramatycznych, a~zamiennik
musi zostać wstawiony w~formie zgodnej z~kontekstem zdania, aby tekst pozostał poprawny składniowo.
Oznacza to, że pojedynczemu bytowi odpowiada nie tyle jedna wartość zastępcza, ile cała rodzina jej
form fleksyjnych, spójnie wyprowadzanych z~tej samej wartości podstawowej. Przykład spójnego
odwzorowania, uwzględniającego koreferencję oraz odmianę przez przypadki, przedstawiono w~tabeli
@tab:mapowanie.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Fragment oryginalny*], [*Typ i~forma*], [*Zamiennik syntetyczny*]),
    [Tomasz Zieliński], [osoba, mianownik], [Paweł Kaczmarek],
    [Zielińskiego], [osoba, dopełniacz (koreferencja)], [Kaczmarka],
    [Tomaszowi Zielińskiemu], [osoba, celownik], [Pawłowi Kaczmarkowi],
    [85072112349], [numer PESEL], [91100587656],
    [ul.~Kwiatowa 5, Warszawa], [adres], [ul.~Lipowa 12, Kraków],
  ),
  caption: flex-caption(
    [Przykładowe spójne odwzorowanie danych oryginalnych na zastępcze (dane fikcyjne).],
    [Przykładowe odwzorowanie danych na zastępcze],
  ),
) <tab:mapowanie>

Spójność oraz odwracalność procesu zapewnia tablica mapująca, w~której zapisywane są powiązania
między wartościami oryginalnymi a~syntetycznymi. Pełni ona dwie role. W~kierunku od oryginału do
zamiennika pozwala sprawdzić, czy dana była już podstawiana, i~ponownie użyć tego samego zamiennika.
W~kierunku odwrotnym, od zamiennika do oryginału, umożliwia przywrócenie pierwotnych wartości
w~odpowiedzi modelu (zob. @sec:przeplyw). Zgodnie z~zasadą pseudonimizacji omówioną w~rozdziale
@ch:anonimizacja, to właśnie przechowywanie tej tablicy czyni proces odwracalnym, a~utrzymywanie jej
po wewnętrznej stronie granicy zaufania odróżnia projektowane rozwiązanie od trwałej anonimizacji.
Mapowanie obowiązuje w~granicach sesji użytkownika, co~wiąże spójność zamienników z~kontekstem
konkretnej rozmowy.

Przedstawiona strategia zapewnia, że poza granicę zaufania trafiają wyłącznie spójne, realistyczne
dane zastępcze, a~ich pierwowzory można odtworzyć po stronie organizacji. Pozostaje pytanie,
w~jaki sposób tak przygotowane zapytanie jest przekazywane do zewnętrznych modeli językowych i~jak
system obsługuje wielu dostawców, czemu poświęcono kolejny podrozdział.
