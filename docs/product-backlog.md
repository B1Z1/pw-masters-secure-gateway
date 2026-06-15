# Product Backlog — Gateway do anonimizacji danych w komunikacji z LLM

> Dokument opisuje pełny zakres systemu w formie epików i feature'ów produktowych.
> Każdy feature zawiera opis, przykłady input/output oraz edge case'y.
> Bez ram czasowych — to jest definicja co ma istnieć, nie kiedy.

---

## EPIC 1 — Infrastruktura i środowisko uruchomieniowe

Całość systemu uruchamia się jedną komendą `docker compose up`. Nie ma żadnych ręcznych kroków konfiguracyjnych poza
uzupełnieniem pliku `.env`.

---

### F-01 · Docker Compose stack

**Opis:**
Plik `docker-compose.yml` definiuje trzy serwisy: `backend` (FastAPI), `redis`, `frontend` (React SPA). Serwisy
komunikują się przez wewnętrzną sieć Docker. Porty eksponowane na host: 8000 (backend), 3000 (frontend). Redis nie jest
eksponowany na zewnątrz.

**Czego oczekujemy po uruchomieniu:**

- `docker compose up` startuje cały stack bez błędów
- `GET http://localhost:8000/health` zwraca `{"status": "ok"}`
- `http://localhost:3000` serwuje React SPA
- Backend łączy się z Redis przez zmienną `REDIS_URL` z `.env`

**Edge cases:**

- Jeśli `REDIS_URL` nie jest ustawiony — backend startuje ale zwraca 503 na każdym endpoincie z informacją "Redis
  unavailable"
- Jeśli Redis jest niedostępny w trakcie działania — endpoint zwraca 503, nie crashuje procesu
- Multi-stage Dockerfile dla backendu: stage 1 instaluje zależności, stage 2 kopiuje tylko kod — minimalizacja rozmiaru
  obrazu

---

### F-02 · Konfiguracja przez zmienne środowiskowe

**Opis:**
Wszystkie parametry konfiguracyjne czytane z `.env`. Repozytorium zawiera `.env.example` z opisem każdej zmiennej. Brak
`.env` w `.gitignore`.

**Zmienne:**

```
REDIS_URL=redis://:password@redis:6379/0
REDIS_PASSWORD=changeme
REDIS_ENCRYPTION_KEY=<32-bajtowy klucz base64>
REDIS_SESSION_TTL=3600

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://host.docker.internal:11434

DEFAULT_LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4o
```

**Edge cases:**

- `REDIS_ENCRYPTION_KEY` musi mieć dokładnie 32 bajty po dekodowaniu base64 — backend waliduje przy starcie i odmawia
  uruchomienia jeśli klucz jest niepoprawny
- Klucze API dostawców LLM są opcjonalne przy starcie — błąd pojawi się dopiero przy próbie użycia danego dostawcy

---

### F-03 · Health check endpoint

**Opis:**
`GET /health` zwraca status wszystkich zależności systemu.

**Output:**

```json
{
  "status": "ok",
  "dependencies": {
    "redis": "ok",
    "spacy_model": "ok"
  }
}
```

**Edge cases:**

- Jeśli Redis niedostępny: `"redis": "unavailable"`, `"status": "degraded"`
- Jeśli model SpaCy nie załadowany: `"spacy_model": "unavailable"`, `"status": "degraded"`
- HTTP 200 nawet gdy `status: degraded` — health check nie powinien failować load balancera przy degradacji

---

## EPIC 2 — Silnik wykrywania PII (NER + custom recognizery)

Silnik przyjmuje tekst i zwraca listę wykrytych encji z typem, pozycją w tekście i poziomem pewności. Jest niezależną
warstwą — można go testować bez reszty systemu.

---

### F-04 · Bazowy NER (Presidio + SpaCy pl_core_news_lg)

**Opis:**
Presidio `AnalyzerEngine` skonfigurowany z modelem `pl_core_news_lg` jako NLP backend. Wykrywa standardowe encje:
`PERSON`, `LOCATION`, `DATE_TIME`, `EMAIL_ADDRESS`, `PHONE_NUMBER`.

**Input:**

```
"Jan Kowalski mieszka w Warszawie przy ul. Złotej 44. Tel: 500 123 456, jan.kowalski@firma.pl"
```

**Output:**

```json
[
  {
    "entity_type": "PERSON",
    "start": 0,
    "end": 12,
    "score": 0.85,
    "text": "Jan Kowalski"
  },
  {
    "entity_type": "LOCATION",
    "start": 22,
    "end": 31,
    "score": 0.80,
    "text": "Warszawie"
  },
  {
    "entity_type": "PHONE_NUMBER",
    "start": 55,
    "end": 66,
    "score": 0.75,
    "text": "500 123 456"
  },
  {
    "entity_type": "EMAIL_ADDRESS",
    "start": 68,
    "end": 90,
    "score": 0.95,
    "text": "jan.kowalski@firma.pl"
  }
]
```

**Edge cases:**

- Nakładające się encje (overlap) — Presidio rozwiązuje przez `ConflictResolutionStrategy.MERGE_SIMILAR_OR_CONTAINED`
- Imię i nazwisko jako dwie oddzielne encje vs. jedna `PERSON` — zależy od modelu SpaCy; akceptowalne, mapping obsługuje
  oba przypadki
- Tekst po angielsku w polskim dokumencie — Presidio obsługuje, ale priorytet jest `pl`

---

### F-05 · PeselRecognizer

