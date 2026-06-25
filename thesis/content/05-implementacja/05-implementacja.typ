#import "../../utils.typ": todo, silentheading, flex-caption

= Implementacja systemu i stos technologiczny <ch:implementacja>

Rozdział piąty przedstawia implementację systemu gateway, którego architekturę zaprojektowano
w~rozdziale @ch:projekt. O~ile poprzedni rozdział określał strukturę rozwiązania na poziomie
koncepcyjnym, o~tyle celem niniejszego rozdziału jest pokazanie, w~jaki sposób poszczególne
komponenty tej architektury zostały zrealizowane w~praktyce, wraz z~uzasadnieniem konkretnych
decyzji technologicznych podjętych na tym etapie. Zgodnie z~przyjętym wcześniej założeniem
(zob. @sec:architektura) system wykonano jako usługę backendową udostępniającą interfejs
programistyczny, dlatego opis koncentruje się na warstwie serwerowej, a~zagadnienia interfejsu
użytkownika pozostają poza jego zakresem.

W~pierwszej części rozdziału przedstawiony zostanie stos technologiczny wykorzystany do budowy
systemu oraz ogólna organizacja kodu, w~szczególności oddzielenie logiki czystej od warstwy
odpowiedzialnej za komunikację z~zasobami zewnętrznymi. Następnie omówiona zostanie implementacja
silnika pseudonimizacji, na którą składają się wykrywanie polskich danych osobowych, generowanie
realistycznych danych zastępczych oraz magazyn odwracalnych mapowań, przechowujący powiązania
między danymi oryginalnymi a~syntetycznymi w~postaci zaszyfrowanej.

Kolejna część rozdziału poświęcona zostanie warstwie API oraz integracji z~zewnętrznymi dostawcami
modeli językowych, w~tym mechanizmowi kierowania żądań do różnych dostawców i~obsłudze sytuacji
błędnych. Rozdział zamykają zagadnienia konfiguracji, uruchomienia i~obserwowalności systemu,
a~także przyjęty sposób testowania i~zapewniania jakości kodu. Tak przedstawiona realizacja pozwala
prześledzić, w~jaki sposób wymagania i~projekt z~poprzednich rozdziałów przełożyły się na działające
oprogramowanie oraz jak współdziałają jego komponenty.

#include "01-stos-technologiczny.typ"
#include "02-wykrywanie.typ"
#include "03-generowanie.typ"
#include "04-magazyn.typ"
#include "05-api-dostawcy.typ"
#include "06-srodowisko.typ"
#include "07-testy.typ"
