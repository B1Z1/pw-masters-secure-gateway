#import "../../utils.typ": todo, silentheading, flex-caption

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

Takie podejście wprost odpowiada na omówione zagrożenia. Skoro dostawca otrzymuje jedynie dane
syntetyczne, ich ewentualne zarejestrowanie, wykorzystanie do trenowania modelu czy zapamiętanie
nie prowadzi do ujawnienia rzeczywistych informacji o~osobach. Jednocześnie ograniczenie
zakresu przekazywanych danych realizuje zasadę minimalizacji i~zmniejsza ryzyko związane
z~transferem danych do państw trzecich. Zachowanie spójnego odwzorowania danych pozwala przy tym
utrzymać kontekst dokumentu, a~tym samym użyteczność odpowiedzi modelu. Sposób, w~jaki dane
osobowe można wykrywać i~zastępować, oraz techniki leżące u~podstaw takiego rozwiązania omówiono
w~kolejnym rozdziale (@ch:anonimizacja), natomiast architekturę i~projekt samego systemu
przedstawiono w~rozdziale poświęconym jego budowie (@ch:projekt).
