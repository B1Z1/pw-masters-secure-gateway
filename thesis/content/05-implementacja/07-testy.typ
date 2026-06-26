#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

#let codefig(file, long, short) = figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read(file)))),
  ),
  caption: flex-caption(long, short),
  kind: image,
)

== Testowanie i zapewnianie jakości <sec:impl-testy>

Ostatnim elementem prac implementacyjnych jest weryfikacja poprawności systemu testami
automatycznymi. Implementację pokrywają testy jednostkowe oraz integracyjne,
obejmujące wszystkie komponenty silnika pseudonimizacji oraz warstwy API. Przyjęto przy tym zasadę,
że testy nie wymagają dostępu do sieci ani zewnętrznych usług, dzięki czemu są szybkie, powtarzalne
i~niezależne od środowiska. Zależności zewnętrzne zastępowane są w~testach atrapami: magazyn Redis
przez jego implementację działającą w~pamięci (fakeredis), biblioteki klienckie dostawców przez
obiekty imitujące ich zachowanie, a~całego dostawcę modelu, na potrzeby testów obiegu, przez
deterministyczny komponent zwracający przekazaną treść, przedstawiony na rysunku @rys:echo. Możliwość
takiej podmiany wynika wprost z~przyjętego podziału na logikę czystą i~warstwę wejścia-wyjścia
(zob. @sec:stos-technologiczny).

#codefig(
  "listings/echo_provider.py",
  [Deterministyczny dostawca zastępczy do testów obiegu: zwraca treść ostatniej wiadomości użytkownika, bez kontaktu z~modelem.],
  [Zastępczy dostawca modelu do testów],
) <rys:echo>

Testy zorganizowano według komponentów systemu, co przedstawiono w~tabeli @tab:testy. Logika czysta,
to jest wykrywanie, generowanie danych zastępczych oraz obliczanie sum kontrolnych i~odmiana, testowana
jest w~izolacji, bez ładowania modelu językowego ani uruchamiania bazy danych. Komponenty wymagające
stanu, takie jak magazyn mapowań czy potok anonimizacji, korzystają z~magazynu działającego
w~pamięci, a~warstwa dostawców z~imitacji ich bibliotek. Determinizm tam, gdzie generowane są wartości
losowe, zapewnia inicjowanie generatora ustalonym ziarnem.

#figure(
  table(
    columns: (auto, 1fr, auto),
    align: (left, left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Obszar*], [*Zakres testów*], [*Sposób (bez sieci)*]),
    [`pii_detection`], [rozpoznawacze, sumy kontrolne, progi, nakładanie encji], [regex i~sumy bez modelu],
    [`pseudonym_generation`], [buildery, fleksja, identyfikatory], [logika czysta, ziarno],
    [`pseudonym_vault`], [szyfrowanie, koreferencja, kolizje, TTL], [fakeredis],
    [`pipeline`], [obieg podstawienie–przywracanie], [fakeredis + stub modelu],
    [`llm_providers`], [router, adaptery, mapowanie błędów], [mockowane SDK],
    [API czatu], [walidacja, kody błędów, brak danych osobowych], [klient testowy],
  ),
  caption: flex-caption(
    [Organizacja testów według komponentów systemu wraz ze sposobem zastąpienia zależności zewnętrznych.],
    [Organizacja testów automatycznych],
  ),
) <tab:testy>

Testy uruchamiane są frameworkiem pytest wraz z~rozszerzeniem do obsługi kodu asynchronicznego,
a~ich wykonanie raportuje pokrycie kodu, w~tym pokrycie gałęzi decyzyjnych. Szczególną rolę pełnią
testy o~charakterze regresyjnym, strzegące stabilności formatu danych zapisywanych w~magazynie.
Format ten, obejmujący układ pól sesji oraz postać koperty szyfrującej (zob. @sec:impl-magazyn),
traktowany jest jako kontrakt: jego niezamierzona zmiana uniemożliwiłaby odczytanie mapowań zapisanych
wcześniej, dlatego testy te wychwytują takie zmiany.

Należy podkreślić, że opisane testy weryfikują poprawność implementacji poszczególnych komponentów,
nie zaś skuteczność samej pseudonimizacji, rozumianą jako trafność wykrywania danych osobowych czy
wpływ procesu na jakość odpowiedzi modelu. Tej ostatniej, opartej na osobnym zbiorze testowym oraz
miarach jakości, poświęcono kolejny rozdział (zob. @ch:ewaluacja). Tym samym zamyka się opis
implementacji systemu, obejmujący stos technologiczny, silnik pseudonimizacji, warstwę API oraz
środowisko uruchomieniowe.
