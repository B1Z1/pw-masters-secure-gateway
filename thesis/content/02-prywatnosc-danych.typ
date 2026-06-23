#import "../utils.typ": todo, silentheading, flex-caption

= Prywatność danych w komunikacji z modelami językowymi <ch:prywatnosc>
#todo[Rozdział do rozwinięcia — poniżej zakres z konspektu (docs/MasterThesisShorten.pdf).]

Rozdział drugi stanowi teoretyczne wprowadzenie do zagadnień związanych z ochroną danych
osobowych w kontekście wykorzystania zewnętrznych modeli językowych. W rozdziale omówione
zostaną główne zagrożenia wynikające z przekazywania danych do komercyjnych modeli LLM, w tym
zjawisko _memorization_, polegające na możliwości odtwarzania fragmentów danych treningowych
przez model, a także ryzyka związane z wykorzystaniem zewnętrznych interfejsów API, takie jak
logowanie zapytań, retencja danych, możliwość ich dalszego wykorzystania do dostrajania modeli
oraz podatność na ataki typu _prompt injection_. Przedstawiona zostanie również analiza wymagań
prawnych wynikających z regulacji RODO/GDPR oraz EU AI Act, wskazująca ryzyka związane
z przetwarzaniem danych osobowych przez zewnętrznych dostawców usług AI. Na podstawie
omówionych zagrożeń oraz wymagań regulacyjnych uzasadniona zostanie potrzeba zastosowania
warstwy pośredniej w postaci systemu gateway anonimizującego, który umożliwia bezpieczne
korzystanie z zewnętrznych modeli językowych przy jednoczesnym ograniczeniu ryzyka naruszenia
prywatności danych. Rozdział ten stanowi podstawę teoretyczną dla architektury rozwiązania
przedstawionej w dalszej części pracy.
