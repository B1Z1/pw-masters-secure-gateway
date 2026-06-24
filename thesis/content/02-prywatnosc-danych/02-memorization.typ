#import "../../utils.typ": todo, silentheading, flex-caption

== Zapamiętywanie danych treningowych przez modele (_memorization_) <sec:memorization>

Jednym z~podstawowych zagrożeń dla prywatności w~przypadku dużych modeli językowych jest
zjawisko zapamiętywania danych treningowych (ang. _memorization_). Modele uczone na ogromnych
zbiorach tekstu nie tylko poznają ogólne wzorce języka, lecz potrafią również zachować
w~swoich parametrach konkretne fragmenty danych, na których je trenowano. Odpowiednio
sformułowana podpowiedź może skłonić model do odtworzenia takiego fragmentu dosłownie, co
bezpośrednio narusza prywatność, jeśli zapamiętany tekst zawierał dane osobowe @Carlini2023.
Problem jest tym poważniejszy, że dotyczy także informacji rzadkich i~unikatowych, które
pojawiły się w~zbiorze treningowym zaledwie kilkukrotnie.

Zapamiętywanie ma w~dużej mierze charakter niezamierzony. Carlini i~in. @Carlini2019 wykazali,
że niezamierzone zapamiętywanie jest trwałym i~trudnym do uniknięcia problemem modeli
sekwencyjnych, a~nie wyłącznie teoretyczną ciekawostką. W~swoich eksperymentach opisali
procedurę pozwalającą wydobyć z~modelu unikatowe, tajne sekwencje, takie jak numery kart
kredytowych, wcześniej umieszczone w~danych treningowych. Oznacza to, że nawet pojedyncze
wystąpienie wrażliwej informacji w~zbiorze uczącym może zostać utrwalone przez model
i~następnie ujawnione.

Skala zapamiętywania nie jest stała i~zależy od kilku mierzalnych czynników. Badania nad jej
kwantyfikacją wykazały trzy zależności: stopień zapamiętywania rośnie wraz ze wzrostem
pojemności modelu, wraz z~liczbą powtórzeń danego przykładu w~zbiorze treningowym oraz wraz
z~długością kontekstu użytego w~podpowiedzi @Carlini2023. Co istotne, autorzy wskazują, że
zjawisko to jest powszechniejsze, niż wcześniej sądzono, i~prawdopodobnie będzie się nasilać
wraz ze skalowaniem modeli. W~praktyce oznacza to, że wraz z~rosnącą liczbą parametrów
współczesnych modeli językowych ryzyko utrwalenia danych osobowych systematycznie wzrasta.

Zapamiętane dane można z~modelu wydobyć za pomocą konkretnych ataków. Ekstrakcja danych
treningowych, polegająca na odzyskaniu fragmentów zbioru uczącego poprzez odpowiednie
odpytywanie modelu, stanowi praktyczne zagrożenie dla współczesnych systemów @Carlini2021,
w~tym dla modeli produkcyjnych udostępnianych komercyjnie @Nasr2023. Pokrewnym zagrożeniem
jest atak wnioskowania o~przynależności (ang. _membership inference_), w~którym przeciwnik,
dysponując jedynie dostępem do modelu w~trybie czarnej skrzynki, ustala, czy dany rekord
znajdował się w~zbiorze treningowym @Shokri2017. Konsekwencje tych ataków są szczególnie
istotne w~kontekście niniejszej pracy. Gdyby treść analizowanych umów cywilnoprawnych trafiła
do zbioru treningowego modelu, zawarte w~niej dane osobowe mogłyby zostać później odtworzone
lub powiązane z~konkretną osobą. Już samo przekazanie takich dokumentów zewnętrznemu dostawcy,
który może wykorzystać je do dalszego trenowania modelu, tworzy realne ryzyko naruszenia
prywatności.
