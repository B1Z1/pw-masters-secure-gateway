# Praca dyplomowa (magisterska) — Typst

Tekst pracy w szablonie **[wut-thesis](https://typst.app/universe/package/wut-thesis) 0.2.0**
(oficjalny szablon Politechniki Warszawskiej). Folder żyje w tym samym repo co projekt
inżynierski; źródłem prawdy o systemie są `../specs/` i `../docs/`, a tu powstaje narracja pracy.

## Wymagania

- [Typst](https://typst.app) ≥ 0.14.0 (`brew install typst`).
- Fonty w katalogu [`fonts/`](fonts/), ładowane przez `--font-path fonts`:
  - `texgyreheros-regular.otf` — **już w repo** (TeX Gyre Heros, GUST, licencja GFL).
  - `Adagio_Slab-Regular.otf` i `Adagio_Slab-Light.otf` — **musisz dograć sam** (logo / strona
    tytułowa). Pobierz `PW_Adagio_Slab.zip` z intranetu PW (wymaga konta pw.edu.pl), rozpakuj
    i wrzuć oba pliki `.otf` do `fonts/`. Są wykluczone z gita przez `.gitignore` (własność PW).

> Bez Adagio_Slab praca **i tak się skompiluje** — szablon pokazuje wtedy „Logo Placeholder"
> zamiast logo wydziału. Po dograniu fontu logo pojawi się automatycznie.

## Kompilacja

```sh
make build    # jednorazowo -> thesis.pdf
make watch    # tryb ciągły (przelicza przy każdym zapisie)
```

Bez `make`: `typst compile thesis.typ --font-path fonts`.

## Konfiguracja

Metadane (autor, promotor, wydział, kierunek, tytuł, streszczenie, słowa kluczowe) ustawia się
na górze [`thesis.typ`](thesis.typ) — pola oznaczone `TODO:` wymagają uzupełnienia. Lista
dozwolonych kodów wydziału (`faculty`) jest w komentarzu obok tego pola.

Dwie flagi sterujące (góra `thesis.typ`):

- `draft` — `true` na czas pisania (kolorowane linki, widoczne TODO, „DRAFT" w nagłówku).
  Ustaw `false` w wersji finalnej.
- `in-print` — `true` tylko dla wersji do fizycznego druku/oprawy (większe marginesy na zszycie).
  Do oddania w APD musi być `false`.

## Struktura

- `thesis.typ` — plik główny (konfiguracja + dołączanie rozdziałów).
- `content/` — rozdziały (na razie przykładowe z szablonu; `Tutorial.typ` to ściąga ze składni Typst).
- `items.bib` — bibliografia. `glossary.typ` — skróty/glosariusz. `images/`, `listings/` — zasoby.
