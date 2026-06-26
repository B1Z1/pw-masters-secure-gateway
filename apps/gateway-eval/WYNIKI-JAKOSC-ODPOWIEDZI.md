# Jakość odpowiedzi LLM przy pseudonimizacji — wyniki badania (F-34)

Dokument zbiera wyniki drugiej osi ewaluacji — wpływu pseudonimizacji na jakość
odpowiedzi LLM w analizie polskich umów cywilnoprawnych. Jest materiałem roboczym do
rozdziału 6 pracy (`thesis/content/06-testy-ewaluacja`) i uzupełnia
`WYNIKI-INTERPRETACJA.md` (oś pierwsza — poprawność pseudonimizacji). Wyniki pochodzą z
prototypu `answer_quality_prototype.py` na korpusie **syntetycznym** (dane zmyślone, ale
realistyczne), więc przykłady można cytować jawnie.

## 1. Pytanie badawcze

Czy podmiana realnego PII na **realistyczne** dane fałszywe zachowuje użyteczność
analityczną LLM w porównaniu z wysłaniem oryginału, oraz czy **realizm** substytutu w ogóle
ma znaczenie? Innymi słowy — czy obrana metoda fałszyfikacji ma sens. To bezpośrednia
walidacja Konstytucji VII (realistyczna substytucja).

## 2. Warunki i metodyka

- Tryb w pełni **offline**, model **lokalny** `qwen2.5:3b` (Ollama). Ramię A wysyła
  oryginały, więc tylko model lokalny jest dopuszczalny (RODO).
- Korpus syntetyczny (najem, zlecenie, o dzieło, sprzedaż), te same dane co w osi
  pierwszej. To dane czysto testowe — brama (Presidio/spaCy) nie była na nich trenowana,
  więc nie ma problemu „train/test".
- **Trzy ramiona** dla każdej umowy i pytania:
  - **A — oryginał**: oryginalny tekst → LLM bezpośrednio (baseline jakości).
  - **B — brama**: tekst → gateway (pseudonimizacja **realistycznym fake** → LLM →
    de-pseudonimizacja). To badane podejście.
  - **D — abstrakcyjne tokeny + odtworzenie**: PII zastąpione **rozróżnialnymi**,
    odwracalnymi tokenami (`[OSOBA_1]`, `[OSOBA_2]`, `[PESEL_1]`…), a w odpowiedzi token
    jest **odmaskowywany** z powrotem do oryginału. To samo, co B, ale substytut jest
    abstrakcyjny zamiast realistycznego — dzięki temu `B vs D` izoluje **czysty efekt
    realizmu** (oba mają pełny, odwracalny pipeline).
- Metryki:
  - **Faktografia** (osoby, PESEL, rachunek): udział wartości z gold obecnych w odpowiedzi.
    W pełni obiektywne, bo gold jest znany.
  - **Rozumowanie** (streszczenie): ROUGE-L względem oryginału.
- Przeprowadzono dwie konfiguracje: pomiar A/B na **20 umowach** (mocniejsza statystyka dla
  przezroczystości) oraz pełny A/B/D na **5 umowach** (izolacja efektu realizmu).

## 3. Wyniki

### Eksperyment 1 — przezroczystość pseudonimizacji (A/B, 20 umów, n = 60)

| Pytanie | A (oryginał) | B (brama) |
|---|---|---|
| osoby (PERSON) | 1,000 | 1,000 |
| PESEL | 0,825 | 0,825 |
| rachunek (BANK_ACCOUNT) | 0,950 | 1,000 |
| **średnia** | **0,925** | **0,942** |

### Eksperyment 2 — czy realizm substytutu ma znaczenie (A/B/D, 5 umów, n = 15)

| Ramię | Średnia | osoby | PESEL | rachunek |
|---|---|---|---|---|
| **A** oryginał | 0,967 | 1,0 | 0,9 | 1,0 |
| **B** brama (realistyczny fake) | **1,000** | 1,0 | 1,0 | 1,0 |
| **D** abstrakcyjne tokeny + odtworzenie | **0,467** | 0,6 | 0,4 | 0,4 |

Rozumowanie (ROUGE-L względem oryginału): A-B ≈ A-D ≈ 0,20 — praktycznie równe.

## 4. Wnioski

### Wniosek 1 — pseudonimizacja jest przezroczysta dla faktografii (B ≈ A)

Średni udział wartości gold: B = 0,942 wobec A = 0,925 (różnica w granicach szumu, B nawet
minimalnie wyższe). LLM widzi dane fałszywe, a po de-pseudonimizacji odpowiedź zawiera
**poprawne, prawdziwe** wartości. Dla osób i rachunków skuteczność jest praktycznie
idealna.

### Wniosek 2 — realizm substytutu ma znaczenie (B ≫ D)

Najważniejszy wynik: **B = 1,0 wobec D = 0,467**, mimo że **oba ramiona mają pełne
odtworzenie**. Sama odwracalność nie wystarczy — liczy się **jakość substytutu**. Przyczyny
porażek D (z surowych odpowiedzi, przed odtworzeniem):
1. **LLM przeformatowuje token** — pisze `PESEL_1` / `NR_RACHUNKU_1` / „Osoba 1" zamiast
   `[PESEL_1]`, więc deterministyczne odtworzenie nie trafia. Przykład: *„Numer rachunku
   wskazany w umowie wynosi: NR_RACHUNKU_1."*
