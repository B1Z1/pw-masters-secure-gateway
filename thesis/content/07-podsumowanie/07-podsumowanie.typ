#import "../../utils.typ": todo, silentheading, flex-caption

= Podsumowanie i wnioski <ch:podsumowanie>

Celem pracy było zaprojektowanie i~implementacja systemu gateway proxy, który wykrywa dane osobowe
w~treści zapytania, zastępuje je realistycznymi danymi syntetycznymi przed wysłaniem do modelu
językowego, a~następnie przywraca wartości pierwotne w~wygenerowanej odpowiedzi (zob. @ch:wstep).
Cel ten udało się osiągnąć: powstał działający system, który pseudonimizuje dane na wartości fałszywe,
lecz czytelne dla człowieka i~zachowujące strukturę dokumentu, a~zarazem odwraca ten proces,
zwracając użytkownikowi odpowiedź odnoszącą się do rzeczywistych osób oraz dokumentów.

Postawione pytanie badawcze dotyczyło tego, w~jakim stopniu pseudonimizacja wpływa na jakość
odpowiedzi modeli językowych w~analizie polskich umów cywilnoprawnych. Ewaluacja (zob. @ch:ewaluacja)
pozwala odpowiedzieć na nie dwojako. Po pierwsze, ochrona jest szczelna, gdyż czułość wykrywania
mierzona w~skali mikro wynosi 1,0, a~na poziomie pojedynczych encji dokładnie odtworzono 87% wartości,
niemal 100% po wyłączeniu dat (zob. @sec:eval-detekcja, @sec:eval-odtworzenie). Po drugie,
pseudonimizacja okazała się dla faktografii przezroczysta, ponieważ średni udział poprawnych wartości
w~odpowiedzi wyniósł 0,942 dla bramy wobec 0,925 dla oryginału, a~więc różnica mieści się w~granicach
szumu (zob. @sec:eval-jakosc). Dla zadań faktograficznych zastosowanie pseudonimizacji nie pogarsza
zatem jakości odpowiedzi w~stopniu mierzalnym, a~ochrona prywatności nie odbywa się tu kosztem
użyteczności.

Ewaluacja przyniosła też wniosek dotyczący samej postaci danych zastępczych. Przewaga realistycznego
zamiennika nad abstrakcyjnymi tokenami była wyraźna jedynie na słabym modelu lokalnym, natomiast
na modelach znacznie silniejszych całkowicie zanikła. Na dostatecznie mocnym modelu nie ma więc
znaczenia, czy dane podstawione są realistyczne, czy stanowią jedynie rozróżnialne identyfikatory,
ponieważ model wiernie przepisuje jedne i~drugie. Realistyczna substytucja pozostaje jednak wyborem
najbezpieczniejszym dla systemu niezależnego od dostawcy modelu, gdyż zachowuje użyteczność w~pełnym
zakresie modeli, od małych po duże.

Rozwiązanie ma swoje ograniczenia, które wyznaczają zarazem kierunki dalszych prac. Najpoważniejsze
dotyczy dat, których nadmiarowe wykrywanie obniża precyzję i~psuje odwracalność (zob.
@sec:eval-detekcja), a~druga oś ewaluacji, dotycząca rozumowania, pozostała nierozstrzygnięta wobec
nieadekwatności miary ROUGE-L. Wyniki mają ponadto charakter prototypowy, oparty na korpusie
syntetycznym oraz zadaniach faktograficznych. Naturalnym rozszerzeniem jest udostępnienie systemu
użytkownikowi końcowemu w~postaci własnego interfejsu czatu
z~możliwością wyboru modelu, a~także dodanie obsługi kolejnych dostawców modeli językowych. Dalsze
prace obejmują również poprawę obsługi dat oraz odtwarzanie uciętych nazwisk na podstawie koreferencji.
