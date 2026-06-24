#import "../../utils.typ": todo, silentheading, flex-caption

== Formalne modele prywatności <sec:modele-prywatnosci>

Stwierdzenie, że dane są już wystarczająco anonimowe, wymaga miary pozwalającej ocenić, jak duże
pozostaje ryzyko ponownej identyfikacji. Odpowiedzią na tę potrzebę są formalne modele
prywatności, czyli matematyczne definicje gwarancji, jakie powinien spełniać udostępniany zbiór
danych. Najbardziej znanym z~nich jest k-anonimowość (ang. _k-anonymity_), zaproponowana przez
Latanyę Sweeney. Zgodnie z~jej definicją udostępnienie danych zapewnia ochronę na poziomie
k-anonimowości, jeżeli informacji o~każdej osobie zawartej w~zbiorze nie można odróżnić od
co~najmniej $k-1$ innych osób, których dane również się w~nim znajdują @Sweeney2002. W~praktyce
osiąga się to przez generalizację quasi-identyfikatorów, na przykład zastąpienie dokładnej daty
urodzenia samym rokiem albo kodu pocztowego jego skróconą wersją, oraz przez tłumienie
pojedynczych, nazbyt wyróżniających się rekordów.

Sama k-anonimowość nie chroni jednak przed ujawnieniem cech wrażliwych w~sytuacji, gdy w~grupie
nieodróżnialnych rekordów wszystkie przyjmują tę samą wartość atrybutu chronionego. Ograniczenie
to usuwają kolejne modele: l-różnorodność (ang. _l-diversity_), wymagająca odpowiedniego
zróżnicowania wartości wrażliwych w~każdej grupie @Machanavajjhala2007, oraz t-bliskość (ang.
_t-closeness_), która dodatkowo kontroluje rozkład tych wartości względem rozkładu w~całym
zbiorze @Li2007. Wszystkie trzy modele wyrastają z~tego samego założenia, że dane mają postać
tabeli, w~której wiersze odpowiadają osobom, a~kolumny ich atrybutom.

Odmienne podejście proponuje prywatność różnicowa (ang. _differential privacy_). Zamiast opisywać
własności samego zbioru, formułuje ona obietnicę dotyczącą wyniku analizy: udział pojedynczej
osoby w~badaniu nie powinien w~odczuwalny sposób wpływać na jego rezultat, niezależnie od tego,
jakimi innymi danymi i~źródłami informacji dysponuje obserwator @Dwork2014. Własność tę osiąga
się, dodając do wyników zapytań odpowiednio dobrany szum losowy, tak aby obecność lub nieobecność
konkretnej osoby w~zbiorze pozostawała niewidoczna w~rozkładzie odpowiedzi. Model ten jest więc
przeznaczony do statystycznej analizy danych oraz publikacji wyników zagregowanych, a~nie do
udostępniania treści pojedynczych dokumentów.

Wspólną cechą wszystkich tych modeli jest założenie o~ustrukturyzowanej, najczęściej liczbowej
postaci danych. Tymczasem w~scenariuszu rozważanym w~niniejszej pracy chronione informacje
występują w~tekście swobodnym, a~najgroźniejsze wnioskowania mają charakter semantyczny, to
znaczy opierają się na znaczeniu wyrażonym w~treści, a~nie na statystycznym rozkładzie wartości
@Lison2021. Z~tego powodu formalnych modeli prywatności nie da się wprost przenieść na umowy
cywilnoprawne przekazywane do modelu językowego. Ochrona danych w~takim przypadku wymaga
najpierw wykrycia konkretnych fragmentów tekstu niosących informacje identyfikujące, a~następnie
zastąpienia ich innymi wartościami. Tym dwóm zagadnieniom, technikom maskowania oraz
rozpoznawaniu encji, poświęcone są kolejne podrozdziały.