2. **LLM semantycznie odrzuca token** — uznaje, że danych nie ma: *„w umowach nie
   wymieniono imion ani nazwisk żadnych osób"*, *„Nie są one podane w treści"*. Token
   `[OSOBA_1]` nie wygląda jak nazwisko, `[PESEL_1]` nie wygląda jak numer.

Realistyczna fałszywka („Roksana Czerwionka", „95011509543") nie ma żadnego z tych
problemów — LLM traktuje ją jak prawdziwe dane, wiernie przepisuje, a brama odtwarza
oryginał. To bezpośrednie potwierdzenie Konstytucji VII: realistyczny substytut zachowuje
kontekst semantyczny, którego model potrzebuje.

### Wniosek 3 — spadek PESEL to ograniczenie MODELU, nie bramy

PESEL osiąga 0,825 — ale **identycznie w ramieniu A i B** (A = B). Skoro oryginał wypada
tak samo, spadek **nie jest winą pseudonimizacji**, tylko ograniczeniem małego modelu,
który bywa, że gubi lub halucynuje 11-cyfrowy numer w długim kontekście. Uwaga metodyczna:
na mniejszej próbce (5 umów) PESEL w B wyglądał na problem bramy — dopiero większa próbka
(20 umów) skorygowała tę interpretację do A = B.

### Wniosek 4 — ROUGE-L jest nieadekwatny dla osi rozumowania

ROUGE-L(A,B) ≈ ROUGE-L(A,D) ≈ 0,20 — praktycznie równe i bez kierunku. Powód: ROUGE liczy
pokrycie **leksykalne** streszczeń, zdominowane przez wspólne słownictwo umowy („umowa",
„strony", „zobowiązuje"), a nie przez PII. Do oceny jakości rozumowania potrzeba metryki
**semantycznej** (BERTScore) albo **LLM-as-judge**.

## 5. Znaczenie dla pracy (rozdział 6)

Badane podejście wygrywa na **obu** osiach:

- **B ≈ A** (0,94 vs 0,93) → pseudonimizacja **nie szkodzi** użyteczności odpowiedzi.
- **B ≫ D** (1,0 vs 0,47) → przy tym samym, odwracalnym pipelinie **realistyczny** substytut
  bije abstrakcyjne tokeny — czyli realizm fałszyfikacji jest **konieczny**, nie kosmetyczny.

To jednoznaczna, ilościowa odpowiedź na pytanie badawcze: **obrana metoda fałszyfikacji ma
sens** — z konkretnym uzasadnieniem, dlaczego realizm substytutu jest istotny.

## 6. Zastrzeżenia i ograniczenia

- Model `qwen2.5:3b` jest mały (3,1 mld parametrów), CPU — wyniki reprezentują lekki,
  lokalny model, nie duże modele komercyjne.
- Próba: 20 umów (A/B) i 5 umów (A/B/D), korpus **syntetyczny**. Realistyczny, ale nie
  zastępuje umów rzeczywistych.
- **D = 0,467 to dolna granica**. Większość porażek D to przeformatowanie tokenu (powód 1),
  które „rozmyte" odtwarzanie mogłoby częściowo naprawić. Jednak przypadki **semantycznego
  odrzucenia** (powód 2) są nieusuwalne nawet idealnym odtwarzaniem — to czysty,
  nieredukowalny efekt realizmu. Świadomie zostawiono prosty algorytm odtwarzania, bo
  różnica B vs D i tak jest rozstrzygająca.
- Metryka faktograficzna mierzy **obecność** wartości gold w odpowiedzi, nie pełną
  poprawność pragmatyczną.
- ROUGE-L zostawiono jako wynik negatywny (czego NIE używać), nie jako miarę jakości
  rozumowania.
- To **prototyp** (F-34). Pełna wersja: BERTScore/LLM-judge dla rozumowania, większa i
  zróżnicowana próba, drugi model, ewentualnie pomiar odporności PESEL.

## 7. Reprodukcja

```bash
# stack lokalny (Ollama + brama), model qwen2.5:3b
docker compose -f docker-compose.yml -f dev/ollama/docker-compose.ollama.yml up -d ollama gateway-api

cd apps/gateway-eval
# A/B/D na 5 umowach (izolacja efektu realizmu)
PYTHONPATH=. .venv/bin/python answer_quality_prototype.py --sample 5 \
  --out eval-results/answer_quality_4arms.json
# A/B na 20 umowach (mocniejsza statystyka przezroczystości)
PYTHONPATH=. .venv/bin/python answer_quality_prototype.py --sample 20 \
  --out eval-results/answer_quality_20docs.json
```

Szczegóły, w tym **surowe odpowiedzi** A/B/D (gotowe przykłady do pracy, m.in. token
odrzucony przez model), w plikach JSON w `apps/gateway-eval/eval-results/`.