**Opis:**
Custom recognizer dla numeru PESEL. Waliduje format (11 cyfr) oraz sumę kontrolną. Dodatkowo wyciąga płeć z cyfry na
pozycji indeks 9 (0-indexed) — parzysta = kobieta, nieparzysta = mężczyzna. Płeć jest przechowywana w kontekście sesji i
używana przez generator fake danych.

**Walidacja sumy kontrolnej:**
Wagi: `[1, 3, 7, 9, 1, 3, 7, 9, 1, 3]`
Suma = Σ(cyfra[i] × waga[i]) mod 10
Ostatnia cyfra (indeks 10) musi być równa `(10 - suma) mod 10`

**Input:** `"PESEL: 90010112345"`

**Output:**

```json
{
  "entity_type": "PESEL",
  "start": 7,
  "end": 18,
  "score": 0.99,
  "text": "90010112345",
  "context": {
    "gender": "male"
  }
}
```

**Edge cases:**

- PESEL z myślnikami lub spacjami (`900-101-123-45`) — recognizer normalizuje przed walidacją, ale zwraca oryginalny
  tekst (z myślnikami) jako `text`
- PESEL z niepoprawną sumą kontrolną — score 0.4 (format ok, ale prawdopodobnie nie PESEL), nie blokowany ale z niskim
  confidence
- 11 losowych cyfr które przypadkowo spełniają walidację — akceptowane (false positive w tym kontekście jest OK — lepiej
  zamaskować za dużo)
- Data w PESEL > 2000 roku: miesiąc + 20 (styczeń 2001 = `21`, nie `01`)

---

### F-06 · NipRecognizer

**Opis:**
Custom recognizer dla NIP. Format: 10 cyfr (z myślnikami lub bez: `XXX-XXX-XX-XX` lub `XXXXXXXXXX`). Walidacja sumy
kontrolnej.

**Walidacja:**
Wagi: `[6, 5, 7, 2, 3, 4, 5, 6, 7]`
Suma = Σ(cyfra[i] × waga[i]) mod 11
Wynik musi być równy ostatniej cyfrze. Jeśli suma mod 11 = 10 — NIP jest nieprawidłowy.

**Input:** `"NIP: 123-456-78-90"`

**Output:**

```json
{
  "entity_type": "NIP",
  "start": 5,
  "end": 18,
  "score": 0.99,
  "text": "123-456-78-90"
}
```

**Edge cases:**

- NIP zaczynający się od `0` — prawidłowy, regex nie może wymagać niezerowej pierwszej cyfry
- NIP w treści zdania bez etykiety (`"NIP:"`) — niższy score (0.6), bo brak kontekstu
- Nakładanie się z PESEL: 10 cyfr NIPu może być częścią 11-cyfrowego PESEL — Presidio rozwiązuje przez zasięg (span)
  encji, dłuższa wygrywa

---

### F-07 · RegonRecognizer

**Opis:**
Custom recognizer dla REGON. Dwa warianty: 9-cyfrowy (podmiot) i 14-cyfrowy (jednostka lokalna). Każdy ma inny algorytm
sumy kontrolnej.

**Walidacja 9-cyfrowego:**
Wagi: `[8, 9, 2, 3, 4, 5, 6, 7]`
Suma = Σ(cyfra[i] × waga[i]) mod 11; jeśli 10 → 0
Musi być równa cyfrze na pozycji 8.

**Walidacja 14-cyfrowego:**
Wagi: `[2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]`
Suma = Σ(cyfra[i] × waga[i]) mod 11; jeśli 10 → 0
Musi być równa cyfrze na pozycji 13.

**Edge cases:**

- 14-cyfrowy REGON zaczyna się od 9-cyfrowego REGON tej samej firmy — recognizer musi preferować dłuższy match
- REGON bez etykiety kontekstowej — score 0.5 (same cyfry, brak kontekstu)

---

### F-08 · PolishBankAccountRecognizer

**Opis:**
Custom recognizer dla numeru rachunku bankowego w formacie NRB (Numer Rachunku Bankowego). Format: 26 cyfr, opcjonalnie
ze spacjami co 4 cyfry lub z prefiksem `PL` (IBAN).

**Format NRB:** `CC BBBB BBBB XXXX XXXX XXXX XXXX`
gdzie `CC` = 2 cyfry kontrolne, `BBBB BBBB` = 8 cyfr (numer banku i oddziału), reszta = 16 cyfr konta.

**Walidacja mod 97 (opcjonalna):**
Przesuń pierwsze 4 znaki na koniec, zastąp litery cyframi (PL = 2521), oblicz mod 97. Wynik musi być równy 1.

**Input:** `"przelew na nr: 61 1090 1014 0000 0712 1981 2074"`

**Output:**

```json
{
  "entity_type": "BANK_ACCOUNT",
  "start": 15,
  "end": 47,
  "score": 0.90,
  "text": "61 1090 1014 0000 0712 1981 2074"
}
```

**Edge cases:**

- Numer z prefiksem `PL` (IBAN) — recognizer obsługuje oba formaty
- Numer bez spacji (ciągłe 26 cyfr) — obsługiwane
- 26-cyfrowy ciąg cyfr w innym kontekście (np. kod kreskowy) — brak etykiety bankowej → score 0.4

---

### F-09 · PolishAddressRecognizer

**Opis:**
Recognizer dla polskich adresów. Wykrywa wzorce: `ul./al./pl. [Nazwa] [Numer]`, kod pocztowy `XX-XXX`, miasto po kodzie
pocztowym. Adres może być jednoliniowy lub wieloliniowy.

