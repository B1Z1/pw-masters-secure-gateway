#import "../../utils.typ": todo, silentheading, flex-caption

== Skuteczność wykrywania i pseudonimizacji <sec:eval-detekcja>

#todo[Definicje miar: precyzja, czułość, F1, agregacja mikro/makro, polityka dopasowania spanów
(pokrycie vs dokładne granice). Tabela wyników per typ: czułość mikro 1,0, precyzja 0,887 (obniżana
przez DATE_TIME). Przewaga czułości nad precyzją widoczna w danych. Następnie analiza błędów
(===): telefon (konfiguracja Presidio leniency, pętla ewaluacja→poprawa, przed/po), nazwisko w linii
podpisu (kontekstowość modelu spaCy, recall-exact PERSON 0,969, koreferencja jako kierunek),
nadwykrywanie i nakładki dat (fragment „dniu DD." jako osobna data).]

=== Analiza błędów wykrywania

#todo[Trzy przyczyny wg warstwy systemu: telefon (konfiguracja), nazwisko (model), data (rekognizer).]
