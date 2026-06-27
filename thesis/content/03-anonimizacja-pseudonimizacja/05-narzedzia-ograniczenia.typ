#import "../../utils.typ": todo, silentheading, flex-caption

== Istniejące narzędzia i ich ograniczenia <sec:narzedzia>

Opisane techniki oraz metody rozpoznawania encji znalazły odzwierciedlenie w~gotowych
narzędziach do wykrywania i~maskowania danych osobowych. Najbardziej rozpowszechnionym
rozwiązaniem otwartoźródłowym jest Microsoft Presidio, framework łączący predefiniowane
rozpoznawacze, oparte na wyrażeniach regularnych, sumach kontrolnych i~analizie kontekstu,
z~modelami rozpoznawania encji nazwanych @presidio. Samo rozpoznawanie encji Presidio realizuje
za pomocą zewnętrznych bibliotek przetwarzania języka, domyślnie spaCy @spacy. Po stronie
komercyjnej podobną funkcję pełnią usługi chmurowe klasy DLP (ang. _Data Loss Prevention_),
takie jak Google Cloud Sensitive Data Protection, udostępniające rozbudowany zbiór wykrywanych
typów danych @gcpdlp. W~środowisku akademickim wiele prac nad deidentyfikacją tekstu skupiało
się z~kolei na danych medycznych @Carrell2013.

Narzędzia te, choć dojrzałe i~szeroko stosowane, ujawniają ograniczenia w~zastosowaniu do
polskich umów cywilnoprawnych. Pierwszym z~nich jest niepełne pokrycie polskich identyfikatorów.
Presidio rozpoznaje wprawdzie numer PESEL, lecz spośród charakterystycznych dla polskiego obrotu
prawnego identyfikatorów nie obejmuje numerów NIP ani REGON @presidio. Podobnie Google Cloud
Sensitive Data Protection wykrywa numer PESEL, numer paszportu oraz numer dowodu osobistego,
jednak także w~tym przypadku brakuje numerów NIP oraz REGON @gcpdlp. Tymczasem dane te regularnie
pojawiają się w~umowach zawieranych przez przedsiębiorców, co czyni tę lukę istotną z~praktycznego
punktu widzenia.

Drugim ograniczeniem jest jakość rozpoznawania encji ogólnych, takich jak imiona, nazwiska czy
adresy. Zależy ona od użytego modelu językowego, a~uzyskanie dobrych wyników dla polszczyzny
wymaga podłączenia modelu wytrenowanego dla tego języka i~radzącego sobie z~omówioną wcześniej
fleksją. Trzecim, dotyczącym rozwiązań komercyjnych, jest sam charakter usługi chmurowej:
przesłanie dokumentu do zewnętrznego dostawcy w~celu wykrycia danych odtwarza omówiony już
wcześniej problem wyprowadzania informacji poza organizację (zob. @ch:prywatnosc).
Wreszcie choć dla języka polskiego istnieją publicznie dostępne zasoby i~narzędzia do
rozpoznawania encji @Marcinczuk2019, mają one charakter ogólny i~nie są przystosowane do
specyfiki polskich umów cywilnoprawnych.

Zestawienie tych ograniczeń uzasadnia potrzebę opracowania dedykowanego rozwiązania. Żadne
z~istniejących narzędzi nie łączy bowiem rozpoznawania pełnego zakresu polskich danych
identyfikujących z~odwracalnym podstawianiem realistycznych danych syntetycznych oraz z~lokalnym
przechowywaniem mapowania, dzięki któremu rzeczywiste dane nie opuszczają infrastruktury
organizacji. Połączenie tych elementów w~jednej warstwie pośredniej, działającej jako gateway
przed wysłaniem zapytania do modelu językowego, stanowi przedmiot projektu przedstawionego
w~kolejnym rozdziale (@ch:projekt).