**Input:** `"zamieszkałego przy ul. Marszałkowskiej 10/3, 00-001 Warszawa"`

**Output:**

```json
{
  "entity_type": "ADDRESS",
  "start": 18,
  "end": 58,
  "score": 0.85,
  "text": "ul. Marszałkowskiej 10/3, 00-001 Warszawa"
}
```

**Edge cases:**

- Adres bez nazwy ulicy (tylko miasto i kod) — niższy score, ale nadal wykrywany
- Adres z numerem lokalu (`/3`, `m. 3`, `lok. 3`) — wszystkie warianty obsługiwane
- Nazwa ulicy będąca nazwiskiem (`ul. Kowalskiego`) — nie koliduje z PERSON bo SpaCy widzi `ul.` jako prefix adresowy

---

### F-10 · Konfiguracja progów detekcji i strategia false positive/negative

**Opis:**
Każdy recognizer ma konfigurowalny `score_threshold` — minimalne confidence poniżej którego encja jest ignorowana.
Domyślne progi per typ encji zdefiniowane w konfiguracji (nie na twardo w kodzie).

**Domyślne progi:**

```yaml
PESEL: 0.85       # walidacja sumy → wysoki score dla poprawnych
NIP: 0.85
REGON: 0.80
BANK_ACCOUNT: 0.75
PERSON: 0.70      # SpaCy bywa niepewny dla polskich imion
EMAIL_ADDRESS: 0.90
PHONE_NUMBER: 0.65
ADDRESS: 0.70
```

**Strategia:**
W kontekście prawnym priorytetem jest **recall** (lepiej zamaskować za dużo niż za mało). Progi są celowo niskie.
Fałszywe alarmy są akceptowalne — użytkownik widzi w UI które encje zostały wykryte i może to zweryfikować.

**Edge cases:**

- Próg ustawiony na 0.0 — maskuje wszystko co recognizer w ogóle wykryje (tryb "paranoidalny")
- Próg ustawiony na 1.0 — praktycznie wyłącza detekcję (tylko 100% pewne encje)
- Zmiana progu nie wymaga restartu — czytana z konfiguracji per request

---

## EPIC 3 — Generator fake danych i mapping store

Moduł odpowiedzialny za generowanie realistycznych danych zastępczych oraz przechowywanie mapowania oryginal → fake w
obrębie sesji.

---

### F-11 · Generator realistycznych danych zastępczych (Faker pl_PL)

**Opis:**
Klasa `FakeDataGenerator` generuje realistyczne polskie dane zastępcze dla każdego typu encji. Dane są spójne
kontekstowo — płeć zachowana, formaty poprawne, sumy kontrolne valid.

**Mapowanie typów na generatory:**

| Typ encji       | Generator                                                              | Uwagi                                     |
|-----------------|------------------------------------------------------------------------|-------------------------------------------|
| `PERSON`        | `faker.first_name_[male/female]()` + `faker.last_name_[male/female]()` | Płeć z kontekstu sesji (PESEL) lub losowa |
| `PESEL`         | Własna funkcja                                                         | Spójna płeć, poprawna suma kontrolna      |
| `NIP`           | Własna funkcja                                                         | Poprawna suma kontrolna                   |
| `REGON`         | Własna funkcja                                                         | Wariant 9 lub 14-cyfrowy zachowany        |
| `EMAIL_ADDRESS` | `faker.email()`                                                        |                                           |
| `PHONE_NUMBER`  | `faker.phone_number()`                                                 | Format polski (+48 lub 9 cyfr)            |
| `LOCATION`      | `faker.city()`                                                         |                                           |
| `ADDRESS`       | `faker.street_address()` + `faker.postcode()` + `faker.city()`         |                                           |
| `BANK_ACCOUNT`  | Własna funkcja                                                         | Poprawny NRB z walidacją mod 97           |
| `DATE_TIME`     | `faker.date_of_birth()`                                                | Format DD.MM.YYYY, zbliżony wiek          |

**Edge cases:**

- Generowanie PESEL dla kobiety po 2000 roku — miesiąc + 20, płeć z cyfry na pozycji 9
- Faker może wygenerować dane już użyte w tej sesji (kolizja) — generator sprawdza Redis przed zwrotem, przy kolizji
  generuje ponownie (max 3 próby, potem dodaje losowy sufiks)
- `DATE_TIME` — jeśli oryginalna data to data urodzenia (kontekst PESEL), generuj datę w podobnym przedziale wiekowym (
  ±10 lat), żeby zachować wiarygodność tekstu

---

### F-12 · Redis mapping store z szyfrowaniem AES-256

**Opis:**
Klasa `MappingStore` przechowuje w Redis dwukierunkowe mapowanie: `original → fake` i `fake → original`. Wszystkie
wartości szyfrowane AES-256 przed zapisem. Mapowania mają TTL — wygasają automatycznie po upływie sesji.

**Struktura kluczy Redis:**

```
session:{session_id}:fwd:{hash(original)}  →  encrypt(fake_value)
session:{session_id}:rev:{hash(fake)}       →  encrypt(original_value)
session:{session_id}:meta                   →  {"created_at": ..., "entity_count": ...}
```

Klucze używają `hash(original)` zamiast samego tekstu — unika przechowywania PII w kluczu Redis.

**Metody:**

