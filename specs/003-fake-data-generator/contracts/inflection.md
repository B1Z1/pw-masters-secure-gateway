# Contract — Polish inflection (`gateway_api/pseudonym_generation/inflection.py`)

Pure Python, **no NLP dependency** (research D2). Documents the declension **method** so the thesis can
describe it as a consistent rule set, not ad-hoc strings. Used for PERSON and LOCATION only; ADDRESS is
atomic.

## API

```
classify(name: str, gender: str | None) -> Pattern
decline(base: str, pattern: Pattern, case: str) -> str
all_forms(base: str, pattern: Pattern) -> dict[str, str]   # {case: form} over CASES
```

`CASES = ("nom", "gen", "dat", "acc", "ins", "loc")`. First name and surname are classified and declined
**independently** (so "Jan Kowalski" → "Jana Kowalskiego" = gen(Jan)+gen(Kowalski)).

## Direction of use (why fixed tables suffice)

We **only generate** forms from a *known base + known pattern*:
- the **original**'s base form (`lemma`) and `case` come from spaCy (research D1);
- the **fake**'s base is what we generated, and we `classify()` it by suffix.

We never parse an arbitrary inflected surface — that hard direction is spaCy's. So a handful of suffix
tables covers the common patterns.

## Patterns and bands (suffix substitution)

| Pattern | Trigger (suffix / gender) | Example base | Method |
|---|---|---|---|
| `ADJ_M` | `-ski/-cki/-dzki` (masc.) | Kowalski | adjectival: gen `-ego`, dat `-emu`, acc `-ego`, ins `-im`, loc `-im` |
| `ADJ_F` | `-ska/-cka/-dzka` (fem.) | Kowalska | adjectival fem: gen/dat/loc `-iej`, acc `-ą`, ins `-ą` |
| `NOUN_M_CONS` | consonant-ending masc. | Nowak, Marek | noun masc: gen `-a`, dat `-owi`, acc `-a`, ins `-iem`, loc `-u`; **fleeting e** (Marek→Marka), common stem softening |
| `NOUN_F_A` | `-a`-ending fem. | Anna, Anka | noun fem: gen `-y`, dat/loc `-ie` (**k/g softening** Anka→Ance), acc `-ę`, ins `-ą` |
| `CITY_M` | masc. `-ów`/consonant | Kraków | loc `w Krakowie`, etc. (table per ending) |
| `CITY_F` | fem. `-a` | Warszawa | gen `-y`, loc `-ie`, etc. |
| `CITY_N` | neuter | Zakopane | neuter city table |
| `INDECLINABLE` | foreign; fem. surname not `-a`; `-o` endings | Nguyen, Linde, Moniuszko | **base form for every case** (documented limitation, Constitution IX) |

(The exact suffix tables are an implementation detail finalized in code; the bands above are the
contract — adding/refining a rule must not change the public function signatures.)

## Guarantees / limitations

- All forms of one classified base resolve through `all_forms` to a single fake (consistency).
- `INDECLINABLE` → identical base form across cases (rare/foreign names; FR-020 limitation).
- Coverage is the common patterns only; correctness across every Polish lemma is **not** a goal (Constitution
  IX). This is recorded in the Epic 3 limitations doc.

## Test surface (`test_inflection.py`)

Each pattern across all six cases; INDECLINABLE returns base for every case; independent first/last
declension ("Jana Kowalskiego"); city patterns ("Kraków"→"w Krakowie"); fleeting-e and k/g softening
sample cases.
