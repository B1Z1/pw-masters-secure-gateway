#import "../../utils.typ": todo, silentheading, flex-caption

= Prywatność danych w komunikacji z modelami językowymi <ch:prywatnosc>

Korzystanie z~zewnętrznych modeli językowych wiąże się z~przekazywaniem danych poza
infrastrukturę organizacji, a~tym samym z~częściową utratą kontroli nad sposobem ich dalszego
przetwarzania. Niniejszy rozdział systematyzuje zagrożenia dla prywatności wynikające z~tej
sytuacji oraz przedstawia ramy prawne wyznaczające granice dopuszczalnego przetwarzania danych
osobowych. Najpierw scharakteryzowano model przekazywania danych do dostawców usług AI oraz
wynikające z~niego powierzchnie narażenia, następnie omówiono mechanizmy zagrożeń po stronie
samego modelu oraz interfejsu API, a~na końcu wymagania regulacyjne. Na tej podstawie
uzasadniono potrzebę zastosowania pośredniczącej warstwy anonimizującej, której projekt
przedstawiono w~dalszej części pracy.

#include "01-granica-zaufania.typ"
#include "02-memorization.typ"
#include "03-ryzyka-api.typ"
#include "04-regulacje.typ"
#include "05-uzasadnienie.typ"
