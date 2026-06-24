#import "../../utils.typ": todo, silentheading, flex-caption

== Wymagania prawne dotyczące ochrony danych osobowych <sec:regulacje>

Zagrożenia opisane w~poprzednich podrozdziałach mają wymiar nie tylko techniczny, lecz także
prawny. Przekazywanie danych osobowych do zewnętrznych dostawców usług AI podlega regulacjom,
które wyznaczają granice dopuszczalnego przetwarzania oraz nakładają na podmioty przetwarzające
określone obowiązki. W~przypadku rozwiązania analizowanego w~niniejszej pracy szczególne
znaczenie mają dwa akty prawa unijnego: ogólne rozporządzenie o~ochronie danych (RODO) oraz
akt o~sztucznej inteligencji (EU AI Act).

=== Ogólne rozporządzenie o ochronie danych (RODO)

RODO definiuje dane osobowe jako wszelkie informacje o~zidentyfikowanej lub możliwej do
zidentyfikowania osobie fizycznej (art. 4 pkt 1) @gdpr2016. Kluczowe z~perspektywy
projektowanego systemu jest rozróżnienie między anonimizacją a~pseudonimizacją. Zgodnie
z~motywem 26 rozporządzenia zasady ochrony danych nie mają zastosowania do informacji
anonimowych, czyli takich, których nie da się powiązać z~konkretną osobą. Dane poddane
pseudonimizacji, które za pomocą dodatkowych informacji można z~powrotem przypisać osobie,
pozostają natomiast danymi osobowymi i~podlegają rozporządzeniu w~pełnym zakresie. Oznacza to,
że samo zastąpienie danych w~treści zapytania nie zwalnia z~obowiązków wynikających z~RODO,
jeśli zachowywana jest możliwość ich odtworzenia.

Rozporządzenie ustanawia również zasadę minimalizacji danych, zgodnie z~którą przetwarzane dane
powinny być ograniczone do tego, co niezbędne do osiągnięcia celu przetwarzania
(art. 5 ust. 1 lit. c) @gdpr2016. Przekazanie dokumentu zewnętrznemu dostawcy modelu czyni
z~niego podmiot przetwarzający, co wymaga odpowiedniej podstawy prawnej oraz uregulowania
powierzenia przetwarzania (art. 28). Dodatkowym utrudnieniem jest fakt, że wielu dostawców
modeli językowych działa poza Europejskim Obszarem Gospodarczym, co uruchamia obostrzenia
dotyczące transferu danych do państw trzecich (rozdział V rozporządzenia). Problem nabiera wagi
w~kontekście umów cywilnoprawnych, które z~natury zawierają liczne dane identyfikacyjne, takie
jak imiona i~nazwiska, numery PESEL, adresy czy dane finansowe stron, a~w~niektórych przypadkach
mogą obejmować również informacje należące do szczególnych kategorii danych, podlegających
wzmożonej ochronie na podstawie art. 9 rozporządzenia.

=== Akt o sztucznej inteligencji (EU AI Act)

Akt o~sztucznej inteligencji wprowadza podejście oparte na ryzyku, klasyfikując systemy AI
według poziomu zagrożenia, jakie stwarzają, od praktyk zakazanych, przez systemy wysokiego
ryzyka objęte najszerszymi obowiązkami, po systemy o~ryzyku ograniczonym i~minimalnym
@aiact2024. Dla rozwiązań wykorzystujących modele językowe istotne są przede wszystkim
obowiązki w~zakresie przejrzystości, w~tym informowanie użytkownika, że wchodzi w~interakcję
z~systemem sztucznej inteligencji. Akt o~sztucznej inteligencji nie zastępuje przy tym
przepisów o~ochronie danych osobowych, lecz je uzupełnia, ponieważ przetwarzanie danych
w~systemach AI nadal w~pełni podlega RODO. Dla projektowanego systemu oznacza to konieczność
łącznego spełnienia wymagań obu reżimów prawnych. Wprowadzony przez akt podział na poziomy
ryzyka zilustrowano na rysunku @rys:ai-act-ryzyko.

#figure(
  {
    let band(w, fill, title, sub) = box(
      width: w, fill: fill, inset: (y: 7pt, x: 8pt), radius: 3pt,
      stroke: 0.5pt + gray.darken(20%),
      align(center)[#strong[#title] \ #text(size: 0.78em, fill: gray.darken(40%))[#sub]],
    )
    align(center, stack(
      dir: ttb, spacing: 5pt,
      band(34%, red.lighten(55%), [Ryzyko niedopuszczalne], [praktyki zakazane]),
      band(54%, orange.lighten(55%), [Wysokie ryzyko], [najszersze obowiązki i~nadzór]),
      band(74%, yellow.lighten(50%), [Ograniczone ryzyko], [obowiązki przejrzystości]),
      band(94%, green.lighten(65%), [Minimalne ryzyko], [brak dodatkowych wymogów]),
    ))
  },
  caption: flex-caption(
    [Poziomy ryzyka w~akcie o~sztucznej inteligencji (EU AI Act).],
    [Poziomy ryzyka w EU AI Act],
  ),
) <rys:ai-act-ryzyko>
