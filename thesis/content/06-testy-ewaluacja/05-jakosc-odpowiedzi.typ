#import "../../utils.typ": todo, silentheading, flex-caption

== Wpływ pseudonimizacji na jakość odpowiedzi <sec:eval-jakosc>

#todo[Pytanie badawcze: czy realistyczna pseudonimizacja zachowuje użyteczność analityczną LLM i czy
realizm substytutu ma znaczenie. Metoda: trzy ramiona (A oryginał, B brama z realistycznym
zamiennikiem, D abstrakcyjne tokeny), model lokalny qwen2.5:3b, metryka faktograficzna (obecność
wartości gold) oraz ROUGE-L (nazwane bez cytatu). Dwa eksperymenty (===): przezroczystość A/B na 20
umowach (B≈A, 0,942 vs 0,925) oraz znaczenie realizmu A/B/D na 5 umowach (B≫D, 1,0 vs 0,467).
Wnioski: realizm konieczny, spadek PESEL to ograniczenie modelu (A=B), ROUGE-L nieadekwatny.
Walidacja realistycznej substytucji z rozdz. 4 (sec:dane-zastepcze). Charakter prototypu.]

=== Przezroczystość pseudonimizacji

#todo[Eksperyment A/B na 20 umowach (n=60): B≈A.]

=== Znaczenie realizmu substytutu

#todo[Eksperyment A/B/D na 5 umowach (n=15): B≫D mimo pełnej odwracalności obu ramion.]
