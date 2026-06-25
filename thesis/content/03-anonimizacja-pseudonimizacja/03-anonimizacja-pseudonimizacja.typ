#import "../../utils.typ": todo, silentheading, flex-caption

= Anonimizacja i pseudonimizacja danych w systemach AI <ch:anonimizacja>

Zagrożenia i~wymagania prawne omówione w~poprzednim rozdziale wskazują, że dane osobowe nie
powinny opuszczać infrastruktury organizacji w~postaci jawnej. Niniejszy rozdział przedstawia
techniczne podstawy ochrony takich danych, czyli metody, które pozwalają przekształcić treść
zapytania tak, aby nie zawierała informacji umożliwiających identyfikację osób, a~mimo to
pozostawała użyteczna dla modelu językowego. Najpierw rozróżniono anonimizację i~pseudonimizację
od strony operacyjnej oraz uzasadniono wybór tej drugiej. Następnie przywołano formalne modele
prywatności i~wskazano granice ich stosowalności do tekstu swobodnego. Kolejno omówiono techniki
maskowania danych, ze szczególnym uwzględnieniem podstawiania realistycznych wartości
syntetycznych, oraz metody rozpoznawania encji nazwanych służące do wykrywania danych osobowych
w~tekście, wraz z~wyzwaniami języka polskiego. Rozdział zamyka przegląd istniejących narzędzi
i~ich ograniczeń, który uzasadnia potrzebę opracowania rozwiązania przedstawionego w~dalszej
części pracy.

#include "01-anonimizacja-pseudonimizacja.typ"
#include "02-modele-prywatnosci.typ"
#include "03-techniki-maskowania.typ"
#include "04-ner.typ"
#include "05-narzedzia-ograniczenia.typ"
