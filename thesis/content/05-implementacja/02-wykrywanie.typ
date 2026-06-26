#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Wykrywanie danych osobowych <sec:impl-wykrywanie>

Pierwszym ogniwem silnika pseudonimizacji jest moduł wykrywania, którego zadaniem jest zlokalizowanie
w~tekście fragmentów stanowiących dane osobowe (zob. @sec:ner). Moduł ten zaimplementowano na bazie
biblioteki Microsoft Presidio, frameworka przeznaczonego do wykrywania i~anonimizacji danych
wrażliwych @presidio. Centralnym jego elementem jest komponent `AnalyzerEngine`, który orkiestruje
zbiór rozpoznawaczy (ang. _recognizers_) i~na ich podstawie zwraca listę wykrytych encji wraz z~oceną
pewności. Przyjęte podejście jest hybrydowe: łączy statystyczny model rozpoznawania encji nazwanych
z~rozpoznawaczami regułowymi. Takie połączenie metod uczenia maszynowego z~regułami jest typowe dla
systemów deidentyfikacji tekstu @Lison2021, ponieważ żadna z~tych metod z~osobna nie pokrywa
wszystkich rodzajów danych osobowych.

Wykrywanie encji o~swobodnej postaci, takich jak imiona i~nazwiska, nazwy miejscowości czy daty,
powierzono statystycznemu modelowi języka polskiego `pl_core_news_lg` z~biblioteki spaCy @spacy.
Model ten oznacza encje etykietami zaczerpniętymi z~Narodowego Korpusu Języka Polskiego (NKJP),
w~tym `persName` dla osób oraz `placeName` i~`geogName` dla miejsc @Przepiorkowski2012. Etykiety te
różnią się jednak od typów, którymi posługuje się Presidio, dlatego silnik NLP skonfigurowano
z~jawnym odwzorowaniem etykiet NKJP na typy encji Presidio. Odwzorowanie to okazało się niezbędne,
gdyż bez niego bazowy model nie ujawniłby żadnej encji. Przyjęte mapowanie przedstawiono w~tabeli
@tab:mapowanie-etykiet. Warto zaznaczyć, że nazwy organizacji, choć rozpoznawane przez model,
celowo pominięto w~zbiorze typów zwracanych przez moduł, gdyż w~rozważanym zastosowaniu nie są one
traktowane jako dane osobowe.

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    stroke: 0.5pt + gray.lighten(30%),
    inset: (x: 8pt, y: 5pt),
    table.header([*Etykieta NKJP (spaCy)*], [*Typ encji Presidio*], [*Rodzaj danych*]),
    [`persName`], [PERSON], [imię i~nazwisko],
    [`placeName`, `geogName`], [LOCATION], [miejscowość, region],
    [`date`, `time`], [DATE\_TIME], [data, godzina],
  ),
  caption: flex-caption(
    [Odwzorowanie etykiet encji NKJP używanych przez model spaCy na typy encji Presidio.],
    [Mapowanie etykiet NKJP na typy Presidio],
  ),
) <tab:mapowanie-etykiet>

Dane o~ściśle określonej strukturze, charakterystyczne dla polskiego obrotu prawnego, obsłużono
osobnymi rozpoznawaczami regułowymi. Należą do nich numer PESEL, NIP, REGON oraz numer rachunku
bankowego, a~także adres i~data zapisana słownie. Dla identyfikatorów liczbowych przyjęto wspólny
schemat: wyrażenie regularne lokalizuje kandydata o~właściwej długości, a~o~ocenie jego pewności
rozstrzyga suma kontrolna. Reprezentatywnym przykładem jest tu numer PESEL. Zgodnie z~jego
specyfikacją jest to „jedenastocyfrowy symbol numeryczny" kodujący datę urodzenia, liczbę porządkową
z~oznaczeniem płci oraz cyfrę kontrolną @peselgov, a~rozpoznawacz po odnalezieniu jedenastu cyfr
weryfikuje poprawność tej cyfry kontrolnej.

