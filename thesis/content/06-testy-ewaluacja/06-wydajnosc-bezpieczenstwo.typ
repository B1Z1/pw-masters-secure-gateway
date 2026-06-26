#import "../../utils.typ": todo, silentheading, flex-caption

== Wydajność i bezpieczeństwo przetwarzania <sec:eval-wydajnosc>

#todo[Część o wydajności i część o bezpieczeństwie, każda jako ===.]

=== Wydajność

#todo[Potok synchroniczny (bez strumieniowania, uzasadnione w sec:wymagania). Percentyle czasu:
total p50 ~85 ms, p99 ~106 ms. Dominuje detekcja/NER (~65 ms), dalej generowanie zamienników,
zapis do magazynu, przywracanie. Jednokrotne ładowanie modelu (sec:impl-srodowisko). Korpus
jednorodny (1500–2999 znaków, 15–29 encji) — liczby orientacyjne, zależne od maszyny. Tabela:
percentyle czasu wg kanału.]

=== Bezpieczeństwo przetwarzania

#todo[Metoda audytu wycieków: skan tekstu wychodzącego po ocalałych oryginałach, maskowanie
zadeklarowanych fałszywek, dedup po pozycji, gold jako jedyna wyrocznia. Wynik: 2 wycieki (nazwiska
z analizy błędów), telefony już szczelne. Etap 2 (Echo) potwierdza szczelność pełnego obiegu
(54 z 56 dokumentów). Tryb offline. Powiązanie z zasadą „żadne PII nie wychodzi w oryginale" i
minimalizacją danych (sec:wymagania). Akapit zamykający — most do rozdz. 7.]
