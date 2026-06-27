#import "../../utils.typ": todo, silentheading, flex-caption

= Testy, ewaluacja i analiza wyników <ch:ewaluacja>

Zaprojektowanie i~zbudowanie systemu, opisane w~dwóch poprzednich rozdziałach, nie rozstrzyga
jeszcze, jak dobrze gotowa brama wywiązuje się ze~swojego zadania. Niniejszy rozdział poddaje gotowe
rozwiązanie ewaluacji prowadzonej wzdłuż dwóch osi. Pierwsza dotyczy poprawności samej
pseudonimizacji, to jest trafności wykrywania danych osobowych, szczelności ich podstawienia oraz
wierności przywracania w~odpowiedzi. Druga sprawdza, czy zastąpienie danych realistycznymi
wartościami syntetycznymi zachowuje wartość analityczną odpowiedzi modelu w~zadaniu analizy polskich
umów cywilnoprawnych, a~obie osie odpowiadają na to samo nadrzędne pytanie, czy ochronę prywatności
daje się pogodzić z~użytecznością. Najpierw omówiono metodykę oraz zbiór testowy, na którym oparto
pomiar, czyli czarnoskrzynkowe stanowisko sterujące żywą bramą oraz syntetyczny korpus polskich
umów, dla którego zbiór poprawnych odpowiedzi jest znany z~góry. Na tej podstawie wyznaczono miary
skuteczności wykrywania i~pseudonimizacji wraz z~analizą najczęstszych błędów, a~następnie zbadano
odwracalność procesu, czyli wierność odtwarzania danych pierwotnych. Kolejno przeniesiono uwagę
z~poprawności na użyteczność, porównując odpowiedzi modelu udzielane na danych oryginalnych oraz
pseudonimizowanych i~sprawdzając, czy realizm danych zastępczych ma znaczenie oraz czy wniosek ten
utrzymuje się na modelach znacznie silniejszych.

#include "01-metodyka.typ"
#include "02-zbior-testowy.typ"
#include "03-wykrywanie.typ"
#include "04-odtworzenie.typ"
#include "05-jakosc-odpowiedzi.typ"
