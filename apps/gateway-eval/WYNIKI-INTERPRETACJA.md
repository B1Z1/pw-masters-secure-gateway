# Interpretacja wyników ewaluacji bramy PII

Dokument zbiera wyniki przebiegu na żywo harnessa `gateway-eval` przeciwko działającej
bramie oraz ich interpretację. Jest materiałem roboczym do rozdziału 6 pracy
(`thesis/content/06-testy-ewaluacja`). Wszystkie dane pochodzą z korpusu **syntetycznego**
(PII zmyślone, ale realistyczne), więc przykłady można cytować jawnie.

## 1. Warunki przebiegu

- Tryb w pełni **offline**, dostawca **Echo** (atrapa, nie prawdziwy LLM) — żadna treść nie
  opuszcza maszyny.
- Korpus: **56 dokumentów, 1150 instancji PII**, 10 typów encji, pełne umowy (najem,
  zlecenie, o dzieło, sprzedaż) o długości ~1800–2300 znaków i ~20 encjach na dokument.
- Dane generowane przez Faker `pl_PL` (realne polskie imiona, nazwiska, miasta, adresy,
  poprawne sumy kontrolne PESEL/NIP/REGON/NRB), korpus reprodukowalny (seed = 42).
- Ground truth pochodzi wyłącznie z gold standardu, nigdy z wyjścia bramy
  (anty-cyrkularność).

## 2. Wyniki ogólne

| Wymiar | Wynik |
|---|---|
| Detekcja — recall (micro / macro) | **0,9957 / 0,9970** |
| Detekcja — precision (micro) | 0,8869 |
| Detekcja — F1 (micro) | 0,9381 |
| Audyt wycieków (przed poprawką telefonu) | 5 odrębnych wycieków |
| Odtworzenie (poziom encji) | **1001 / 1150 = 87% `exact`** |
| Odtworzenie z pominięciem DATE\_TIME | ~100% |

Wniosek nadrzędny: brama **działa bardzo dobrze**. Recall jest priorytetem (Konstytucja II
— pominięte PII to najgorszy wynik) i wynosi ~99,6%, przy świadomie niższej precyzji
(brama celowo nadwykrywa). Wyjątki są nieliczne, konkretne i dają się zdiagnozować co do
przyczyny źródłowej. To mocniejszy i bardziej wiarygodny obraz niż „wszystko 100%".

## 3. Trzy wnioski szczegółowe

### Wniosek 1 — wyciek telefonów (przyczyna: konfiguracja Presidio) — NAPRAWIONE

