# Kompilacja pracy dyplomowej (szablon wut-thesis 0.2.0).
# Fonty ładowane z lokalnego katalogu fonts/ przez --font-path.

TYPST ?= typst
MAIN  := thesis.typ
OUT   := thesis.pdf
FONTS := fonts

.PHONY: build watch build-print clean

# Kompilacja jednorazowa (wersja robocza, draft).
build:
	$(TYPST) compile $(MAIN) $(OUT) --font-path $(FONTS)

# Kompilacja w trybie ciągłym (przeliczanie przy każdym zapisie).
watch:
	$(TYPST) watch $(MAIN) $(OUT) --font-path $(FONTS)

# Wersja do druku/oprawy: ustaw `in-print: true` w thesis.typ przed użyciem.
# Przed oddaniem do APD wróć do `in-print: false` i `draft: false`.
build-print:
	$(TYPST) compile $(MAIN) thesis-print.pdf --font-path $(FONTS)

clean:
	rm -f $(OUT) thesis-print.pdf
