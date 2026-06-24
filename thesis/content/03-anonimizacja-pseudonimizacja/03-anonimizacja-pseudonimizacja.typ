#import "../../utils.typ": todo, silentheading, flex-caption

= Anonimizacja i pseudonimizacja danych w systemach AI <ch:anonimizacja>
#todo[Rozdział do rozwinięcia — poniżej zakres z konspektu (docs/MasterThesisShorten.pdf).]

Rozdział trzeci przedstawia podstawy teoretyczne oraz przegląd rozwiązań związanych z ochroną
danych osobowych w systemach wykorzystujących modele językowe. Omówione zostaną kluczowe
pojęcia oraz techniki stosowane w procesie zabezpieczania danych, ze szczególnym uwzględnieniem
metod istotnych z perspektywy projektowanego systemu gateway. Celem rozdziału jest przedstawienie
istniejących podejść do pseudonimizacji danych osobowych oraz wskazanie narzędzi i metod,
które mogą zostać wykorzystane do ochrony informacji przekazywanych do zewnętrznych modeli
językowych.

W pierwszej części rozdziału omówiona zostanie różnica pomiędzy anonimizacją a pseudonimizacją
danych osobowych. Przedstawione zostanie, że anonimizacja polega na trwałym usunięciu możliwości
identyfikacji osoby, natomiast pseudonimizacja umożliwia odwrócenie procesu dzięki zastosowaniu
odpowiednich mechanizmów mapowania danych. Wyjaśnione zostanie również, dlaczego projektowany
system opiera się na pseudonimizacji, mimo że w szerszym ujęciu proces ten pełni funkcję
anonimizującą w komunikacji z modelami językowymi.

Następnie zaprezentowane zostaną wybrane techniki maskowania danych osobowych, takie jak
podstawianie danych syntetycznych, tokenizacja oraz usuwanie danych. Szczególna uwaga zostanie
poświęcona metodzie zastępowania danych realistycznymi wartościami syntetycznymi, która pozwala
zachować kontekst i strukturę dokumentu, a tym samym ograniczyć wpływ procesu pseudonimizacji
na jakość odpowiedzi generowanych przez model językowy.

Istotnym elementem rozdziału będzie również omówienie metod rozpoznawania encji nazwanych
(NER, ang. _Named Entity Recognition_), wykorzystywanych do identyfikacji danych osobowych
w tekście. Przedstawione zostaną wyzwania związane z przetwarzaniem języka polskiego, a także
narzędzia wykorzystane w projektowanym rozwiązaniu, w tym framework Microsoft Presidio oraz
modele językowe wspierające rozpoznawanie polskich encji. Pozwoli to uzasadnić wybór technologii
zastosowanych w projektowanym systemie.

W końcowej części rozdziału omówione zostaną regulacje prawne oraz istniejące rozwiązania
techniczne związane z ochroną danych osobowych w systemach AI. Analiza ta pozwoli wskazać
ograniczenia obecnych narzędzi w zakresie obsługi polskich danych osobowych oraz uzasadnić
potrzebę opracowania rozwiązania przedstawionego w niniejszej pracy.
