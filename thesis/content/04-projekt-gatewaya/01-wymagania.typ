#import "../../utils.typ": todo, silentheading, flex-caption

== Wymagania funkcjonalne i niefunkcjonalne <sec:wymagania>

Projekt systemu rozpoczyna się od ustalenia wymagań, które przekładają wnioski z~analizy zagrożeń
oraz podstaw teoretycznych (rozdz. @ch:prywatnosc i~@ch:anonimizacja) na konkretne właściwości
oprogramowania. W~inżynierii wymagań przyjęło się dzielić je na funkcjonalne, jakościowe oraz
ograniczenia, przy czym dwa ostatnie rodzaje określa się zwykle łącznie mianem wymagań
niefunkcjonalnych @Abad2017. Wymagania funkcjonalne opisują, co~system ma robić, natomiast
niefunkcjonalne odnoszą się do tego, w~jaki sposób ma to robić, obejmując jakość, bezpieczeństwo
i~wydajność rozwiązania. Zestawienie wymagań projektowanego gatewaya przedstawiono na rysunku
@rys:wymagania, a~w~dalszej części podrozdziału omówiono je kolejno.

#figure(
  {
    let req(body) = box(
      width: 100%, fill: luma(240), inset: (y: 6pt, x: 8pt), radius: 3pt,
      stroke: 0.5pt + gray.darken(20%),
      align(left, text(size: 0.88em, body)),
    )
    let col(title, items) = stack(
      dir: ttb, spacing: 6pt,
      align(center, text(weight: "bold", size: 0.95em, title)),
      ..items,
    )
    align(center, box(width: 97%, grid(
      columns: (1fr, 1fr), column-gutter: 14pt,
      col([Wymagania funkcjonalne], (
        req([Wykrywanie danych osobowych w~języku polskim]),
        req([Pseudonimizacja realistycznymi danymi syntetycznymi]),
        req([Odwracalność i~przywracanie danych w~odpowiedzi]),
        req([Spójność zamienników w~ramach sesji]),
        req([Pseudonimizacja całej historii konwersacji]),
        req([Obsługa wielu dostawców modeli językowych]),
      )),
      col([Wymagania niefunkcjonalne], (
        req([Bezpieczeństwo i~prywatność w~fazie projektowania]),
        req([Modularność i~niezależność od dostawcy]),
        req([Wydajność i~tryb synchroniczny]),
        req([Ukierunkowanie na język polski]),
        req([Prostota i~udokumentowane ograniczenia]),
      )),
    )))
  },
  caption: flex-caption(
    [Zestawienie wymagań funkcjonalnych i~niefunkcjonalnych projektowanego systemu.],
    [Wymagania funkcjonalne i niefunkcjonalne],
  ),
) <rys:wymagania>

=== Wymagania funkcjonalne

Podstawowym zadaniem systemu jest automatyczne wykrywanie danych osobowych w~treści zapytania
zapisanego w~języku polskim. Wykrywanie obejmuje zarówno encje ogólne, takie jak imiona i~nazwiska,
adresy, adresy e-mail czy numery telefonów, jak i~identyfikatory o~ściśle określonej strukturze,
charakterystyczne dla polskiego obrotu prawnego: numer PESEL, NIP, REGON, numer rachunku bankowego
oraz daty (zob. @sec:ner). Ponieważ pominięcie danej osobowej oznacza jej wyciek poza granicę
zaufania, mechanizm wykrywania projektowany jest z~przewagą czułości nad precyzją (ang.
_recall over precision_): lepiej oznaczyć fragment nadmiarowo, niż przeoczyć rzeczywistą daną.

Wykryte dane muszą zostać zastąpione realistycznymi danymi syntetycznymi, a~nie sztucznymi
znacznikami w~rodzaju „[OSOBA_1]". Zgodnie z~uzasadnieniem przedstawionym w~rozdziale
@ch:anonimizacja, zachowanie poprawnej struktury dokumentu wymaga zastąpienia nazwiska innym
prawdopodobnym nazwiskiem, numeru PESEL innym numerem o~poprawnej sumie kontrolnej, a~adresu innym
adresem zgodnym z~formatem. Dane zastępcze powinny przy tym zachowywać istotne własności oryginału,
w~tym poprawność struktur identyfikatorów oraz zgodność rodzaju gramatycznego imion.

Trzecim wymaganiem jest odwracalność procesu. System nie tylko zastępuje dane przed wysłaniem
zapytania, lecz także przywraca wartości oryginalne w~odpowiedzi zwróconej przez model, tak aby
użytkownik otrzymał wynik odnoszący się do rzeczywistych osób i~dokumentów. Pełny obieg, od
zapytania, przez podstawienie, aż po przywrócenie, musi przy tym zachować zgodność: każdej wartości
syntetycznej widocznej w~odpowiedzi powinno odpowiadać poprawne odwzorowanie z~powrotem na właściwy
oryginał.

