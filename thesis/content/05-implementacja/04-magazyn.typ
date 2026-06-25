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

== Magazyn odwracalnych mapowań i szyfrowanie <sec:impl-magazyn>

Trzecim komponentem silnika pseudonimizacji jest magazyn odwracalnych mapowań. To w~nim zapisywane
są powiązania między danymi oryginalnymi a~syntetycznymi, co czyni proces odwracalnym oraz zapewnia
spójność zamienników w~obrębie sesji (zob. @sec:dane-zastepcze). W~ujęciu prawnym magazyn pełni rolę
„dodatkowych informacji", których oddzielne przechowywanie odróżnia pseudonimizację od anonimizacji
@gdpr2016. Zgodnie z~przyjętą architekturą tablica ta nigdy nie opuszcza wewnętrznej strony granicy
zaufania (zob. @sec:granica-zaufania).

Magazyn zbudowano na bazie Redis, szybkiego magazynu danych typu klucz-wartość przechowywanego
w~pamięci. Mapowania jednej sesji gromadzone są w~pojedynczej strukturze typu HASH, czyli zbiorze par
pole-wartość @redis. Takie ujęcie ma istotną zaletę: cała sesja podlega jednej operacji wygaśnięcia
oraz jednej operacji usunięcia, a~jej zawartość można odczytać jednym zapytaniem. Strukturę pól sesji
przedstawiono w~tabeli @tab:hash-sesji.

#figure(
  table(
    columns: (auto, 1fr),
    align: (left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Nazwa pola (jawna)*], [*Wartość (szyfrowana AES-256-GCM)*]),
    [`fwd:` HMAC(typ | oryginał)], [baza zamiennika],
    [`rev:` forma zamiennika], [oryginał, przypadek, typ encji],
    [`forms:` baza zamiennika], [mapa przypadek → forma zamiennika],
    [`corefs`], [lematy oryginałów i~bazy ich zamienników],
    [`meta`], [znaczniki czasu oraz liczniki sesji],
  ),
  caption: flex-caption(
    [Struktura HASH pojedynczej sesji: nazwy pól pozostają jawne (HMAC lub forma syntetyczna), a~dane oryginalne zapisane w~wartościach są szyfrowane.],
    [Struktura HASH sesji w~magazynie],
  ),
) <tab:hash-sesji>

Kluczowym wymaganiem bezpieczeństwa jest to, by poza pamięcią magazynu rzeczywiste dane osobowe nie
występowały w~postaci jawnej (zob. @sec:wymagania). Dlatego wartości pól zawierające dane oryginalne
szyfrowane są algorytmem AES-256-GCM, trybem zapewniającym jednocześnie poufność oraz integralność
danych, czyli uwierzytelnione szyfrowanie @nist80038d. Szyfrowaniu podlegają wyłącznie dane
oryginalne, natomiast wartości syntetyczne oraz nazwy pól pozostają jawne, gdyż same w~sobie nie
ujawniają informacji o~rzeczywistych osobach. Każda zaszyfrowana wartość zapisywana jest jako koperta
złożona z~jednorazowego wektora (nonce), szyfrogramu oraz znacznika uwierzytelniającego. Warstwę
szyfrującą przedstawiono na rysunku @rys:aes.

#codefig(
  "listings/aes_gcm.py",
  [Warstwa szyfrująca: AES-256-GCM nad 32-bajtowym kluczem oraz nadrzędny kodek pieczętujący obiekty JSON, przez który przechodzi każda wartość zapisywana w~magazynie.],
  [Warstwa szyfrująca AES-256-GCM],
) <rys:aes>

Szczególnej uwagi wymaga indeks służący do sprawdzenia, czy dana wartość była już podstawiana. Gdyby
kluczem takiego indeksu była wprost wartość oryginalna, pojawiłaby się ona w~nazwie pola, a~więc poza
zaszyfrowaną wartością. Aby tego uniknąć, nazwę pola indeksu wyprowadza się jako kluczowany skrót
HMAC-SHA256 z~typu encji oraz znormalizowanej postaci oryginału. HMAC jest kluczowaną funkcją skrótu
przeznaczoną do uwierzytelniania wiadomości @rfc2104, a~w~tym zastosowaniu jego istotną własnością
jest jednokierunkowość: z~nazwy pola nie sposób odtworzyć oryginału, a~mimo to ten sam oryginał zawsze
daje tę samą nazwę, co umożliwia jego odszukanie. Sposób wyznaczania klucza oraz nazwy pola
przedstawiono na rysunku @rys:hmac.