- `get_or_create(session_id, original, entity_type) → fake` — zwraca cached lub generuje nowy
- `get_original(session_id, fake) → original | None` — lookup odwrotny
- `get_all_mappings(session_id) → List[Mapping]` — wszystkie mapowania sesji (do debugowania)
- `delete_session(session_id)` — czyści wszystkie klucze sesji
- `extend_ttl(session_id)` — przedłuża TTL przy każdej aktywności w sesji

**Szyfrowanie:**
Użyj `cryptography.fernet.Fernet` (AES-128-CBC + HMAC-SHA256) lub `cryptography.hazmat` z `AES-GCM` dla AES-256-GCM.
Klucz z `REDIS_ENCRYPTION_KEY`. Szyfrowanie/deszyfrowanie transparentne dla wywołującego.

**Edge cases:**

- Redis restart — sesja ginie (TTL nie jest persistent). Akceptowalne — użytkownik zaczyna nową sesję.
- Ta sama wartość oryginalna, inny typ encji — traktowane jako oddzielne encje (np. "Kowalski" jako PERSON i jako część
  adresu). Klucz Redis zawiera `entity_type` w hashu.
- Kolizja hash(original) — SHA-256 sprawia że praktycznie niemożliwa, ale store sprawdza wartość po deserializacji

---

### F-13 · Spójność mapowania w sesji multi-turn

**Opis:**
W ramach jednej sesji ta sama oryginalna wartość zawsze mapuje się na ten sam fake. Dotyczy to zarówno dokładnych
matches jak i różnych form gramatycznych tej samej encji.

**Przykład:**

```
Wiadomość 1: "Jan Kowalski podpisał umowę"
  → "Jan Kowalski" mapuje na "Piotr Wiśniewski"
  → Redis: fwd("Jan Kowalski") = "Piotr Wiśniewski"

Wiadomość 3: "Co Kowalski zobowiązał się zrobić?"
  → "Kowalski" mapuje na "Wiśniewski" (ta sama baza)
  → Redis: fwd("Kowalski") sprawdza czy istnieje wpis,
    jeśli nie — szuka partial match, używa "Wiśniewski"
```

**Strategia partial match:**
Przed `get_or_create` sprawdzamy czy jakaś istniejąca oryginalna wartość zawiera lub jest zawarta w nowej encji (
case-insensitive). Jeśli tak — zwracamy odpowiadający fake (i jego formę bazową). Generujemy nowy tylko gdy brak
jakiegokolwiek overlapa.

**Edge cases:**

- "Anna Kowalska" i "Jan Kowalski" to dwie różne osoby — mimo wspólnego rdzenia "Kowalsk" muszą mieć oddzielne
  mapowania. Partial match działa na poziomie pełnego imienia+nazwiska, nie pojedynczych tokenów.
- Reset sesji przez użytkownika — `delete_session()` + nowy `session_id` → świeże mapowania

---

### F-14 · Obsługa polskiej fleksji (odmiana przez przypadki)

**Opis:**
Polski jest językiem fleksyjnym — nazwisko "Kowalski" pojawia się w tekście jako "Kowalskiego", "Kowalskiemu", "
Kowalskim" itd. Wszystkie formy muszą mapować się na ten sam fake w odpowiedniej formie.

**Strategia (pragmatyczna, nie perfekcyjna):**

1. Przy generowaniu fake nazwiska — buduj słownik podstawowych form odmienionych: mianownik, dopełniacz, celownik,
   biernik, narzędnik, miejscownik (dla imion i nazwisk najczęstszych wzorców odmiany)
2. Przy lookup w de-pseudonimizacji — sprawdzaj nie tylko exact match, ale też wszystkie wygenerowane formy
3. Formy przechowywane w Redis jako dodatkowy klucz: `session:{id}:forms:{hash(fake_nominative)}` →
   `{"gen": "Wiśniewskiego", "dat": "Wiśniewskiemu", ...}`

**Znane ograniczenia (opisane w pracy):**

- Rzadkie nazwiska obcego pochodzenia nie będą miały poprawnych form odmienionych
- System nie obsługuje wszystkich 7 przypadków — skupia się na najczęstszych (mianownik, dopełniacz, biernik)
- Imiona obce (np. "Anna-Maria") — brak odmiany, traktowane jako nieodmienialne

**Edge cases:**

- Nazwisko kończące się na samogłoskę (Zara, Nowacka) — inne wzorce odmiany niż zakończone na spółgłoskę
- Odmiana imienia a odmiana nazwiska są niezależne — "Jana Kowalskiego" to `gen(Jan)` + `gen(Kowalski)`, nie jedna encja

---

## EPIC 4 — Pipeline pseudonimizacji i de-pseudonimizacji

Główny orchestrator systemu. Łączy NER, fake generator i mapping store w jeden flow.

---

### F-15 · Pipeline inbound (pseudonimizacja zapytania)

**Opis:**
Klasa `AnonymizationPipeline` przetwarza wiadomość użytkownika przed wysłaniem do LLM. Wykrywa PII, zastępuje fake
danymi, zachowuje mapowanie w Redis.

**Flow:**

```
1. INPUT: tekst wiadomości użytkownika
2. analyzer.analyze(text) → lista RecognizerResult (encje z pozycjami)
3. Sortowanie encji od końca tekstu do początku (reverse order by start position)
   — zapobiega przesuwaniu indeksów przy podmianie
4. Dla każdej encji:
   a. mapping_store.get_or_create(session_id, original_text, entity_type) → fake
   b. text = text[:start] + fake + text[end:]
5. OUTPUT: pseudonimizowany tekst + lista podmian dla debugowania
```