Z~odwracalnością wiąże się wymaganie spójności w~ramach sesji użytkownika. Ta sama dana, występująca
wielokrotnie w~dokumencie, a~także w~kolejnych zapytaniach tej samej sesji, powinna być
konsekwentnie zastępowana tym samym odpowiednikiem. Wymaganie to obejmuje również koreferencję,
czyli rozpoznanie, że „Jan Kowalski" oraz pojawiające się dalej samo „Kowalski" odnoszą się do tej
samej osoby, a~także spójną odmianę przez przypadki, właściwą fleksyjnemu językowi polskiemu
(zob. @sec:ner).

Ponieważ docelowym trybem pracy systemu jest konwersacja, w~której cała historia rozmowy przesyłana
jest do modelu w~każdej turze, pseudonimizacji podlega nie tylko ostatnie zapytanie, lecz każda
wiadomość w~historii. W~przeciwnym razie dane przywrócone na potrzeby wyświetlenia wcześniejszej
odpowiedzi mogłyby ponownie opuścić granicę zaufania przy kolejnym żądaniu.

Ostatnim wymaganiem funkcjonalnym jest obsługa wielu dostawców modeli językowych. System powinien
umożliwiać kierowanie zapytań do różnych dostawców, wybieranych w~zależności od żądania, bez
konieczności modyfikowania pozostałych komponentów. Co istotne, żadne żądanie nie może pomijać etapu
pseudonimizacji: nie przewiduje się trybu bezpośredniego przekazywania danych (ang. _passthrough_),
w~którym tekst trafiałby do modelu z~pominięciem ochrony.

=== Wymagania niefunkcjonalne

Wymagania niefunkcjonalne wygodnie jest uporządkować według uznanego modelu jakości oprogramowania.
Norma ISO/IEC 25010 wyróżnia osiem charakterystyk jakości produktu, spośród których dla
projektowanego systemu kluczowe są trzy: bezpieczeństwo, utrzymywalność oraz wydajność
@iso25010 @Karnouskos2018.

Najważniejszą charakterystyką jest bezpieczeństwo, rozumiane jako ochrona informacji i~danych
w~taki sposób, by dostęp do nich miały wyłącznie podmioty o~odpowiednich uprawnieniach
@Karnouskos2018. W~projektowanym systemie wymaganie to przyjmuje postać zasady prywatności w~fazie
projektowania (ang. _privacy by design_), zgodnie z~którą ochrona prywatności jest wymaganiem
systemowym, traktowanym na równi z~każdym wymaganiem funkcjonalnym @Hoepman2014. Z~zasady tej wynika
kilka konkretnych ograniczeń projektowych. Po pierwsze, realizowana jest strategia minimalizacji
danych, jedna z~wyróżnionych przez Hoepmana strategii projektowania prywatności @Hoepman2014: poza
granicę zaufania trafiają wyłącznie dane syntetyczne, a~tablica wiążąca je z~oryginałami nigdy nie
opuszcza infrastruktury organizacji. Po drugie, oryginalne dane osobowe przechowywane są w~postaci
zaszyfrowanej. Po trzecie, w~dziennikach systemu nie zapisuje się rzeczywistych danych osobowych.
Po czwarte, jak wspomniano przy wymaganiach funkcjonalnych, każde żądanie przechodzi przez etap
pseudonimizacji.

Drugą istotną charakterystyką jest utrzymywalność, której podcharakterystyką jest modularność
@Karnouskos2018. System projektowany jest jako zbiór wymiennych komponentów o~jasno wydzielonych
odpowiedzialnościach, co pozwala rozwijać i~testować je niezależnie. W~szczególności warstwa
komunikacji z~dostawcami modeli opiera się na jednolitym interfejsie oraz wymiennych adapterach,
dzięki czemu dodanie nowego dostawcy sprowadza się do dostarczenia kolejnego adaptera i~zmiany
konfiguracji, bez ingerencji w~logikę pseudonimizacji (zob. @sec:dostawcy-llm). Modularności sprzyja
też oddzielenie logiki czystej, niezależnej od zasobów zewnętrznych, od warstwy odpowiedzialnej za
wejście i~wyjście.

Trzecią charakterystyką jest wydajność, rozumiana jako sprawność działania względem zużywanych
zasobów @Karnouskos2018. Z~natury zadania wynika tu istotne ograniczenie: ponieważ przywrócenie
danych wymaga kompletnej odpowiedzi modelu, system działa synchronicznie i~nie przesyła odpowiedzi
strumieniowo. Do tej grupy należą również akceptowalny narzut czasowy wprowadzany przez
pseudonimizację oraz jednokrotne, a~nie powtarzane przy każdym żądaniu, ładowanie modelu
rozpoznającego encje.

Projekt obejmuje wreszcie dwa wymagania o~charakterze przekrojowym. Pierwszym jest ukierunkowanie
na język polski, wynikające z~przypadku użycia, którym jest analiza polskich umów cywilnoprawnych:
zarówno wykrywanie, jak i~generowanie danych zastępczych muszą uwzględniać specyfikę polszczyzny.
Drugim jest prostota rozwiązania połączona z~jawnym dokumentowaniem ograniczeń. Tam, gdzie pełne
pokrycie problemu byłoby nieproporcjonalnie kosztowne, świadomie wybierane jest rozwiązanie
prostsze, a~jego granice są odnotowywane.
