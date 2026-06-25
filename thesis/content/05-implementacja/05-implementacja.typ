#import "../../utils.typ": todo, silentheading, flex-caption

= Implementacja systemu i stos technologiczny <ch:implementacja>

Rozdział piąty przedstawia implementację kluczowych komponentów systemu gateway, opisując
sposób realizacji założeń projektowych określonych w poprzednim rozdziale. Omówione zostaną
decyzje dotyczące wyboru technologii oraz implementacja mechanizmów odpowiedzialnych za
pseudonimizację danych, komunikację z modelami językowymi, zarządzanie sesją oraz obsługę
interfejsu użytkownika. Celem rozdziału jest przedstawienie praktycznej realizacji zaprojektowanej
architektury oraz uzasadnienie zastosowanych rozwiązań technologicznych.

W pierwszej części rozdziału zaprezentowany zostanie stos technologiczny wykorzystany do
budowy systemu wraz z uzasadnieniem wyboru narzędzi zastosowanych w warstwie backendowej,
mechanizmach rozpoznawania danych osobowych, przechowywaniu mapowań oraz warstwie interfejsu
użytkownika. Pozwoli to przedstawić, w jaki sposób wymagania funkcjonalne i niefunkcjonalne
zostały odwzorowane w konkretnych rozwiązaniach technologicznych.

Centralnym elementem rozdziału będzie opis implementacji silnika pseudonimizacji odpowiedzialnego
za wykrywanie i zastępowanie danych osobowych w treści zapytań użytkownika. Omówione zostaną
mechanizmy rozpoznawania polskich danych identyfikacyjnych, sposób generowania danych
zastępczych oraz rozwiązania zapewniające zachowanie spójności mapowań w ramach sesji.
Przedstawiona zostanie również implementacja warstwy API umożliwiającej komunikację pomiędzy
użytkownikiem a zewnętrznymi modelami językowymi oraz mechanizmy integracji z różnymi
dostawcami modeli LLM.

W końcowej części rozdziału opisane zostaną rozwiązania związane z przechowywaniem danych
sesyjnych, obsługą interfejsu użytkownika oraz konfiguracją środowiska uruchomieniowego.
Umożliwi to przedstawienie kompletnej implementacji systemu oraz sposobu współdziałania
wszystkich jego komponentów.
