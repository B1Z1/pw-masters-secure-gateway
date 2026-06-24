#import "../../utils.typ": todo, silentheading, flex-caption

== Przekazywanie danych do zewnętrznych modeli językowych <sec:granica-zaufania>

Współczesne duże modele językowe udostępniane są najczęściej w~modelu usługowym
(ang. _machine learning as a service_), w~którym organizacja nie uruchamia modelu we własnej
infrastrukturze, lecz korzysta z~niego za pośrednictwem interfejsu programistycznego (API)
wystawionego przez zewnętrznego dostawcę. Aby uzyskać odpowiedź, użytkownik przesyła do
dostawcy pełną treść zapytania, obejmującą zarówno polecenie, jak i~dołączone dokumenty.
W~przypadku analizy umów cywilnoprawnych oznacza to, że poza organizację trafia cały tekst
dokumentu wraz ze wszystkimi zawartymi w~nim danymi osobowymi.

Moment przekazania danych do dostawcy wyznacza granicę zaufania, czyli punkt, w~którym dane
opuszczają środowisko kontrolowane przez organizację i~trafiają do systemu zarządzanego przez
podmiot trzeci. Po przekroczeniu tej granicy organizacja traci bezpośrednią kontrolę nad tym,
w~jaki sposób dane są przechowywane, przetwarzane i~wykorzystywane. Nawet jeśli dostawca
deklaruje określone zasady ochrony, ich faktyczne przestrzeganie pozostaje poza możliwością
weryfikacji przez użytkownika, a~samo przekazanie danych jest nieodwracalne.

Z~perspektywy ochrony prywatności przekazanie danych do zewnętrznego modelu rodzi dwie odrębne
powierzchnie narażenia. Pierwszą stanowi sam model językowy, który może utrwalić fragmenty
przekazanych lub treningowych danych i~później je ujawnić (zob. @sec:memorization). Drugą jest
infrastruktura i~interfejs API dostawcy, gdzie dane mogą być rejestrowane, przechowywane oraz
wykorzystywane do dalszego rozwoju modeli (zob. @sec:ryzyka-api). Rozróżnienie to porządkuje
analizę zagrożeń prowadzoną w~dalszej części rozdziału.