Trzy numery w formacie `+48 702/809/802 …` przeżyły w tekście wychodzącym w oryginale.
Dowód: `+48 596 001 338` jest wykrywany, a `+48 702 654 235` (ten sam format, ten sam
kontekst „numer telefonu …") **nie**.

Przyczyna źródłowa: `PhoneRecognizer` używał domyślnej dla Presidio walidacji
`leniency=VALID`, która akceptuje wyłącznie numery uznawane przez bibliotekę
`phonenumbers` za **faktycznie przypisywalne** (`is_valid=True`). Faker generuje też
numery `is_possible=True, is_valid=False` (zakresy specjalne 702/809/802), które były
**odrzucane** — czyli niewykrywane, niepodmienione, wyciekające. To naruszenie
Konstytucji I (PII nie może wyjść w oryginale).

Charakter naprawy: **strojenie istniejącego rekognizera, nie nowy hak** — zmiana
`leniency=phonenumbers.Leniency.POSSIBLE`. Weryfikacja: przy `POSSIBLE` wykrywane są
wszystkie trzy numery. Naprawa wprowadzona na gałęzi `main`
(`apps/gateway-api/.../recognizers/__init__.py`). Zgodna z Konstytucją II (recall ponad
precyzję). Koszt: możliwy lekki wzrost liczby fałszywie dodatnich telefonów (ciągi
numeropodobne) — wartość do zmierzenia w kolejnym przebiegu jako punkt danych
recall/precision.

### Wniosek 2 — wyciek nazwiska w podpisie (przyczyna: model spaCy) — DO OPISANIA

Nazwiska (np. `Godzisz`, `Potoczna`) wyciekały przy wzmiance w **linii podpisu**.

Dowód rozstrzygający, że to **nie Presidio**: na pełnym dokumencie surowe wyjście spaCy i
wyjście bramy są **identyczne** — `[(2208, 2213, 'Jakub'), …]`. Presidio (`SpacyRecognizer`)
to wierny passthrough, niczego nie przycina.

Przyczyna źródłowa: model `pl_core_news_lg` jest **zależny od kontekstu**. Ten sam ciąg
`Jakub Godzisz` jest tagowany w całości w komparycji i w izolacji, ale w kontekście całego
~2275-znakowego dokumentu (układ stopki, powtórzenia, długi kontekst) model **ucina do
samego imienia** `Jakub`. Nazwisko zostaje poza spanem, więc podmiana go nie obejmuje. To
**nie** jest błąd kodu ani konfiguracji, lecz inherentne ograniczenie statystycznego NER.
„Overlap-recall" liczy to jako trafienie (stąd 1,0), ale recall-exact spada do 0,969 i
audyt ujawnia wyciek.

Charakter ewentualnej naprawy: **wymagałaby dodatkowego komponentu (hak po NER)**, nie
strojenia. Heurystyka „rozszerz span o przyległy token z wielkiej litery" naprawiłaby ten
przypadek, ale wprowadziłaby własne fałszywie dodatnie (rozszerzenia w etykiety,
nagłówki), a model i tak zawiedzie inaczej na innym wejściu — to przesuwanie klasy błędu,
nie eliminacja. Zgodnie z Konstytucją IX rekomendacja: **opisać jako udokumentowane
ograniczenie**, a jako kierunek rozwoju wskazać **uzupełnianie przez koreferencję** —
skoro pełne `Jakub Godzisz` jest poprawnie wykryte w komparycji, a brama posiada już
`coreference_matching`, uciętą wzmiankę można naprawić na podstawie informacji, którą
system **już posiada** (a nie zgadywania). To rozwiązanie pryncypialne, nie whack-a-mole.

### Wniosek 3 — nadwykrywanie i łamana odwracalność dat (przyczyna: rekognizer/model)

Dla DATE\_TIME: recall 1,0, ale **precision 0,53** (98 fałszywie dodatnich) oraz **135 z ~145
dat nieodtworzonych** (`missed`). Wszystkie `missed` w odtworzeniu to wyłącznie DATE\_TIME —
każdy inny typ odtwarza się ~w 100%.

Przyczyna źródłowa: brama wykrywa, obok prawdziwej daty `01.12.1993`, dodatkowo
**nakładający się** fragment `dniu 01.` jako osobną datę. Te nakładki psują round-trip:
fake przypisany do `dniu 01.` nie jest odwracany, przez co oryginalna data nie wraca do
tekstu. Ten sam mechanizm obniża precyzję (nadmiarowe detekcje liczą się jako FP wobec
gold). To realne zachowanie (umowy faktycznie piszą „zawarta w dniu DD.MM.YYYY"), więc
dobry, autentyczny materiał do analizy.

Charakter ewentualnej naprawy: doprecyzowanie `DateRecognizer` (granice wzorca, by nie
łapał `dniu DD.`) i/lub poprawa rozwiązywania nakładek w warstwie detekcji. To realna
poprawa po stronie bramy (EPIC 2), wykraczająca poza zakres harnessa — kandydat na future
work albo osobną iterację.

## 4. Co z tego wynika dla rozdziału 6

1. **Harness spełnił swoje zadanie** — na realistycznych, długich umowach wykrył dwie
   autentyczne luki prywatności (telefony, powtórzone nazwiska) oraz problem
   odwracalności dat. Krótki, prosty korpus tego nie ujawniał. To uzasadnia sens i wartość
   ewaluacji jako osobnego artefaktu.
2. **Pętla ewaluacja → poprawa → ponowny pomiar** (telefon) jest mocnym argumentem
   metodologicznym. Warto pokazać liczby przed/po (recall telefonów, koszt precyzji).
3. **Granice systemu są uczciwie zdiagnozowane co do warstwy**: telefon = konfiguracja
   Presidio (naprawione), nazwisko = model spaCy (ograniczenie + koreferencja jako future
   work), data = rekognizer dat (future work). To pokazuje dojrzałość analizy, a nie
   „ukrywanie" niedoskonałości.
4. Spójna narracja: **wysoka skuteczność ogólna (recall ~99,6%) + nieliczne, konkretne
   wyjątki z przyczyną źródłową i ścieżką naprawy**.

## 5. Zastrzeżenia metodologiczne (do uwzględnienia w pracy)

- Stage 2 używa **Echo**, nie prawdziwego LLM — testuje szczelność i odwracalność
  zintegrowanego potoku, a **nie** jakość odpowiedzi modelu (to było F-34, świadomie poza
  zakresem).
- Audyt wycieków **maskuje zadeklarowane przez bramę fałszywki** przed skanem, bo tekst
  wychodzący jest pełen syntetycznych wartości z tej samej puli Faker co oryginały
  (inaczej kolizje fałszywka↔oryginał dawałyby fałszywe wycieki). Gold pozostaje jedynym
  wyznacznikiem „co jest oryginałem". Wyciek liczony jest raz na ocalałą formę (dedup po
  pozycji).
- `doc_exact_restore_rate = 0,0` jest miarą **surową** (dokument liczy się tylko, gdy
  WSZYSTKIE encje są odtworzone dokładnie i na właściwej pozycji). Zero wynika tu w całości
  z dat — wskaźnik na poziomie encji (87% `exact`, ~100% bez dat) jest bardziej
  informatywny i to jego warto podać jako nagłówkowy.
- Detekcja używa modelu językowego (spaCy + Presidio), ale **nie** generatywnego LLM —
  „bez LLM" oznacza brak modelu generującego odpowiedzi, nie brak NER.
