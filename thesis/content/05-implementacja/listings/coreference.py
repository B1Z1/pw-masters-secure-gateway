class CoreferenceResolver:
    """Decyduje, czy wzmianka nazwy ma użyć zamiennika istniejącej już osoby.

    Zwraca bazę zamiennika do ponownego użycia albo None, gdy należy utworzyć
    nową osobę (0 dopasowań -> nowa; >=2 różne dopasowania -> niejednoznaczne,
    również nowa; nazwiska, którego nie da się dopasować -> nowa).
    """

    def resolve(
        self, entity_type: str, normalized_key: str, coref_records: list[dict]
    ) -> str | None:
        matches = [
            record
            for record in coref_records
            if record["entity_type"] == entity_type
               and lemma_overlap(normalized_key, record["lemma"])
        ]
        distinct_fake_bases = {record["fake_base"] for record in matches}

        if len(distinct_fake_bases) != 1:
            return None

        matched = matches[0]

        return aligned_fake(normalized_key, matched["lemma"], matched["fake_base"])
