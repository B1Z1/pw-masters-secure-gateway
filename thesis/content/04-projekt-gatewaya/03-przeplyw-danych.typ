#import "../../utils.typ": todo, silentheading, flex-caption
#import "../../requirements.typ": fletcher
#import fletcher: diagram, node, edge

== Przepływ danych w procesie pseudonimizacji <sec:przeplyw>

#todo[
  Pełny round-trip: żądanie → wykrywanie → podstawienie (zapis mapowania) → wysłanie do modelu
  (tylko dane syntetyczne) → odpowiedź → przywrócenie oryginałów → zwrot. Granica zaufania:
  co~ją przekracza (tylko pseudonimy; mapowanie i~klucz zostają w~systemie), nawiązanie do
  @sec:granica-zaufania. Synchroniczność. Własny diagram przepływu (rys:przeplyw).
]
