#import "../../utils.typ": todo, silentheading, flex-caption

= Testy, ewaluacja i analiza wyników <ch:ewaluacja>
#todo[Rozdział do rozwinięcia — poniżej zakres z konspektu (docs/MasterThesisShorten.pdf).]

Rozdział szósty przedstawia metodologię testowania systemu oraz wyniki przeprowadzonej ewaluacji,
których celem jest ocena skuteczności zaprojektowanego rozwiązania oraz weryfikacja wpływu
pseudonimizacji na jakość odpowiedzi generowanych przez modele językowe. W rozdziale omówione
zostaną zarówno metody oceny skuteczności silnika pseudonimizacji, jak i analiza wpływu
zastosowanego procesu na użyteczność odpowiedzi modeli LLM w zadaniach związanych z analizą
polskich umów cywilnoprawnych.

W pierwszej części rozdziału przedstawiony zostanie sposób przygotowania zbioru testowego
obejmującego dokumenty zawierające kontrolowane dane osobowe, który posłuży do oceny jakości
wykrywania oraz pseudonimizacji informacji wrażliwych. Na tej podstawie przeprowadzona zostanie
ewaluacja silnika pseudonimizacji z wykorzystaniem standardowych metryk jakości, co pozwoli
określić skuteczność wykrywania poszczególnych typów danych osobowych oraz zidentyfikować
najczęściej występujące błędy.

Kolejna część rozdziału poświęcona zostanie ocenie wpływu pseudonimizacji na jakość odpowiedzi
modeli językowych w zadaniach analizy dokumentów. Porównane zostaną odpowiedzi generowane
na podstawie danych oryginalnych oraz danych poddanych pseudonimizacji, co pozwoli ocenić,
w jakim stopniu zastosowane mechanizmy ochrony danych wpływają na użyteczność uzyskiwanych
rezultatów. Uzupełnieniem ewaluacji będzie analiza wydajności działania systemu oraz weryfikacja
bezpieczeństwa procesu przetwarzania danych.