**Input:**

```json
{
  "session_id": "abc-123",
  "text": "Jan Kowalski, PESEL 90010112345, zamieszkały w Warszawie"
}
```

**Output:**

```json
{
  "pseudonymized_text": "Piotr Wiśniewski, PESEL 85030567890, zamieszkały w Krakowie",
  "entities_replaced": [
    {
      "original": "Jan Kowalski",
      "fake": "Piotr Wiśniewski",
      "type": "PERSON"
    },
    {
      "original": "90010112345",
      "fake": "85030567890",
      "type": "PESEL"
    },
    {
      "original": "Warszawie",
      "fake": "Krakowie",
      "type": "LOCATION"
    }
  ]
}
```

**Edge cases:**

- Nakładające się encje po sortowaniu — Presidio filtruje overlaps przed zwrotem wyników; pipeline zakłada brak nakładań
- Pusta lista encji — tekst przechodzi bez zmian, sesja tworzona ale pusta
- Tekst tylko w języku angielskim — NER nadal działa (Presidio jest multilingual), ale skuteczność niższa

---

### F-16 · Pipeline outbound (de-pseudonimizacja odpowiedzi)

**Opis:**
Po otrzymaniu odpowiedzi od LLM — podmień fake dane z powrotem na oryginalne. Lookup odbywa się przez Redis (rev
mapping) oraz słownik form fleksyjnych.

**Flow:**

```
1. INPUT: tekst odpowiedzi LLM (zawiera fake dane)
2. Pobierz wszystkie mapowania dla session_id: List[(fake, original)]
3. Dla każdego mapowania (sortowane od najdłuższego fake do najkrótszego — unika partial replace):
   a. Exact match: replace all occurrences of fake → original
   b. Fuzzy match (jeśli exact nie trafił): Levenshtein distance ≤ 2
      — obsługuje przypadek gdy LLM lekko odmienił fake imię
4. OUTPUT: tekst z przywróconymi oryginalnymi danymi
```

**Input:**

```
"Piotr Wiśniewski zobowiązał się do zapłaty. Wiśniewskiemu przysługuje prawo odstąpienia."
```

**Output:**

```
"Jan Kowalski zobowiązał się do zapłaty. Kowalskiemu przysługuje prawo odstąpienia."
```

**Edge cases:**

- LLM zmienił formę gramatyczną fake imienia w sposób nieprzewidziany — fuzzy matching wyłapuje jeśli różnica ≤ 2 znaki
- Fake wartość pojawia się jako część innego słowa (np. fake miasto "Radom" w słowie "radomski") — replace używa word
  boundary (`\b`) dla tokenów alfanumerycznych
- Wiele różnych fake wartości które są podobne do siebie — sortowanie od najdłuższej zapobiega partial replace (
  najpierw "Wiśniewski Jan", potem "Wiśniewski", potem "Jan")
- LLM nie użył fake danych w odpowiedzi (np. odpowiedź ogólna bez nazw) — de-pseudonimizacja nie zmienia nic, zwraca
  tekst bez zmian

---

### F-17 · Tryb standalone (anonimizacja bez LLM)

**Opis:**
Endpoint `POST /v1/anonymize` uruchamia tylko pipeline inbound bez wysyłania do LLM. Użyteczny do testowania silnika, do
ręcznej weryfikacji co system wykrywa oraz jako niezależne API do anonimizacji tekstu.

**Request:**

```json
{
  "text": "Jan Kowalski, PESEL 90010112345",
  "session_id": "optional-abc-123",
  "language": "pl"
}
```

**Response:**

```json
{
  "original_text": "Jan Kowalski, PESEL 90010112345",
  "anonymized_text": "Piotr Wiśniewski, PESEL 85030567890",
  "session_id": "abc-123",
  "entities": [
    {
      "type": "PERSON",
      "original": "Jan Kowalski",
      "replacement": "Piotr Wiśniewski",
      "start": 0,
      "end": 12,
      "score": 0.85
    },
    {
      "type": "PESEL",
      "original": "90010112345",
      "replacement": "85030567890",
      "start": 21,
      "end": 32,
      "score": 0.99
    }
  ]
}
```

**Edge cases:**

- Brak `session_id` w request — system generuje nowy UUID i zwraca go w response
- Ten sam `session_id` co istniejąca sesja chatowa — mapowania są współdzielone (intencjonalne)
- Pusty tekst — zwraca `{"anonymized_text": "", "entities": []}` bez błędu

---

## EPIC 5 — Adaptery LLM (provider-agnostic)

Warstwa abstrakcji pozwalająca na komunikację z różnymi dostawcami LLM przez jeden interfejs. System nie wie nic o
konkretnym dostawcy — router wybiera adapter na podstawie konfiguracji.

---

### F-18 · Abstrakcja LLMProvider

**Opis:**
Bazowa klasa abstrakcyjna `LLMProvider` z jedną metodą: `async def complete(messages: list[Message]) -> str`. Wszystkie
adaptery implementują tę klasę. Format messages zgodny z OpenAI (role + content).

**Interfejs:**

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict]) -> str:
        """Send messages and return assistant response text."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if provider is reachable."""
        ...
