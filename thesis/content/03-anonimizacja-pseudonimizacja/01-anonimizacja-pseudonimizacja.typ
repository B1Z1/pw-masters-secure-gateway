#import "../../utils.typ": todo, silentheading, flex-caption

== Anonimizacja a pseudonimizacja danych <sec:anon-pseudo>

Ochrona danych osobowych w~treści zapytania sprowadza się do przekształcenia jej w~taki sposób,
aby usunąć informacje pozwalające powiązać tekst z~konkretną osobą, a~jednocześnie zachować na
tyle dużo treści, by pozostała ona użyteczna dla modelu. Ogólny proces usuwania związku między
zbiorem danych a~osobą, której one dotyczą, określa się mianem deidentyfikacji (ang.
_de-identification_) @Garfinkel2015. Aby mówić o~nim precyzyjnie, trzeba najpierw rozróżnić
rodzaje informacji, które ten związek tworzą. Identyfikatory bezpośrednie (ang.
_direct identifiers_) to dane jednoznacznie wskazujące osobę, takie jak imię i~nazwisko, adres,
numer telefonu czy numer rachunku bankowego. Quasi-identyfikatory (ang.
_quasi-identifiers_) same w~sobie nie pozwalają na identyfikację, lecz prowadzą do niej
w~połączeniu z~innymi danymi i~wiedzą zewnętrzną, jak płeć, narodowość czy miejsce zamieszkania
@Lison2021.
To rozróżnienie jest istotne, ponieważ samo usunięcie identyfikatorów bezpośrednich
często nie wystarcza, by dane przestały być możliwe do przypisania konkretnej osobie. Dokumenty
takie jak umowy cywilnoprawne są przy tym gęsto wypełnione identyfikatorami obu rodzajów, co
czyni problem szczególnie wyrazistym.

Na gruncie tak rozumianej deidentyfikacji rysuje się różnica między anonimizacją
a~pseudonimizacją. Anonimizacja oznacza trwałe i~nieodwracalne usunięcie związku między danymi
a~osobą; po jej przeprowadzeniu ponowna identyfikacja nie jest już możliwa @Garfinkel2015.
Pseudonimizacja polega natomiast na zastąpieniu identyfikatorów bezpośrednich pseudonimami
w~sposób, który zachowuje możliwość odwrócenia tego procesu. Jak ujmuje to raport NIST,
pseudonimizację można w~prosty sposób odwrócić, jeśli podmiot, który ją przeprowadził,
przechowuje tablicę wiążącą pierwotne tożsamości z~pseudonimami, albo jeśli podstawienie wykonano
algorytmem, którego parametry są znane. Kluczowa różnica nie leży więc w~samym
podstawieniu danych, lecz w~tym, czy zachowano środek umożliwiający jego cofnięcie.

Tym środkiem jest zwykle tajny klucz albo tablica mapująca przechowywana po stronie podmiotu
dokonującego pseudonimizacji. W~zależności od użytej techniki odwzorowanie między daną a~jej
pseudonimem może opierać się na liczniku, generatorze liczb losowych, kodzie uwierzytelniającym
wiadomość lub szyfrowaniu symetrycznym; w~każdym z~tych przypadków odtworzenie pierwotnej
wartości jest niemożliwe bez znajomości sekretu, a~bezpieczeństwo całego rozwiązania sprowadza
się do ochrony tablicy mapującej @ENISA2021. Pseudonimizacja jest przy tym uznaną i~ugruntowaną
metodą ochrony danych, do której wprost odwołuje się RODO, traktując ją jako jedno
z~zabezpieczeń. Pytanie o~to, jak rygorystycznie zmierzyć stopień, w~jakim dane pozostają anonimowe,
prowadzi natomiast do formalnych modeli prywatności, którym poświęcono kolejny podrozdział
(@sec:modele-prywatnosci).

W~projektowanym systemie wybór pada na pseudonimizację, a~nie anonimizację, i~wynika on wprost
z~jego zadania. Gateway nie tylko wykrywa i~zastępuje dane osobowe przed wysłaniem zapytania do
modelu, lecz także przywraca pierwotne wartości w~odpowiedzi, którą model odsyła. Operacja
przywrócenia jest możliwa tylko wtedy, gdy zachowana zostaje tablica mapująca pierwotne dane na
ich syntetyczne odpowiedniki, a~przechowywanie tej tablicy jest właśnie tym, co definiuje proces
jako pseudonimizację. Z~perspektywy prawnej dane przetwarzane w~ten sposób pozostają danymi osobowymi, ponieważ
istnieje możliwość ich odtworzenia (zob. @sec:regulacje).
Warto jednak zauważyć, że tablica mapująca nigdy nie opuszcza infrastruktury organizacji: do
zewnętrznego dostawcy trafiają wyłącznie pseudonimy, a~bez dostępu do sekretu nie jest on
w~stanie powiązać ich z~rzeczywistymi osobami. W~rezultacie z~punktu widzenia dostawcy modelu
przekazane dane pełnią funkcję anonimowych, mimo że w~ramach całego systemu proces pozostaje
pseudonimizacją. To właśnie ta dwoistość, odwracalność po stronie organizacji i~nieodwracalność
po stronie odbiorcy, czyni pseudonimizację właściwym punktem wyjścia dla ochrony danych
w~komunikacji z~modelami językowymi.
