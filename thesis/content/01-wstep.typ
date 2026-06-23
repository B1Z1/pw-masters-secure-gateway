#import "../utils.typ": todo, silentheading, flex-caption

= Wstęp <ch:wstep>

Duże modele językowe (LLM, ang. _Large Language Models_) w~ciągu ostatnich lat przeszły
drogę od narzędzi badawczych do powszechnie używanych asystentów wspierających codzienną pracę
zawodową. Wraz z~dynamicznym rozwojem generatywnej sztucznej inteligencji rozwiązania oparte na
modelach językowych trafiły do warsztatu prawników, analityków finansowych oraz programistów,
którzy wykorzystują je do streszczania dokumentów, analizy ich treści czy redagowania pism.
Ta wygoda ma jednak swoją cenę. Korzystanie z~modeli udostępnianych przez zewnętrznych dostawców
wiąże się z~przekazywaniem danych poza infrastrukturę organizacji i~utratą pełnej kontroli nad
tym, w~jaki sposób są one dalej przetwarzane.

Znaczenie tego problemu potwierdzają zarówno głośne incydenty bezpieczeństwa, jak i~wyniki badań
naukowych. Przykładem jest ujawnienie wewnętrznych danych firmy Samsung Electronics w~2023 roku,
gdy jej pracownicy wprowadzili do narzędzi generatywnej AI poufny kod źródłowy oraz treść
wewnętrznych spotkań @samsung2023. Co więcej, badania pokazują, że duże modele językowe potrafią
dosłownie odtworzyć fragmenty danych, na których je trenowano, w~tym dane osobowe takie jak imiona
i~nazwiska, numery telefonów czy adresy e-mail @Carlini2021. Co istotne, problem ten dotyczy nie
tylko starszych modeli, ale również współczesnych systemów produkcyjnych, w~tym ChatGPT @Nasr2023.
Oznacza to, że ryzyko wycieku informacji nie znika nawet wtedy, gdy użytkownik zachowuje ostrożność
podczas formułowania zapytań.

Rosnąca skala tych zagrożeń znajduje odzwierciedlenie w~regulacjach prawnych. RODO ustanawia
zasadę minimalizacji danych oraz obowiązki związane z~ich ochroną @gdpr2016, a~unijny akt
o~sztucznej inteligencji (EU AI Act) nakłada dodatkowe wymagania na systemy oparte na sztucznej
inteligencji @aiact2024. Jednocześnie ochrona danych osobowych w~analizie dokumentów prawnych
w~języku polskim pozostaje obszarem słabo wspieranym przez istniejące narzędzia, co stanowi główną
motywację niniejszej pracy.

Celem niniejszej pracy jest zaprojektowanie i~implementacja systemu _gateway proxy_, który
automatycznie wykrywa dane osobowe w~treści zapytania, zastępuje je realistycznymi danymi
syntetycznymi przed wysłaniem do modelu językowego, a~następnie przywraca pierwotne wartości
w~wygenerowanej odpowiedzi. Praca analizuje wpływ takiego podejścia na użyteczność modeli LLM
w~zadaniach analizy polskich umów cywilnoprawnych oraz odpowiada na pytanie badawcze dotyczące
tego, w~jakim stopniu pseudonimizacja danych wpływa na jakość generowanych odpowiedzi.

Praca składa się z~siedmiu rozdziałów: wstępu, części poświęconych zagrożeniom oraz teoretycznym
podstawom ochrony danych, opisu projektu i~implementacji systemu, a~także rozdziału ewaluacyjnego
i~podsumowania.

We wstępie nakreślono kontekst wykorzystania modeli językowych w~pracy zawodowej oraz wynikające
z~niego zagrożenia dla prywatności danych, a~także określono cel i~strukturę pracy.

W~drugim rozdziale omówiono mechanizmy powstawania tych zagrożeń, w~tym zjawisko zapamiętywania
danych treningowych przez modele oraz ryzyka związane z~przekazywaniem danych przez interfejsy API,
a~także wymagania wynikające z~regulacji takich jak RODO i~EU AI Act.

Trzeci rozdział poświęcono teoretycznym podstawom ochrony danych w~systemach sztucznej
inteligencji. Wyjaśniono w~nim różnicę między anonimizacją a~pseudonimizacją, przedstawiono
techniki maskowania danych oraz wyzwania związane z~rozpoznawaniem encji nazwanych
(NER, ang. _Named Entity Recognition_) w~języku polskim.

W~czwartym rozdziale przedstawiono projekt systemu gateway, obejmujący jego architekturę oraz
mechanizmy wykrywania i~pseudonimizacji danych osobowych.

Piąty rozdział opisuje implementację systemu oraz wykorzystany stos technologiczny, w~tym warstwę
API i~integrację z~modelami językowymi.

Szósty rozdział poświęcono testom i~ewaluacji systemu, w~tym ocenie skuteczności pseudonimizacji
oraz jej wpływu na jakość odpowiedzi modeli LLM w~zadaniach analizy polskich umów cywilnoprawnych.

Podsumowanie zawiera syntezę uzyskanych wyników, odpowiedź na postawione pytanie badawcze oraz
wskazanie kierunków dalszego rozwoju systemu.
