#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Uzasadnienie potrzeby anonimizującej warstwy pośredniej <sec:uzasadnienie>

Przedstawione zagrożenia oraz wymagania prawne prowadzą do wniosku, że bezpośrednie
przekazywanie danych osobowych do zewnętrznych modeli językowych jest zarówno ryzykowne, jak
i~prawnie ograniczone. Z~jednej strony sam model może utrwalić i~później ujawnić przekazane
informacje (zob. @sec:memorization), a~infrastruktura dostawcy naraża je na rejestrowanie,
ponowne wykorzystanie oraz ataki (zob. @sec:ryzyka-api). Z~drugiej strony RODO nakłada na
podmiot przekazujący dane szereg obowiązków, w~tym zasadę minimalizacji oraz ograniczenia
dotyczące transferu danych poza Europejski Obszar Gospodarczy (zob. @sec:regulacje). Rezygnacja
z~modeli zewnętrznych pozwoliłaby uniknąć tych problemów, oznaczałaby jednak utratę dostępu do
najbardziej zaawansowanych narzędzi, co w~wielu zastosowaniach jest nie do przyjęcia.

Rozwiązaniem tego konfliktu jest wprowadzenie pośredniczącej warstwy anonimizującej, która
przejmuje kontrolę nad danymi, zanim opuszczą one infrastrukturę organizacji. Warstwa taka,
działająca jako _gateway_, automatycznie wykrywa dane osobowe w~treści zapytania, zastępuje je
realistycznymi danymi syntetycznymi przed wysłaniem do modelu, a~następnie przywraca pierwotne
wartości w~wygenerowanej odpowiedzi. Dzięki temu poza granicę zaufania trafia wyłącznie tekst
pozbawiony rzeczywistych danych identyfikujących, podczas gdy odwzorowanie między wartościami
oryginalnymi a~zastępczymi pozostaje wewnątrz systemu kontrolowanego przez organizację.
Działanie takiej warstwy przedstawiono na rysunku @rys:gateway.

#figure(
  diagram(
    spacing: (24mm, 15mm),
    node-stroke: 0.6pt,
    node-corner-radius: 3pt,
    node((0, 0), [Użytkownik], name: <u>),
    node((1, 0), [Gateway\ #text(size: 0.72em, fill: gray.darken(40%))[wykrywanie\ i~podstawianie PII]], name: <g>),
    node((2, 0), [Model LLM\ #text(size: 0.72em, fill: gray.darken(40%))[dostawca]], name: <m>),
    node((1, 1.25), [#text(size: 0.76em)[magazyn mapowań]], stroke: (dash: "dotted"), name: <map>),
    edge(<g>, <map>, "<->", stroke: gray),
    edge(<u>, <g>, "->", [#text(size: 0.82em)[1.~dane osobowe]], bend: 30deg),
    edge(<g>, <m>, "->", [#text(size: 0.82em)[2.~dane syntetyczne]], bend: 30deg),
    edge(<m>, <g>, "->", [#text(size: 0.82em)[3.~dane syntetyczne]], bend: 30deg),
    edge(<g>, <u>, "->", [#text(size: 0.82em)[4.~dane oryginalne]], bend: 30deg),
    edge((1.5, -1.05), (1.5, 1.6), stroke: (dash: "dashed", paint: gray)),
    node((1.5, -1.25), text(size: 0.74em, fill: gray.darken(40%))[granica zaufania], stroke: none),
  ),
  caption: flex-caption(
    [Działanie pośredniczącej warstwy anonimizującej (gateway).],
    [Działanie gatewaya pseudonimizującego],
  ),
) <rys:gateway>

Takie podejście wprost odpowiada na omówione zagrożenia. Skoro dostawca otrzymuje jedynie dane
syntetyczne, ich ewentualne zarejestrowanie, wykorzystanie do trenowania modelu czy zapamiętanie
nie prowadzi do ujawnienia rzeczywistych informacji o~osobach. Jednocześnie ograniczenie
zakresu przekazywanych danych realizuje zasadę minimalizacji i~zmniejsza ryzyko związane
z~transferem danych do państw trzecich. Zachowanie spójnego odwzorowania danych pozwala przy tym
utrzymać kontekst dokumentu, a~tym samym użyteczność odpowiedzi modelu. Sposób, w~jaki dane
osobowe można wykrywać i~zastępować, oraz techniki leżące u~podstaw takiego rozwiązania omówiono
w~kolejnym rozdziale (@ch:anonimizacja), natomiast architekturę i~projekt samego systemu
przedstawiono w~rozdziale poświęconym jego budowie (@ch:projekt).
