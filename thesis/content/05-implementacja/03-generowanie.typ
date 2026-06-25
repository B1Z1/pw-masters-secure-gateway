#import "../../utils.typ": todo, silentheading, flex-caption, code-listing-figure

== Generowanie danych zastępczych <sec:impl-generowanie>

#todo[
  Sekcja: implementacja generatora danych syntetycznych na bazie biblioteki Faker (lokalizacja
  `pl_PL`); buildery per typ; generowanie identyfikatorów o poprawnej sumie kontrolnej (reużycie
  logiki z modułu wykrywania); własny silnik fleksji oparty na tablicach sufiksów (fleksja tylko
  generująca); struktura `FakeValue` (forma podstawowa + rodzina form fleksyjnych); determinizm
  z ziarnem na potrzeby testów; zachowanie istotnych własności (rodzaj gramatyczny imienia, wariant
  REGON, offset PESEL). Listing z aplikacji (generowanie PESEL / odmiana). Źródła: dok. Faker,
  źródło o morfologii/fleksji polszczyzny.
]
