#import "../../utils.typ": todo, silentheading, flex-caption

= Testy, ewaluacja i analiza wyników <ch:ewaluacja>

Rozdział piąty zamknął opis budowy systemu, pozostaje więc pytanie, jak dobrze zbudowana brama
wywiązuje się ze~swojego zadania. Niniejszy rozdział poddaje gotowe rozwiązanie ewaluacji prowadzonej
wzdłuż dwóch osi. Pierwsza dotyczy poprawności samej pseudonimizacji, to jest trafności wykrywania
danych osobowych, szczelności ich podstawienia oraz wierności przywracania w~odpowiedzi. Druga
sprawdza, czy zastąpienie danych realistycznymi wartościami syntetycznymi zachowuje wartość
analityczną odpowiedzi modelu w~zadaniu analizy polskich umów cywilnoprawnych. Obie osie odpowiadają
na to samo nadrzędne pytanie, czy ochronę prywatności daje się pogodzić z~użytecznością.

Rozdział otwiera omówienie metodyki oraz zbioru testowego, na którym oparto pomiar: czarnoskrzynkowego
stanowiska sterującego żywą bramą oraz syntetycznego korpusu polskich umów, dla którego zbiór
poprawnych odpowiedzi jest znany z~góry. Na tej podstawie wyznaczono miary skuteczności wykrywania
i~pseudonimizacji wraz z~analizą najczęstszych błędów, a~następnie zbadano odwracalność procesu,
czyli wierność odtwarzania danych pierwotnych.

Druga część rozdziału przenosi uwagę z~poprawności na użyteczność. Porównano w~niej odpowiedzi modelu
udzielane na danych oryginalnych oraz pseudonimizowanych, co pozwoliło rozstrzygnąć, czy realizm
danych zastępczych ma znaczenie dla jakości analizy. Rozdział zamyka ocena wydajności potoku oraz
weryfikacja bezpieczeństwa przetwarzania, sprawdzająca, czy poza granicę zaufania nie wydostają się
dane w~postaci oryginalnej.

#include "01-metodyka.typ"
#include "02-zbior-testowy.typ"
#include "03-wykrywanie.typ"
#include "04-odtworzenie.typ"
#include "05-jakosc-odpowiedzi.typ"
#include "06-wydajnosc-bezpieczenstwo.typ"