#codefig(
  "listings/hmac_index.py",
  [Indeks w~przód: znormalizowany klucz encji oraz nazwa pola jako jednokierunkowy skrót HMAC-SHA256, nieujawniający wartości oryginalnej.],
  [Wyznaczanie nazwy pola indeksu (HMAC)],
) <rys:hmac>

Spójność zamienników obejmuje również koreferencję, czyli rozpoznanie, że różne wzmianki odnoszą się
do tej samej osoby (zob. @sec:dane-zastepcze). Realizuje to osobny komponent, który porównuje lematy
nazw: jeżeli zbiór tokenów jednej wzmianki zawiera się w~zbiorze tokenów drugiej, uznaje je za
odnoszące się do tego samego bytu, na przykład „Andrzej Kamiński" oraz samo „Kamiński". Podejście jest
celowo zachowawcze: gdy wzmianka pasuje do więcej niż jednego znanego bytu, komponent nie zgaduje
i~traktuje ją jako nową osobę. Logikę tej decyzji przedstawiono na rysunku @rys:coref.

#codefig(
  "listings/coreference.py",
  [Rozstrzyganie koreferencji: zamiennik istniejącej osoby jest reużywany tylko przy jednoznacznym dopasowaniu lematu, w~przeciwnym razie powstaje nowa osoba.],
  [Rozstrzyganie koreferencji nazw],
) <rys:coref>

Przy tworzeniu nowego zamiennika magazyn dba o~jego niepowtarzalność, ponawiając generowanie, gdyby
wylosowana wartość kolidowała z~już użytą w~sesji. Osobnym zagadnieniem jest współbieżność: ponieważ
podstawienie obejmuje najpierw odczyt, a~następnie zapis, dwa równoległe żądania dotyczące tego samego
oryginału mogłyby wygenerować dwa różne zamienniki i~naruszyć spójność. Aby temu zapobiec, operacja
podstawienia wykonywana jest pod blokadą właściwą dla danej sesji, dzięki czemu żądania tej samej
sesji są szeregowane, a~różne sesje nadal przebiegają równolegle. Rozwiązanie działa w~obrębie
pojedynczego procesu, co odnotowano jako ograniczenie (zob. @sec:wymagania). Wejściowy punkt
podstawienia wraz z~blokadą przedstawiono na rysunku @rys:get-or-create.

#codefig(
  "listings/get_or_create.py",
  [Wejściowy punkt podstawienia: blokada właściwa dla sesji szereguje współbieżne żądania o~ten sam oryginał, chroniąc spójność zamienników.],
  [Podstawienie pod blokadą sesji],
) <rys:get-or-create>

Przywracanie danych w~odpowiedzi modelu przebiega w~kierunku odwrotnym. Na podstawie indeksu
odwrotnego, którego kluczami są formy zamienników, w~tekście odnajdywane są wartości syntetyczne
i~zastępowane oryginałami, z~uwzględnieniem przypadka gramatycznego dla osób oraz miejscowości. Każda
operacja na sesji odświeża jej czas życia, dzięki czemu mapowania utrzymywane są jedynie przez czas
trwania aktywnej rozmowy, po czym są automatycznie usuwane.

Tak zaprojektowany magazyn zamyka silnik pseudonimizacji: dostarcza spójnych, odwracalnych
i~zaszyfrowanych mapowań, na których opierają się zarówno podstawianie, jak i~przywracanie danych.
Pozostaje pokazać, w~jaki sposób wszystkie omówione komponenty łączą się w~obsłudze pojedynczego
żądania oraz jak system komunikuje się z~zewnętrznymi dostawcami modeli, czemu poświęcono kolejny
podrozdział.
