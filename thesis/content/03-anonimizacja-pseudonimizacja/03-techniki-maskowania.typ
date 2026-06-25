#import "../../utils.typ": todo, silentheading, flex-caption

== Techniki maskowania danych osobowych <sec:techniki-maskowania>

Maskowanie danych osobowych obejmuje rodzinę przekształceń, które usuwają lub zniekształcają
informacje identyfikujące w~dokumencie. Zgodnie z~opinią Grupy Roboczej Artykułu~29 techniki te
dzielą się na dwa główne podejścia: randomizację, która zmienia prawdziwość danych, aby osłabić
ich związek z~osobą, oraz generalizację, która obniża szczegółowość wartości @wp216. Obok nich
opinia wymienia pseudonimizację, polegającą na zastąpieniu jednego atrybutu innym; sama w~sobie
nie czyni ona zbioru anonimowym, lecz pozostaje użytecznym środkiem bezpieczeństwa.
Z~perspektywy projektowanego systemu kluczowe jest to, które z~tych technik pozwalają zachować
na tyle dużo treści dokumentu, by model językowy mógł nadal poprawnie go przeanalizować.

Najprostszą techniką jest usuwanie, czyli całkowite wykreślenie identyfikatora, oraz redakcja,
w~której dana zostaje zasłonięta umownym symbolem lub etykietą kategorii, na przykład
zastąpienie nazwiska napisem „IMIĘ I~NAZWISKO" @Garfinkel2015. Generalizacja podstawia wartość
mniej dokładną, lecz wciąż poprawną, jak sam rok zamiast pełnej daty urodzenia. Perturbacja,
a~w~szczególności dodanie szumu, modyfikuje atrybuty tak, by były mniej dokładne, zachowując
przy tym ogólny rozkład wartości w~zbiorze @wp216. Tokenizacja zastępuje identyfikator
pseudonimem wyliczonym za pomocą licznika, generatora liczb losowych, kodu uwierzytelniającego
wiadomość lub szyfrowania, przy czym odtworzenie pierwotnej wartości wymaga znajomości sekretu
lub tablicy mapującej @ENISA2021. Ostatnią techniką jest podstawianie danych syntetycznych,
czyli zastąpienie rzeczywistej danej inną, fikcyjną, lecz wyglądającą realistycznie. Podział
omawianych technik ze~względu na odwracalność przedstawiono na rysunku @rys:techniki-maskowania.

#figure(
  {
    let tech(body, fill: luma(240)) = box(
      width: 100%, fill: fill, inset: (y: 6pt, x: 8pt), radius: 3pt,
      stroke: 0.5pt + gray.darken(20%),
      align(center, body),
    )
    let col(title, items) = stack(
      dir: ttb, spacing: 6pt,
      align(center, text(weight: "bold", size: 0.9em, title)),
      ..items,
    )
    align(center, box(width: 92%, grid(
      columns: (1fr, 1fr), column-gutter: 16pt,
      col([Bez odwracalności \ (anonimizujące)], (
        tech([Usuwanie i~redakcja]),
        tech([Generalizacja]),
        tech([Perturbacja (szum)]),
      )),
      col([Z~odwracalnością \ (pseudonimizujące)], (
        tech([Tokenizacja]),
        tech([Podstawianie danych \ syntetycznych], fill: green.lighten(70%)),
      )),
    )))
  },
  caption: flex-caption(
    [Podział technik maskowania danych osobowych ze~względu na odwracalność procesu.],
    [Podział technik maskowania danych],
  ),
) <rys:techniki-maskowania>

Wybór techniki nie jest obojętny dla jakości dalszego przetwarzania. Każde maskowanie wiąże się
z~napięciem między ograniczeniem ryzyka ujawnienia a~zachowaniem użyteczności danych, a~celem
dobrej anonimizacji jest zminimalizowanie tego ryzyka przy jednoczesnym zachowaniu jak
największej części treści @Lison2021. Usuwanie i~redakcja chronią najskuteczniej, lecz
pozostawiają w~tekście luki oraz sztuczne znaczniki, które zaburzają jego strukturę gramatyczną
i~spójność. Dla modelu językowego, interpretującego znaczenie całego zdania, taki ubytek bywa
problematyczny: zdanie pozbawione podmiotu lub najeżone symbolami „XXX" niesie mniej informacji
kontekstowej i~może prowadzić do gorszej odpowiedzi.

Z~tego względu projektowany system opiera się na podstawianiu realistycznych danych
syntetycznych. Dane syntetyczne to wartości generowane sztucznie, które naśladują dane
rzeczywiste, zachowując ich własności, a~jednocześnie ograniczają ryzyko związane z~prywatnością
@Shi2025. W~rozważanym przypadku nie chodzi o~tworzenie całych zbiorów za pomocą złożonych modeli
generatywnych, lecz o~najprostszą postać tego podejścia: zastąpienie konkretnego nazwiska innym,
prawdopodobnym nazwiskiem, numeru PESEL innym numerem o~poprawnej strukturze, a~adresu innym,
zgodnym z~formatem adresem. Dzięki temu dokument przekazany do modelu pozostaje poprawny
składniowo i~zachowuje swój kontekst, mimo że nie zawiera już rzeczywistych danych osobowych.
Mechanizm odwzorowania wartości pierwotnych na syntetyczne, pozwalający później przywrócić
oryginalne dane w~odpowiedzi, opisano szerzej przy architekturze systemu (@ch:projekt).
