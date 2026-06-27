#import "../../utils.typ": todo, silentheading, flex-caption

= Projekt bezpiecznego gatewaya do anonimizacji danych <ch:projekt>

Zagrożenia, wymagania prawne oraz techniczne podstawy pseudonimizacji omówione w~poprzednich
rozdziałach określają, czego wymaga się od rozwiązania, nie wskazują jednak, w~jaki sposób je
zbudować. Niniejszy rozdział przedstawia projekt architektury gatewaya, czyli warstwy
pośredniczącej między użytkownikiem a~zewnętrznym modelem językowym, której zadaniem jest wykrycie
danych osobowych w~zapytaniu, zastąpienie ich realistycznymi danymi syntetycznymi przed wysłaniem
oraz przywrócenie wartości oryginalnych w~odpowiedzi. Najpierw określono wymagania funkcjonalne
i~niefunkcjonalne, przekładające wcześniejszą analizę na konkretne właściwości oprogramowania.
Następnie zarysowano wysokopoziomową architekturę systemu, wyróżniając jego komponenty oraz ich
odpowiedzialności i~organizując całość wokół granicy zaufania, po czym prześledzono przepływ danych
w~obiegu żądanie–odpowiedź, w~którym dane dwukrotnie przekraczają tę granicę. Kolejno omówiono
strategię doboru realistycznych danych zastępczych, dbającą o~spójność i~odwracalność zamienników,
a~rozdział zamyka projekt warstwy komunikacji z~dostawcami modeli, umożliwiającej obsługę wielu
z~nich bez modyfikowania pozostałych komponentów. Tak zaprojektowany system stanowi podstawę
implementacji przedstawionej w~dalszej części pracy.

#include "01-wymagania.typ"
#include "02-architektura.typ"
#include "03-przeplyw-danych.typ"
#include "04-dane-zastepcze.typ"
#include "05-dostawcy-llm.typ"