Istotną decyzją projektową jest sposób potraktowania wartości o~błędnej sumie kontrolnej. Zamiast ją
odrzucać, rozpoznawacz pozostawia ją w~wyniku, lecz z~niską oceną pewności. Wynika to z~przyjętej
przewagi czułości nad precyzją (zob. @sec:wymagania): ciąg cyfr o~niepoprawnej sumie wciąż może być
rzeczywistym, lecz omyłkowo zapisanym identyfikatorem, a~jego pominięcie oznaczałoby wyciek danych
poza granicę zaufania. Mechanizm ten, wspólny dla wszystkich rozpoznawaczy z~sumą kontrolną,
zrealizowano w~metodzie `analyze` ich wspólnej klasy bazowej `ChecksumPatternRecognizer`,
przedstawionej na rysunku @rys:checksum.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", "class ChecksumPatternRecognizer(PatternRecognizer):

    def analyze(
        self,
        text: str,
        entities,
        nlp_artifacts=None,
        regex_flags: int | None = None,
    ):
        results = super().analyze(
            text, entities, nlp_artifacts=nlp_artifacts, regex_flags=regex_flags
        )
        for result in results:
            normalized = strip_separators(text[result.start : result.end])
            valid, meta = self.validate_checksum(normalized)
            result.score = S_VALID if valid else S_INVALID
            meta = dict(meta or {})
            meta.setdefault(\"normalized\", normalized)
            meta[\"checksum_valid\"] = valid
            attach_pii_meta(result, meta)
        return results"))),
  ),
  caption: flex-caption(
    [Metoda `analyze` rozpoznawacza z~sumą kontrolną: o~ocenie decyduje wynik weryfikacji, a~wartość o~błędnej sumie pozostaje w~wyniku.],
    [Rozpoznawacz oparty na sumie kontrolnej],
  ),
  kind: image,
) <rys:checksum>

Konkretne rozpoznawacze identyfikatorów dziedziczą po tej klasie bazowej i~dostarczają jedynie własne
wyrażenia regularne oraz funkcję weryfikującą sumę kontrolną. Ilustruje to rozpoznawacz numeru
rachunku bankowego, przedstawiony na rysunku @rys:bank. Rozpoznaje on zarówno zapis ciągły, jak
i~pogrupowany, w~obu wariantach z~opcjonalnym przedrostkiem `PL`, a~przy weryfikacji oblicza sumę
kontrolną metodą mod-97, zgodną ze standardem IBAN, i~odnotowuje rozpoznany format.

#figure(
  rect(
    width: 100%,
    fill: luma(248),
    stroke: 0.5pt + gray.lighten(30%),
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    text(size: 0.8em, align(left, raw(block: true, lang: "python", read("listings/bank_recognizer.py")))),
  ),
  caption: flex-caption(
    [Rozpoznawacz numeru rachunku bankowego: własne wzorce (zapis ciągły i~pogrupowany) oraz weryfikacja sumy kontrolnej metodą mod-97.],
    [Rozpoznawacz numeru rachunku bankowego],
  ),
  kind: image,
) <rys:bank>

Oceny pewności przypisywane są w~sposób deterministyczny, według ustalonych przedziałów zależnych od
typu encji oraz poprawności sumy kontrolnej. Ocenę podstawową może następnie podnieść kontekstowe
wzmacnianie udostępniane przez Presidio: jeżeli w~sąsiedztwie encji pojawi się słowo wskazujące, na
przykład „PESEL" obok ciągu cyfr, ocena zostaje powiększona o~stały składnik @presidio. Wartość
końcową ograniczono z~góry, aby zarezerwować ocenę skrajną dla przypadków jednoznacznych. Tak
wyznaczona ocena jest porównywana z~progiem właściwym dla danego typu encji. Progi zapisano
w~odrębnym pliku konfiguracyjnym, odczytywanym na bieżąco, dzięki czemu zmiana wartości wpływa na
kolejne żądania bez ponownego uruchamiania usługi. Domyślne progi ustawiono celowo nisko, co ponownie
odzwierciedla przewagę czułości nad precyzją.

Ponieważ różne rozpoznawacze mogą wskazać nakładające się fragmenty tekstu, wyniki przechodzą przez
deterministyczne rozstrzyganie nakładania się encji, w~którym pierwszeństwo ma fragment dłuższy,
obejmujący pozostałe. Dzięki temu wykryty adres pochłania na przykład zawartą w~nim nazwę
miejscowości. Tak uzgodnioną listę encji odwzorowuje się na wewnętrzny obiekt `DetectedEntity`,
niezależny od reprezentacji Presidio. Pozostałe komponenty systemu nie zależą zatem od wewnętrznej
budowy biblioteki, a~obiekt ten udostępnia dodatkowo kanał metadanych. Dla osób i~miejscowości moduł
odczytuje ponadto z~modelu spaCy formę podstawową (lemat) oraz przypadek gramatyczny, niezbędne do
późniejszego, zgodnego z~odmianą, podstawienia danych zastępczych (zob. @sec:impl-generowanie). Sam
model, którego wczytanie jest kosztowne, ładowany jest tylko raz, przy starcie aplikacji i~w~osobnym
wątku, tak aby nie blokować obsługi pozostałych żądań (zob. @sec:impl-srodowisko).

Wynikiem działania modułu jest lista wykrytych danych osobowych wraz z~ich położeniem, typem oraz
oceną pewności. Kolejnym krokiem jest dobranie dla nich realistycznych wartości zastępczych, czemu
poświęcono następny podrozdział.