```

**Edge cases:**

- Provider niedostępny (timeout, błąd sieci) — adapter rzuca `LLMProviderError` z opisem. Pipeline łapie i zwraca 503 z
  opisem błędu.
- Provider zwraca pustą odpowiedź — adapter rzuca `LLMProviderError("Empty response")`
- Rate limit od dostawcy (429) — adapter nie retry'uje, rzuca błąd z informacją o rate limit

---

### F-19 · OpenAI adapter

**Opis:**
Implementacja `LLMProvider` używająca oficjalnego `openai` Python SDK. Obsługuje modele GPT-4o, GPT-4-turbo,
GPT-3.5-turbo.

**Konfiguracja:** `OPENAI_API_KEY`, `DEFAULT_MODEL` z `.env`

**Konwersja messages:** Format OpenAI jest natywny — brak konwersji.

**Edge cases:**

- Wiadomość systemowa (`role: system`) przekazywana jako pierwsza w liście — OpenAI to obsługuje
- Model niedostępny (np. deprecated) — błąd z API propagowany do użytkownika
- Odpowiedź zawiera `finish_reason: length` (urwana przez token limit) — adapter loguje warning, zwraca co dostał

---

### F-20 · Anthropic adapter

**Opis:**
Implementacja `LLMProvider` używająca `anthropic` Python SDK. Obsługuje modele Claude 3 Opus, Sonnet, Haiku.

**Konwersja messages:**
Anthropic ma inny format — oddzielny parametr `system` zamiast `role: system` w liście messages. Adapter konwertuje
wewnętrznie:

```
OpenAI messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
  ↓ adapter konwertuje
