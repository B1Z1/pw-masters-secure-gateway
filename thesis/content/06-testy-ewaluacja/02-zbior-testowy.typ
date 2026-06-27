#import "../../utils.typ": todo, silentheading, flex-caption

== Zbiór testowy <sec:eval-korpus>

Wiarygodny pomiar wymaga dokumentów, w~których z~góry znane są wszystkie dane osobowe i~ich dokładne
położenie. Ręczne anotowanie rzeczywistych umów jest pod tym względem pracochłonne i~podatne na błędy
w~granicach encji, dlatego korpus testowy zbudowano syntetycznie. Punktem wyjścia są szablony czterech rodzajów umów cywilnoprawnych, w~których
miejsca na dane osobowe oznaczono slotami o~określonym typie i~roli. Slot wypełnia się następnie
wartością fikcyjną, zapisując jednocześnie jej dokładne położenie oraz typ. Dzięki temu wzorzec
odniesienia powstaje automatycznie, bez ręcznej anotacji i~bez ryzyka pomyłki w~offsetach.

Wartości wstawiane w~sloty pochodzą z~generatora danych Faker @faker w~odmianie polskiej, z~którego korzysta
także sam system przy podstawianiu danych zastępczych (zob. @sec:dane-zastepcze). Są to autentycznie
wyglądające polskie imiona, nazwiska, miejscowości i~adresy, a~także identyfikatory o~poprawnej
strukturze i~poprawnej sumie kontrolnej, takie jak PESEL, NIP, REGON czy numer rachunku bankowego.
Realizm ten jest istotny, ponieważ rozpoznawacze reagują na strukturę danej: przypadkowy ciąg cyfr
nie przeszedłby weryfikacji sumy kontrolnej i~nie obciążyłby mechanizmu wykrywania tak, jak robi to
wartość rzeczywista. Same dokumenty są pełnymi umowami z~realistycznym układem obejmującym komparycję
oraz linie podpisu stron. Każdy z~nich liczy od 1800 do 2300 znaków i~zawiera około dwudziestu encji.

Tak zbudowany korpus liczy 56 dokumentów oraz 1150 instancji danych osobowych w~dziesięciu typach.
Ich rozkład przedstawiono w~tabeli @tab:eval-korpus-typy. Proces generowania jest deterministyczny,
oparty na stałej wartości początkowej generatora liczb losowych, dzięki czemu cały korpus odtwarza
się identycznie, co~potwierdza zgodność jego sumy kontrolnej między kolejnymi przebiegami. Każdy
wynik raportowany w~dalszej części rozdziału jest więc w~pełni reprodukowalny.

#figure(
  table(
    columns: (auto, auto, 1fr),
    align: (left, right, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Typ encji*], [*Liczba*], [*Rodzaj danych*]),
    [`PERSON`], [224], [imię i~nazwisko],
    [`EMAIL_ADDRESS`], [168], [adres e-mail],
    [`PHONE_NUMBER`], [168], [numer telefonu],
    [`DATE_TIME`], [145], [data],
    [`ADDRESS`], [132], [adres: ulica, kod, miejscowość],
    [`LOCATION`], [89], [miejscowość lub region],
    [`PESEL`], [89], [numer ewidencyjny PESEL],
    [`BANK_ACCOUNT`], [76], [numer rachunku bankowego],
    [`NIP`], [36], [numer identyfikacji podatkowej],
    [`REGON`], [23], [numer statystyczny REGON],
    [*Razem*], [*1150*], [],
  ),
  caption: flex-caption(
    [Rozkład typów danych osobowych w~syntetycznym korpusie 56 umów (1150 instancji).],
    [Rozkład typów encji w korpusie],
  ),
) <tab:eval-korpus-typy>

Ponieważ wszystkie dane są fikcyjne, przykłady można przytaczać w~pracy wprost, bez ujawniania
czyichkolwiek informacji. Z~tego względu wszystkie przykłady w~kolejnych podrozdziałach posługują się
wartościami syntetycznymi. Korpus może zostać uzupełniony o~ręcznie anotowane umowy rzeczywiste, te
jednak pozostają lokalne i~nie wchodzą do publikowanych wyników, zgodnie z~wymaganiem prywatności
(zob. @sec:wymagania). Model wykrywający nie był przy tym trenowany na tym korpusie, jest to ogólny
model języka polskiego, nie zachodzi więc nakładanie się zbioru uczącego i~testowego. Na tak
przygotowanym materiale przeprowadzono ocenę skuteczności wykrywania, omówioną w~następnym
podrozdziale.
