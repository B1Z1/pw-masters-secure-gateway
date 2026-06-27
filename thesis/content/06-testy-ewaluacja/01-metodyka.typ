#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Metodyka ewaluacji <sec:eval-metodyka>

Testy z~poprzedniego rozdziału (zob. @sec:impl-testy) potwierdzają poprawność implementacji, nie
mierzą jednak skuteczności pseudonimizacji na realistycznych dokumentach. Służy do tego osobne
narzędzie ewaluacyjne, które steruje uruchomioną bramą przez jej publiczny interfejs i~ocenia jej
odpowiedzi, nie zmieniając przy tym działania samego systemu. Podejście jest czarnoskrzynkowe (ang.
_black-box_): narzędzie obserwuje wyłącznie wyjścia bramy, a~jedynym źródłem prawdy o~tym, co~jest
daną osobową i~jaka jest jej pierwotna wartość, pozostaje niezależny wzorzec odniesienia (ang. _gold
standard_). Wyjścia bramy są w~tym ujęciu predykcjami poddawanymi ocenie, nigdy kluczem odpowiedzi.
Niezależność ta jest konieczna, gdyż przy ocenianiu systemu jego własnymi wykryciami pominięta encja
nie pojawiłaby się ani w~predykcjach, ani we~wzorcu, a~zatem jej wyciek pozostałby niewidoczny.

Pomiar prowadzony jest w~dwóch etapach. Etap pierwszy pomija model generatywny i~wywołuje wprost
operacje wykrywania, podstawienia oraz przywracania, dostarczając zasadniczych miar poprawności:
trafności wykrywania, wyniku audytu wycieków oraz wierności odtworzenia. Etap
drugi obejmuje pełny obieg konwersacyjny, w~którym dostawcę modelu zastępuje deterministyczna atrapa
zwracająca otrzymaną treść bez zmian (zob. @sec:impl-testy, @rys:echo). Potwierdza on szczelność
i~odwracalność zintegrowanego potoku, nie wiążąc pomiaru z~jakością konkretnego modelu.

Przepływ pojedynczego przebiegu przedstawiono na rysunku @rys:eval-harness. Tekst dokumentu trafia do
bramy, a~jej predykcje zestawiane są ze~wzorcem, który niezależnie zasila moduł oceny. Porównanie
obejmuje trzy aspekty: dopasowanie wykrytych encji do wzorca, przeszukanie tekstu wychodzącego pod
kątem ocalałych oryginałów oraz zgodność wartości przywróconych z~pierwotnymi.

#figure(
  diagram(
    spacing: (15mm, 11mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node((0, 0), [Korpus testowy\ #text(size: 0.72em, fill: gray.darken(40%))[tekst +\ encje wzorcowe]], name: <gold>),
    node((2, 0), [Brama\ #text(size: 0.72em, fill: gray.darken(40%))[żywe API:\ wykrywanie ·\ podstawienie ·\ przywracanie]], name: <gw>),
    node((4, 0), [Ocena\ #text(size: 0.72em, fill: gray.darken(40%))[wykrywanie ·\ audyt wycieków ·\ odtworzenie]], name: <score>),
    edge(<gold>, <gw>, "->", [tekst]),
    edge(<gw>, <score>, "->", [predykcje]),
    edge(<gold>, <score>, "->", [wzorzec\ (wyrocznia)], bend: -45deg),
  ),
  caption: flex-caption(
    [Przepływ czarnoskrzynkowej ewaluacji z~niezależnym wzorcem odniesienia.],
    [Przepływ czarnoskrzynkowej ewaluacji],
  ),
) <rys:eval-harness>

Całość przebiega w~trybie offline, bez kontaktu z~usługami zewnętrznymi, tak aby żaden dokument nie
opuszczał maszyny, zgodnie z~wymaganiem prywatności (zob. @sec:wymagania). Umożliwia to korpus
syntetyczny, opisany w~następnym podrozdziale, a~na zewnątrz trafiają wyłącznie zagregowane miary.