Anthropic API:  system="...", messages=[{"role": "user", "content": "..."}]
```

**Edge cases:**

- Kolejność wiadomości: Anthropic wymaga alternacji `user/assistant`. Jeśli dwie kolejne wiadomości mają ten sam role —
  adapter łączy je w jedną.
- Brak wiadomości systemowej — adapter wysyła bez parametru `system`

---

### F-21 · Ollama adapter (lokalny LLM)

**Opis:**
Implementacja `LLMProvider` komunikująca się z lokalnym serwerem Ollama przez REST API. Nie wymaga zewnętrznego SDK —
czysty HTTP.

**Endpoint:** `POST {OLLAMA_BASE_URL}/api/chat`

**Edge cases:**

- Ollama nie uruchomiony — `health_check()` zwraca False, endpoint zwraca 503 z informacją "Ollama unavailable"
- Model nie pobrany (`ollama pull llama3`) — błąd 404 od Ollama propagowany z czytelnym komunikatem
- Długi czas odpowiedzi lokalnych modeli — timeout konfigurowalny oddzielnie (`OLLAMA_TIMEOUT=120`)

---

### F-22 · Router dostawców LLM

**Opis:**
Klasa `LLMRouter` wybiera odpowiedni adapter na podstawie parametru `model` w request lub domyślnej konfiguracji.

**Logika wyboru:**

- `model` zaczyna się od `gpt-` → `OpenAIAdapter`
- `model` zaczyna się od `claude-` → `AnthropicAdapter`
- Inny model → `OllamaAdapter` (zakłada lokalny)
- Brak `model` w request → `DEFAULT_LLM_PROVIDER` z `.env`

**Edge cases:**

- Nieznany model — błąd 400 z listą dostępnych modeli
- API key dla wybranego dostawcy nie skonfigurowany — błąd 503 z informacją który klucz brakuje

---

## EPIC 6 — API Gateway (FastAPI)

Warstwa HTTP łącząca frontend z pipeline'em. Kompatybilna z formatem OpenAI API tam gdzie to ma sens.

---

### F-23 · Endpoint chat completions (POST /v1/chat/completions)

**Opis:**
Główny endpoint systemu. Przyjmuje wiadomości w formacie kompatybilnym z OpenAI API, przepuszcza przez pipeline
pseudonimizacji, wywołuje LLM, de-pseudonimizuje odpowiedź.

**Request:**

```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "user",
      "content": "Streść umowę: Jan Kowalski, PESEL 90010112345..."
    }
  ],
  "session_id": "abc-123"
}
```

**Response:**

```json
{
  "id": "chatcmpl-uuid",
  "object": "chat.completion",
  "model": "gpt-4o",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Umowa dotyczy Jana Kowalskiego, który zobowiązał się..."
      },
      "finish_reason": "stop"
    }
  ],
  "session_id": "abc-123",
  "anonymization_meta": {
    "entities_detected": 3,
    "processing_time_ms": 145
  }
}
```

**Edge cases:**

- `session_id` nie podany — generowany automatycznie, zwracany w response
- Lista `messages` pusta — błąd 400
- Ostatnia wiadomość nie ma `role: user` — błąd 400 (LLM oczekuje zapytania od użytkownika)
- Timeout LLM — błąd 504 z informacją, session_id zachowany (można ponowić)

---

### F-24 · Middleware logowania i metryk

**Opis:**
FastAPI middleware loguje każdy request: czas, endpoint, session_id, liczba wykrytych encji, czas przetwarzania per
etap. **Logi nie zawierają oryginalnych danych PII** — tylko pseudonimizowane wartości i metadane.

**Format logu:**

```json
{
  "timestamp": "2026-06-15T12:00:00Z",
  "session_id": "abc-123",
  "endpoint": "/v1/chat/completions",
  "provider": "openai",
  "model": "gpt-4o",
  "entities_detected": {
    "PERSON": 1,
    "PESEL": 1,
    "LOCATION": 1
  },
  "timing_ms": {
    "ner_analysis": 45,
    "fake_generation": 12,
    "redis_write": 8,
    "llm_request": 1240,
    "deanonymization": 15,
    "total": 1320
  }
}
```

**Edge cases:**

- Błąd podczas logowania nie może przerywać głównego flow — log error idzie do stderr, request jest obsługiwany
- PII w URL lub query params — middleware sanityzuje przed logiem (choć architektura nie powinna w ogóle wysyłać PII w
  URL)

---

### F-25 · Zarządzanie sesjami

**Opis:**
Endpoint `GET /v1/sessions/{session_id}` zwraca metadane sesji. `DELETE /v1/sessions/{session_id}` usuwa sesję i
wszystkie mapowania.

**GET Response:**

```json
{
  "session_id": "abc-123",
  "created_at": "2026-06-15T12:00:00Z",
  "last_activity": "2026-06-15T12:05:00Z",
  "ttl_remaining_seconds": 3300,
  "entity_count": 5,
  "message_count": 3
}
```

**Edge cases:**

- Nieistniejący session_id — 404
- Session po TTL — 404 (Redis usunął automatycznie)
- DELETE na nieistniejącą sesję — 404 (nie 200, żeby klient wiedział że sesja już nie istniała)

---

## EPIC 7 — Frontend (React SPA)

Interfejs użytkownika. Priorytet: funkcjonalność > wygląd. MVP może być estetycznie prosty.

---

### F-26 · Interfejs chatowy

**Opis:**
Główny widok aplikacji. Okno konwersacji z listą wiadomości (user/assistant), pole tekstowe do wpisywania zapytań,
przycisk wyślij. Pod każdą wiadomością użytkownika widoczna jest informacja o wykrytych encjach.

**Zachowanie:**

- Wiadomości user po prawej, assistant po lewej (standardowy chat layout)
- Pole tekstowe obsługuje Shift+Enter jako nową linię, Enter jako wyślij
- Podczas oczekiwania na odpowiedź — loading indicator, pole zablokowane
- Błąd API — komunikat inline, pole odblokowane

**Edge cases:**

- Bardzo długa wiadomość (> 10 000 znaków) — ostrzeżenie przed wysłaniem, nie blokada
- Utrata połączenia podczas oczekiwania — komunikat "Połączenie przerwane, spróbuj ponownie"
- Session_id przechowywany w `sessionStorage` (nie localStorage) — ginie po zamknięciu karty (nowa sesja = nowe
  mapowania)

---

### F-27 · Widok side-by-side (oryginalny vs. pseudonimizowany)

**Opis:**
Przełączalny panel pokazujący obok siebie oryginalny tekst wiadomości i jego pseudonimizowaną wersję. Wykryte encje
podświetlone kolorami per typ. Panel domyślnie zwinięty — otwierany na żądanie.

**Kolorowanie typów:**

- PERSON → niebieski
- PESEL/NIP/REGON → czerwony
- EMAIL/PHONE → zielony
- ADDRESS/LOCATION → pomarańczowy
- BANK_ACCOUNT → fioletowy

**Edge cases:**

- Brak wykrytych encji — panel pokazuje "Brak wykrytych danych osobowych w tej wiadomości"
- Bardzo długi tekst — panel scrollowany niezależnie od głównego chatu

---

### F-28 · Dashboard statystyk

**Opis:**
Panel boczny lub oddzielna zakładka. Pokazuje agregowane statystyki dla aktualnej sesji: liczba wykrytych encji per
typ (wykres słupkowy), czas przetwarzania ostatnich N requestów, aktualny dostawca LLM i model.

**Edge cases:**

- Brak danych (nowa sesja) — puste wykresy z komunikatem "Brak danych"
- Reset sesji — statystyki resetują się

---

### F-29 · Panel konfiguracji

**Opis:**
Zakładka ustawień. Pozwala wybrać aktywnego dostawcę LLM i model, podać klucze API (zapisywane w `sessionStorage`, nie
wysyłane do backendu jako konfiguracja — każdy request niesie klucz w headerze lub backend używa `.env`). Możliwość
zresetowania aktualnej sesji.

**Edge cases:**

- Zmiana dostawcy w trakcie sesji — mapowania są zachowane (Redis), ale nowe wiadomości idą do nowego dostawcy
- Brak klucza API dla wybranego dostawcy — komunikat przed wysłaniem pierwszej wiadomości, nie dopiero po błędzie

---

## EPIC 8 — Testy i ewaluacja

Zestaw testów weryfikujących poprawność systemu oraz materiał do rozdziału ewaluacyjnego pracy.

---

### F-30 · Testy jednostkowe recognizerów

**Opis:**
Testy `pytest` dla każdego custom recognizera. Każdy recognizer ma testy pozytywne (poprawne encje powinny być wykryte),
negatywne (błędne dane nie powinny być wykryte) oraz edge case'y.

**Przykłady dla PeselRecognizer:**

```python
def test_pesel_valid(): assert recognizer.analyze("PESEL 90010112345") detects PESEL
def test_pesel_invalid_checksum(): assert recognizer.analyze("PESEL 90010112340") empty
def test_pesel_gender_male(): assert extracted_gender == "male"
def test_pesel_post_2000(): assert recognizer.analyze("PESEL 02250112345") detects PESEL
```

**Pokrycie:** minimum 10 przypadków testowych per recognizer.

---

### F-31 · Testy integracyjne pipeline

**Opis:**
Testy end-to-end pipeline'u pseudonimizacji i de-pseudonimizacji. Weryfikują że:

- Tekst po pseudonimizacji nie zawiera oryginalnych PII
- Tekst po de-pseudonimizacji zawiera oryginalne PII w poprawnych miejscach
- Multi-turn zachowuje spójność mapowań

**Test multi-turn:**

```
Turn 1: "Jan Kowalski podpisał umowę" → pseudonimizowany
Turn 2: "Co Kowalski zobowiązał się zrobić?" → "Kowalski" mapuje na ten sam fake
Turn 3: De-pseudonimizacja odpowiedzi → "Kowalski" wraca
```

---

### F-32 · Korpus testowy i gold standard

**Opis:**
Zestaw 50 syntetycznych umów cywilnoprawnych (najem, zlecenie, o dzieło, sprzedaż) z wstrzykniętymi danymi PII. Każda
umowa ma ręcznie adnotowany gold standard — oznaczone wszystkie wystąpienia PII z typem i pozycją.

**Generowanie umów:**

- Publiczne wzory umów + wstrzyknięte PII przez skrypt
- Minimum 500 instancji PII łącznie w korpusie
- Reprezentacja wszystkich typów encji (nie tylko PERSON)

**Format gold standard (JSONL):**

```json
{
  "doc_id": "umowa_najmu_001",
  "text": "Jan Kowalski, PESEL 90010112345...",
  "entities": [
    {
      "type": "PERSON",
      "start": 0,
      "end": 12,
      "text": "Jan Kowalski"
    },
    {
      "type": "PESEL",
      "start": 21,
      "end": 32,
      "text": "90010112345"
    }
  ]
}
```

---

### F-33 · Ewaluacja NER (Precision / Recall / F1)

**Opis:**
Skrypt porównujący output silnika NER z gold standard. Oblicza Precision, Recall i F1-score per typ encji oraz
agregowane. Generuje confusion matrix.

**Metryki:**

- Precision = TP / (TP + FP) — ile wykrytych to rzeczywiście PII
- Recall = TP / (TP + FN) — ile PII z gold standard zostało wykrytych
- F1 = 2 × (P × R) / (P + R)

**Output:** tabela per typ encji + heatmapa confusion matrix (jako plik PNG/SVG do pracy).

---

### F-34 · Ewaluacja wpływu pseudonimizacji na LLM (A/B)

**Opis:**
Eksperyment porównujący jakość odpowiedzi LLM na tekst oryginalny vs. pseudonimizowany. Cztery zadania ewaluacyjne na
każdej umowie z korpusu.

**Zadania:**

1. **Streszczenie** — porównanie ROUGE-L i BERTScore między streszczeniem oryginału a pseudonimizowanego
2. **Ekstrakcja klauzul** — Precision/Recall wyciągniętych klauzul (kluczowych postanowień)
3. **Identyfikacja stron** — Accuracy identyfikacji stron umowy i ich ról (wynajmujący/najemca)
4. **Q&A** — odpowiedzi na 5 pytań o treść każdej umowy, ocena Accuracy

**Format wyników:** tabela zbiorcza per zadanie per dostawca LLM (OpenAI vs Anthropic vs Ollama).

---

### F-35 · Analiza wydajności (latency)

**Opis:**
Pomiar czasu przetwarzania per etap pipeline dla różnych długości dokumentów. Testy obciążeniowe przy 10/50/100
równoległych requestach (Locust).

**Mierzone etapy:**

- NER (Presidio analyze)
- Generowanie fake danych (Faker)
- Redis write
- LLM request (czas dostawcy, nie narzut systemu)
- De-pseudonimizacja
- Total pipeline overhead (bez LLM)

**Edge cases:**

- Bardzo długi dokument (> 5 000 słów) — czy NER nie spowalnia quadratycznie
- Wiele encji (> 50 PII w jednym dokumencie) — czy Redis nie staje się bottleneckiem

---

### F-36 · Weryfikacja bezpieczeństwa (audyt wycieku PII)

**Opis:**
Inspekcja wychodzących requestów HTTP do dostawców LLM. Weryfikacja że oryginalne PII nie pojawiają się w żadnym
outgoing request. Test szyfrowania Redis.

**Testy:**

- Przechwyt HTTP proxy (mitmproxy) — skanowanie requestów do OpenAI/Anthropic pod kątem PII
- Próba odczytu Redis bez klucza szyfrowania — weryfikacja że dane są nieczytelne
- Skanowanie logów aplikacji — żadne logi nie zawierają oryginalnych PII

---

## Słownik pojęć

| Termin          | Definicja                                                         |
|-----------------|-------------------------------------------------------------------|
| PII             | Personally Identifiable Information — dane osobowe                |
| NER             | Named Entity Recognition — rozpoznawanie encji nazwanych          |
| Pseudonimizacja | Odwracalna zamiana PII na dane zastępcze z zachowaniem mapowania  |
| Anonimizacja    | Nieodwracalne usunięcie PII (w pracy używane jako termin szerszy) |
| Session         | Kontekst konwersacji z jednym mapowaniem PII → fake               |
| Pipeline        | Przepływ danych: input → NER → fake gen → LLM → de-anon → output  |
| Gold standard   | Ręcznie adnotowany zbiór testowy służący do ewaluacji NER         |
| Recall          | Procent rzeczywistych PII wykrytych przez system                  |
| Precision       | Procent wykrytych encji które rzeczywiście są PII                 |

---

*Wersja 1.0 — dokument roboczy. Aktualizowany w miarę postępu implementacji.*