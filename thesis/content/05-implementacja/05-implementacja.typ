#import "../../utils.typ": todo, silentheading, flex-caption

= Implementacja systemu i stos technologiczny <ch:implementacja>

Zaprojektowana w~rozdziale @ch:projekt architektura określa strukturę rozwiązania na poziomie
koncepcyjnym, nie przesądza jednak, w~jaki sposób poszczególne jej komponenty zrealizować
w~praktyce. Niniejszy rozdział przedstawia implementację gatewaya wraz z~uzasadnieniem decyzji
technologicznych podjętych na tym etapie. Zgodnie z~przyjętym wcześniej założeniem
(zob. @sec:architektura) system wykonano jako usługę backendową udostępniającą interfejs
programistyczny, dlatego opis koncentruje się na warstwie serwerowej, a~zagadnienia interfejsu
użytkownika pozostają poza jego zakresem. Najpierw omówiono stos technologiczny oraz organizację
kodu, w~szczególności oddzielenie logiki czystej od warstwy komunikującej się z~zasobami
zewnętrznymi. Następnie przedstawiono kolejne ogniwa silnika pseudonimizacji, czyli wykrywanie
polskich danych osobowych, generowanie realistycznych danych zastępczych oraz szyfrowany magazyn
odwracalnych mapowań. Kolejno opisano warstwę API oraz integrację z~dostawcami modeli językowych,
wraz z~mechanizmem kierowania żądań i~obsługą sytuacji błędnych, a~także konfigurację, uruchomienie
i~obserwowalność systemu. Rozdział zamyka opis sposobu testowania i~zapewniania jakości kodu. Tak
przedstawiona realizacja pozwala prześledzić, w~jaki sposób wymagania i~projekt z~poprzednich
rozdziałów przełożyły się na działające oprogramowanie oraz jak współdziałają jego komponenty.

#include "01-stos-technologiczny.typ"
#include "02-wykrywanie.typ"
#include "03-generowanie.typ"
#include "04-magazyn.typ"
#include "05-api-dostawcy.typ"
#include "06-srodowisko.typ"
#include "07-testy.typ"
