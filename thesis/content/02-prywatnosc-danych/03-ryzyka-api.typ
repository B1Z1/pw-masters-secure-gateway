#import "../../utils.typ": todo, silentheading, flex-caption

== Ryzyka związane z interfejsami API dostawców <sec:ryzyka-api>

Drugą powierzchnię narażenia stanowi infrastruktura dostawcy oraz interfejs API, za
pośrednictwem którego użytkownik komunikuje się z~modelem. O~ile zagrożenia opisane
w~poprzednim podrozdziale wynikają z~samego sposobu działania modelu, o~tyle ryzyka omawiane
poniżej dotyczą operacyjnej obsługi zapytań po stronie usługodawcy. Przeglądowe opracowania
wskazują, że korzystanie z~usług opartych na modelach językowych wiąże się z~szeregiem zagrożeń
bezpieczeństwa i~prywatności obejmujących cały cykl przetwarzania danych @Yao2024. Że nie są to
zagrożenia wyłącznie teoretyczne, pokazał incydent z~marca 2023 roku, gdy z~powodu błędu
w~bibliotece Redis część użytkowników serwisu ChatGPT zobaczyła tytuły rozmów innych osób,
a~w~przypadku około 1,2% subskrybentów płatnej wersji ujawnione mogły zostać także dane
płatnicze, w~tym imię i~nazwisko oraz końcowe cyfry numeru karty @openai2023outage. Poniżej
omówiono trzy główne kategorie ryzyk związanych z~interfejsami API dostawców.

=== Logowanie i retencja zapytań

Aby świadczyć usługę, dostawca musi odebrać i~przetworzyć treść każdego zapytania, co
w~praktyce oznacza, że pełna treść polecenia wraz z~dołączonymi dokumentami trafia na serwery
usługodawcy. Zapytania są tam zazwyczaj rejestrowane i~przechowywane przez określony czas,
między innymi na potrzeby monitorowania nadużyć oraz utrzymania usługi. Samo istnienie takich
logów zwiększa powierzchnię ataku, ponieważ dane przekazane do modelu mogą zostać ujawnione nie
tylko w~wyniku celowego ataku, lecz także na skutek zwykłego błędu implementacyjnego, czego
przykładem był wspomniany incydent serwisu ChatGPT @openai2023outage. Dla organizacji
przetwarzającej dokumenty zawierające dane osobowe oznacza to, że faktyczna kontrola nad tymi
danymi zostaje przeniesiona na podmiot zewnętrzny.

=== Wykorzystanie danych do trenowania i dostrajania modeli

Drugim ryzykiem jest możliwość wykorzystania przekazanych danych do dalszego trenowania lub
dostrajania modeli. Zasady w~tym zakresie różnią się w~zależności od dostawcy oraz wariantu
usługi. W~przypadku interfejsów API przeznaczonych do zastosowań biznesowych dane zwykle nie są
domyślnie wykorzystywane do trenowania modeli, podczas gdy w~konsumenckich wersjach asystentów
treść konwersacji może służyć do doskonalenia modelu, o~ile użytkownik nie skorzysta z~opcji
rezygnacji (ang. _opt-out_) @openaiprivacy. Rozróżnienie to ma istotne znaczenie praktyczne,
ponieważ przypadkowe użycie wersji konsumenckiej do analizy poufnych dokumentów może skutkować
trwałym włączeniem zawartych w~nich danych osobowych do procesu uczenia modelu. W~połączeniu
z~opisanym wcześniej zjawiskiem zapamiętywania (zob. @sec:memorization) prowadzi to do ryzyka
ich późniejszego ujawnienia.

=== Podatność na ataki typu _prompt injection_

Trzecim zagrożeniem jest podatność na ataki wstrzykiwania poleceń (ang. _prompt injection_),
które w~zestawieniu OWASP zajmują pierwsze miejsce wśród zagrożeń dla aplikacji opartych na
modelach językowych @owasp2025. Atak polega na takim spreparowaniu danych wejściowych, aby
model potraktował je jako instrukcje i~odstąpił od pierwotnego polecenia. Szczególnie
niebezpieczna jest jego odmiana pośrednia (ang. _indirect prompt injection_), w~której
złośliwe instrukcje są ukryte w~treści przetwarzanego dokumentu lub innych danych pobieranych
przez aplikację. Greshake i~in. @Greshake2023 wykazali, że aplikacje integrujące modele
językowe zacierają granicę między danymi a~instrukcjami, co pozwala atakującemu zdalnie przejąć
kontrolę nad ich działaniem, w~tym doprowadzić do kradzieży danych. W~kontekście analizy umów
cywilnoprawnych oznacza to, że odpowiednio spreparowany dokument mógłby skłonić model do
ujawnienia danych z~innych fragmentów kontekstu lub do wykonania niezamierzonych operacji.
