#import "../../utils.typ": todo, silentheading, flex-caption

== Wpływ pseudonimizacji na jakość odpowiedzi <sec:eval-jakosc>

Druga oś ewaluacji dotyczy nie tego, czy dane są chronione, lecz czy po ich ochronie odpowiedź modelu
pozostaje użyteczna. Jako technikę maskowania danych wybrano w~tej pracy podstawianie realistycznych
wartości syntetycznych (zob. @ch:anonimizacja, @sec:dane-zastepcze). Niniejszy podrozdział sprawdza
dwie rzeczy: czy taka pseudonimizacja zachowuje wartość analityczną odpowiedzi w~porównaniu
z~wysłaniem oryginału, oraz czy sam realizm zamiennika w~ogóle ma znaczenie.

Badanie oparto na trzech ramionach, uruchamianych dla tych samych umów i~pytań. Ramię A wysyła do
modelu tekst oryginalny i~stanowi punkt odniesienia jakości. Ramię B to badane podejście, w~którym
tekst przechodzi przez bramę: dane są podstawiane realistycznym zamiennikiem, model odpowiada,
a~odpowiedź zostaje odpseudonimizowana. Ramię D zachowuje pełny, odwracalny obieg ramienia B, lecz
zamiast realistycznych wartości używa abstrakcyjnych, rozróżnialnych tokenów w~rodzaju `[OSOBA_1]`
czy `[PESEL_1]`, odmaskowywanych w~odpowiedzi. Zestawienie B i~D izoluje więc czysty efekt realizmu,
ponieważ oba ramiona mają identyczny mechanizm odwracania, a~różni je wyłącznie postać zamiennika.

Eksperymenty przeprowadzono najpierw na lokalnym modelu `qwen2.5:3b`, uruchamianym offline, spójnie
z~przyjętym dla całej ewaluacji trybem bez kontaktu z~siecią. Ponieważ korpus jest syntetyczny, ten
sam pomiar dało się następnie powtórzyć na modelach znacznie silniejszych, co~pozwoliło sprawdzić, na
ile wnioski zależą od siły modelu. Jakość mierzono dwojako. Faktografię, czyli obecność prawdziwych
wartości z~wzorca w~odpowiedzi, to jest osób, numerów PESEL oraz rachunków, oceniano obiektywnie przez
porównanie z~wzorcem. Rozumowanie, w~zadaniu streszczenia umowy, mierzono miarą ROUGE-L względem
odpowiedzi na oryginale. Przezroczystość zbadano na osobnej próbie 20 umów, a~pełne porównanie trzech ramion na większej
próbie 50 umów.

=== Przezroczystość pseudonimizacji

Pierwszy eksperyment porównuje ramię oryginalne z~bramą na osobnej próbie 20 umów. Wyniki faktograficzne
przedstawiono w~tabeli @tab:eval-jakosc-ab. Średni udział poprawnych wartości wynosi 0,942 dla bramy
wobec 0,925 dla oryginału, a~więc różnica mieści się w~granicach szumu, przy czym brama wypada nawet
minimalnie lepiej. Dla osób i~rachunków skuteczność jest praktycznie idealna. Pseudonimizacja jest
zatem dla faktografii przezroczysta: model widzi dane fałszywe, lecz po odpseudonimizacji odpowiedź
zawiera poprawne, prawdziwe wartości.

#figure(
  table(
    columns: (1fr, auto, auto),
    align: (left, right, right),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Pytanie*], [*A (oryginał)*], [*B (brama)*]),
    [osoby], [1,000], [1,000],
    [PESEL], [0,825], [0,825],
    [rachunek], [0,950], [1,000],
    [*średnia*], [*0,925*], [*0,942*],
  ),
  caption: flex-caption(
    [Faktografia odpowiedzi dla oryginału i~bramy (20 umów, udział poprawnych wartości z~wzorca).],
    [Przezroczystość pseudonimizacji dla faktografii],
  ),
) <tab:eval-jakosc-ab>

Pozornym wyjątkiem jest numer PESEL, którego udział spada do 0,825. Wartość ta jest jednak identyczna
w~ramieniu oryginalnym i~w~bramie, więc spadek nie wynika z~pseudonimizacji, lecz z~ograniczenia samego
modelu, który w~długim kontekście bywa, że gubi lub przekształca jedenastocyfrowy numer.

=== Znaczenie realizmu substytutu

Drugi eksperyment dodaje ramię z~abstrakcyjnymi tokenami i~obejmuje 50 umów. Na lokalnym modelu różnica
jest wyraźna: brama osiąga 1,0, podczas gdy ramię z~tokenami zaledwie 0,467, mimo że oba mają pełny,
odwracalny obieg. Sama odwracalność nie wystarcza tu więc do zachowania użyteczności.

