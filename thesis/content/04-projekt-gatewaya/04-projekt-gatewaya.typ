#import "../../utils.typ": todo, silentheading, flex-caption

= Projekt bezpiecznego gatewaya do anonimizacji danych <ch:projekt>

Rozdział czwarty przedstawia projekt architektury systemu gateway do pseudonimizacji danych
osobowych, stanowiąc przejście pomiędzy analizą teoretyczną a~implementacją rozwiązania opisaną
w~dalszej części pracy. W~rozdziale określone zostaną wymagania funkcjonalne i~niefunkcjonalne
systemu oraz zaprezentowana zostanie architektura rozwiązania obejmująca komponenty odpowiedzialne
za wykrywanie danych osobowych, ich pseudonimizację, komunikację z~zewnętrznymi modelami
językowymi oraz przywracanie danych w~odpowiedziach.

W~pierwszej części omówione zostaną wymagania funkcjonalne związane z~automatycznym
wykrywaniem i~pseudonimizacją danych osobowych, obsługą wielu dostawców modeli językowych
oraz zachowaniem spójności danych w~ramach sesji użytkownika. Przedstawione zostaną również
wymagania niefunkcjonalne obejmujące bezpieczeństwo, modularność oraz wydajność rozwiązania.

Następnie zaprezentowana zostanie wysokopoziomowa architektura systemu oraz przepływ danych
pomiędzy jego głównymi komponentami, od momentu odebrania żądania użytkownika, przez proces
pseudonimizacji danych, aż do wygenerowania odpowiedzi i~przywrócenia oryginalnych informacji.
Omówiona zostanie także strategia generowania danych zastępczych, której celem jest zachowanie
spójności i~kontekstu przetwarzanych dokumentów. Rozdział zamyka projekt warstwy odpowiedzialnej
za komunikację z~zewnętrznymi dostawcami modeli językowych, umożliwiającej korzystanie z~wielu
z~nich bez modyfikacji pozostałych komponentów. Uzupełnieniem rozdziału będą diagramy
architektoniczne przedstawiające strukturę systemu oraz zależności pomiędzy jego komponentami.

#include "01-wymagania.typ"
#include "02-architektura.typ"
#include "03-przeplyw-danych.typ"
#include "04-dane-zastepcze.typ"
#include "05-dostawcy-llm.typ"
