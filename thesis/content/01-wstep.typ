#import "../utils.typ": todo, silentheading, flex-caption

= Wstęp <ch:wstep>
#todo[Rozdział do rozwinięcia — poniżej zakres z konspektu (docs/MasterThesisShorten.pdf).]

Niniejszy rozdział stanowi wprowadzenie do tematyki pracy, osadzając jej problematykę
w kontekście rosnącego znaczenia dużych modeli językowych (LLM, ang. _Large Language Models_)
w środowiskach profesjonalnych oraz wynikających z tego zagrożeń dla prywatności danych.
Wraz z dynamicznym rozwojem generatywnej sztucznej inteligencji narzędzia oparte na modelach
językowych stały się powszechnie wykorzystywane w pracy zawodowej, w tym przez prawników,
analityków finansowych oraz programistów, co wiąże się z coraz częstszym przekazywaniem danych
do zewnętrznych interfejsów API i utratą pełnej kontroli nad ich przetwarzaniem.

Znaczenie tego problemu potwierdzają zarówno incydenty bezpieczeństwa, jak i wyniki badań
naukowych. Przykładem jest przypadek ujawnienia danych firmowych przez pracowników Samsung
Electronics w 2023 roku przy użyciu narzędzi generatywnej AI. Badania wskazują również, że duże
modele językowe mogą odtwarzać fragmenty danych treningowych, w tym dane osobowe, co oznacza,
że ryzyko wycieku informacji może występować niezależnie od sposobu korzystania z modelu.

Rosnąca skala tych zagrożeń znajduje odzwierciedlenie w regulacjach prawnych, takich jak RODO
oraz EU AI Act, które nakładają obowiązki związane z ochroną i minimalizacją danych. Jednocześnie
istniejące rozwiązania nie zapewniają wystarczającego wsparcia w zakresie ochrony danych osobowych
w kontekście analizy dokumentów prawnych, co wskazuje na istotną lukę technologiczną.

Celem niniejszej pracy jest zaprojektowanie i implementacja systemu gateway proxy, który
pseudonimizuje dane osobowe przed ich przekazaniem do modeli językowych, a następnie przywraca
je w odpowiedziach. Praca analizuje wpływ tego podejścia na użyteczność modeli LLM w zadaniach
analizy polskich umów cywilnoprawnych oraz odpowiada na pytanie badawcze dotyczące wpływu
pseudonimizacji danych na jakość generowanych odpowiedzi.