Przyczyny porażek ramienia tokenowego widać w~surowych odpowiedziach modelu, jeszcze przed
odmaskowaniem. Po pierwsze, model przeformatowuje token, pisząc na przykład `NR_RACHUNKU_1` zamiast
`[NR_RACHUNKU_1]`, przez co deterministyczne odmaskowanie nie trafia. Po drugie, model bywa, że odrzuca
token semantycznie, uznając, że danych brak, i~odpowiada, że „w~umowach nie wymieniono imion ani
nazwisk żadnych osób". Token `[OSOBA_1]` nie wygląda jak nazwisko, a~`[PESEL_1]` jak numer. Obie
przyczyny mają wspólne źródło w~ograniczeniach niewielkiego modelu, który nie radzi sobie z~wiernym
przepisaniem nienaturalnych ciągów. Nasuwa się więc pytanie, czy przewaga realistycznego zamiennika
jest cechą metody, czy jedynie skutkiem słabości użytego modelu.

=== Weryfikacja na silniejszych modelach

Aby to rozstrzygnąć, ten sam zestaw 50 umów przepuszczono przez dwa znacznie silniejsze modele
komercyjne, Claude oraz GPT, przy czym każde ramię obsługiwał osobny, niezależny podagent bez dostępu
do wzorca. Wyniki zestawiono w~tabeli @tab:eval-jakosc-modele. Przezroczystość utrzymuje się
niezależnie od modelu, gdyż ramię z~bramą wszędzie osiąga 1,0. Zmienia się natomiast ramię tokenowe,
które na obu silniejszych modelach również osiąga 1,0, więc wyraźna na słabym modelu luka między
realistycznym zamiennikiem a~abstrakcyjnymi tokenami całkowicie zanika.

#figure(
  table(
    columns: (1fr, auto, auto, auto),
    align: (left, right, right, right),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 7pt, y: 5pt),
    table.header([*Ramię*], [*`qwen2.5:3b`*], [*Claude*], [*GPT*]),
    [A — oryginał], [0,967], [1,000], [1,000],
    [B — brama (realistyczny zamiennik)], [1,000], [1,000], [1,000],
    [D — tokeny abstrakcyjne], [0,467], [1,000], [1,000],
  ),
  caption: flex-caption(
    [Średnia faktografia trzech ramion na modelu lokalnym oraz dwóch silniejszych (50 umów).],
    [Faktografia w~zależności od siły modelu],
  ),
) <tab:eval-jakosc-modele>

Pomiar zachował przy tym integralność: ramię z~bramą zwracało wartości fałszywe, na przykład
„Elżbieta Kowara" przy Claude czy „Sara Sadłocha" przy GPT, które po odpseudonimizacji odwzorowały się
dokładnie na oryginały, co~potwierdza poprawność pełnego obiegu także na silnych modelach. Wynik ten
różnicuje wcześniejszą obserwację: przewaga realizmu okazuje się zjawiskiem słabszych modeli, podczas
gdy sama przezroczystość pseudonimizacji jest niezależna od modelu i~potwierdzają ją zgodnie wszystkie
trzy. Realistyczna substytucja pozostaje wyborem najogólniejszym, bo działa od małych po duże modele,
podczas gdy abstrakcyjne tokeny wymagają modelu dostatecznie silnego. Dla systemu niezależnego od
dostawcy modelu (zob. @sec:wymagania) jest to właściwa decyzja, potwierdzająca wybór realistycznych
danych zastępczych (zob. @sec:dane-zastepcze).

Oś rozumowania pozostała nierozstrzygnięta, gdyż użyta do niej miara ROUGE-L okazała się
nieadekwatna: dawała około 0,20 niezależnie od ramienia, mierząc pokrycie leksykalne streszczeń
zdominowane przez wspólne słownictwo umów, a~nie przez dane osobowe. Jej rzetelna ocena wymagałaby
miary semantycznej albo osobnego modelu w~roli sędziego, co~wykracza poza zakres prototypu.

Wyniki tej osi mają charakter prototypowy: próby oparto na korpusie syntetycznym, a~zadania były
faktograficzne, w~których silne modele osiągają sufit możliwości, przez co test różnicuje przede
wszystkim modele słabsze. Mimo to wniosek
nadrzędny jest stabilny: pseudonimizacja nie pogarsza faktografii odpowiedzi, niezależnie od siły
modelu. W~połączeniu z~wysoką skutecznością wykrywania i~odwracania danych (zob. @sec:eval-detekcja,
@sec:eval-odtworzenie) daje to spójny obraz, w~którym ochrona prywatności nie odbywa się kosztem
użyteczności. Pełną odpowiedź na postawione pytanie badawcze, wraz z~oceną realizacji celów,
przedstawiono w~podsumowaniu pracy (zob. @ch:podsumowanie).
