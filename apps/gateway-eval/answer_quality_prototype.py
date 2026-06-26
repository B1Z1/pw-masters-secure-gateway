"""PROTOTYP — jakość odpowiedzi LLM przy pseudonimizacji (F-34, oś druga).

Trzy ramiona dla każdej umowy i pytania:
  A (oryginał)      — oryginalny tekst → LLM bezpośrednio.
  B (brama)         — tekst → gateway (pseudonimizacja → LLM → de-pseudonimizacja).
  C (naiwna maska)  — PII zastąpione [OSOBA]/[PESEL]/… (z gold) → LLM bezpośrednio.

Metryki:
  - pytania FAKTOGRAFICZNE: udział wartości z gold obecnych w odpowiedzi (obiektywne).
    Ramię C z założenia wypadnie słabo (dane ukryte) — to pokazuje, że naiwne maskowanie
    niszczy użyteczność faktograficzną.
  - pytanie ROZUMOWE: ROUGE-L(A,B) i ROUGE-L(A,C) — czy odpowiedź pozostaje równoważna.

To PROTOTYP do oceny sensowności podejścia, nie część produkcyjnego harnessa. Jeśli
liczby mają sens, F-34 warto dopracować przez speckit.

Uruchomienie:
  PYTHONPATH=. .venv/bin/python answer_quality_prototype.py --sample 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import httpx

from gateway_eval.corpus.gold_standard import GoldDocument, load_corpus
from gateway_eval.gateway_client.evaluation_client import EvaluationClient
from gateway_eval.scoring.surface_matching import normalize, tokens

# Naiwne etykiety maskujące (ramię C) — typ kanoniczny → token.
_MASK_LABEL = {
    "PERSON": "[OSOBA]",
    "LOCATION": "[MIEJSCOWOSC]",
    "ADDRESS": "[ADRES]",
    "PESEL": "[PESEL]",
    "NIP": "[NIP]",
    "REGON": "[REGON]",
    "BANK_ACCOUNT": "[NR_RACHUNKU]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "PHONE_NUMBER": "[TELEFON]",
    "DATE_TIME": "[DATA]",
}

_SYSTEM = (
    "Jesteś asystentem analizującym polskie umowy cywilnoprawne. Odpowiadaj zwięźle, "
    "po polsku, wyłącznie na podstawie treści umowy."
)

# Pytania faktograficzne (typ -> oczekiwane = wartości gold tego typu) + rozumowe.
FACTUAL_QUESTIONS = [
    ("osoby", "Wymień wszystkie osoby (imię i nazwisko) występujące w umowie.", "PERSON"),
    ("pesel", "Podaj wszystkie numery PESEL występujące w umowie.", "PESEL"),
    ("rachunek", "Podaj numer rachunku bankowego wskazany w umowie do płatności.", "BANK_ACCOUNT"),
]
REASONING_QUESTIONS = [
    ("streszczenie", "Streść w 2-3 zdaniach przedmiot umowy oraz główne zobowiązania stron."),
]

_DIGITS = re.compile(r"\d+")


def _digits(text: str) -> str:
    return "".join(_DIGITS.findall(text))


def mask_with_gold(document: GoldDocument) -> str:
    """Ramię C: zastąp każdą encję gold naiwnym tokenem (od końca, by offsety były OK)."""
    text = document.text
    for entity in sorted(document.entities, key=lambda e: e.start, reverse=True):
        label = _MASK_LABEL.get(entity.type, "[DANE]")
        text = text[: entity.start] + label + text[entity.end :]
    return text


def mask_with_tokens(document: GoldDocument) -> tuple[str, dict[str, str]]:
    """Ramię D: rozróżnialne, ODWRACALNE tokeny ([OSOBA_1], [OSOBA_2], …).

    Ta sama wartość → ten sam token (spójność jak w pseudonimizacji). Zwraca tekst
    zamaskowany i mapę token → oryginał (do odtworzenia odpowiedzi)."""
    counters: dict[str, int] = {}
    value_to_token: dict[tuple[str, str], str] = {}
    for entity in sorted(document.entities, key=lambda e: e.start):
        key = (entity.type, entity.text)
        if key not in value_to_token:
            counters[entity.type] = counters.get(entity.type, 0) + 1
            base_label = _MASK_LABEL.get(entity.type, "[DANE]").strip("[]")
            value_to_token[key] = f"[{base_label}_{counters[entity.type]}]"

    text = document.text
    for entity in sorted(document.entities, key=lambda e: e.start, reverse=True):
        token = value_to_token[(entity.type, entity.text)]
        text = text[: entity.start] + token + text[entity.end :]

    token_to_value = {token: value for (_, value), token in value_to_token.items()}
    return text, token_to_value


def restore_tokens(answer: str, token_to_value: dict[str, str]) -> str:
    """Algorytm demaskujący ramienia D: token → oryginał (najdłuższe najpierw)."""
    restored = answer
    for token in sorted(token_to_value, key=len, reverse=True):
        restored = re.sub(
            re.escape(token), token_to_value[token], restored, flags=re.IGNORECASE
        )
    return restored


def expected_values(document: GoldDocument, entity_type: str) -> list[str]:
    seen: list[str] = []
    for entity in document.entities:
        if entity.type == entity_type and entity.text not in seen:
            seen.append(entity.text)
    return seen


def _value_present(value: str, answer: str) -> bool:
    if _digits(value) and len(_digits(value)) >= 6:  # PESEL/rachunek itp.
        return _digits(value) in _digits(answer)
    normalized_answer = normalize(answer)
    if normalize(value) in normalized_answer:
        return True
    # dla nazwisk dopuść trafienie po samym nazwisku (ostatni token)
    parts = tokens(value)
    return len(parts) > 1 and normalize(parts[-1]) in normalized_answer


def factual_score(expected: list[str], answer: str) -> float:
    if not expected:
        return float("nan")
    hits = sum(1 for value in expected if _value_present(value, answer))
    return hits / len(expected)


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[index - 1]))
        previous = current
    return previous[-1]


def rouge_l(reference: str, candidate: str) -> float:
    reference_tokens = tokens(normalize(reference))
    candidate_tokens = tokens(normalize(candidate))
    if not reference_tokens or not candidate_tokens:
        return 0.0
    lcs = _lcs_length(reference_tokens, candidate_tokens)
    precision = lcs / len(candidate_tokens)
    recall = lcs / len(reference_tokens)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


async def _ollama_chat(client: httpx.AsyncClient, model: str, prompt: str) -> str:
    response = await client.post(
        "/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
        },
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "")


async def run(args) -> None:
    documents = load_corpus(Path(args.corpus))[: args.sample]
    if not documents:
        raise SystemExit(f"brak dokumentów w {args.corpus}")

    bare_model = args.model.removeprefix("ollama/")
    ollama = httpx.AsyncClient(base_url=args.ollama_url, timeout=args.timeout)
    gateway = EvaluationClient(args.base_url, timeout_s=args.timeout, max_retries=1)

    rows: list[dict] = []
    try:
        async with gateway:
            for index, document in enumerate(documents, start=1):
                masked = mask_with_gold(document)
                masked_tokens, token_map = mask_with_tokens(document)
                print(f"[{index}/{len(documents)}] {document.doc_id} …", flush=True)

                for qid, question, gold_type in FACTUAL_QUESTIONS:
                    prompt_a = f"{document.text}\n\nPytanie: {question}"
                    prompt_c = f"{masked}\n\nPytanie: {question}"
                    prompt_d = f"{masked_tokens}\n\nPytanie: {question}"
                    answer_a = await _ollama_chat(ollama, bare_model, prompt_a)
                    answer_c = await _ollama_chat(ollama, bare_model, prompt_c)
                    answer_d_raw = await _ollama_chat(ollama, bare_model, prompt_d)
                    answer_d = restore_tokens(answer_d_raw, token_map)
                    chat_b = await gateway.chat_completions(prompt_a, f"aq-{document.doc_id}-{qid}", args.model)
                    answer_b = chat_b.answer
                    await gateway.delete_session(f"aq-{document.doc_id}-{qid}")

                    expected = expected_values(document, gold_type)
                    rows.append({
                        "doc": document.doc_id, "q": qid, "kind": "factual",
                        "expected": expected,
                        "score_A": factual_score(expected, answer_a),
                        "score_B": factual_score(expected, answer_b),
                        "score_C": factual_score(expected, answer_c),
                        "score_D": factual_score(expected, answer_d),
                        "answer_A": answer_a, "answer_B": answer_b,
                        "answer_C": answer_c, "answer_D": answer_d,
                        "answer_D_raw": answer_d_raw,
                    })

                for qid, question in REASONING_QUESTIONS:
                    prompt_a = f"{document.text}\n\nPytanie: {question}"
                    prompt_c = f"{masked}\n\nPytanie: {question}"
                    prompt_d = f"{masked_tokens}\n\nPytanie: {question}"
                    answer_a = await _ollama_chat(ollama, bare_model, prompt_a)
                    answer_c = await _ollama_chat(ollama, bare_model, prompt_c)
                    answer_d = restore_tokens(
                        await _ollama_chat(ollama, bare_model, prompt_d), token_map
                    )
                    chat_b = await gateway.chat_completions(prompt_a, f"aq-{document.doc_id}-{qid}", args.model)
                    answer_b = chat_b.answer
                    await gateway.delete_session(f"aq-{document.doc_id}-{qid}")
                    rows.append({
                        "doc": document.doc_id, "q": qid, "kind": "reasoning",
                        "rougeL_AB": rouge_l(answer_a, answer_b),
                        "rougeL_AC": rouge_l(answer_a, answer_c),
                        "rougeL_AD": rouge_l(answer_a, answer_d),
                        "answer_A": answer_a, "answer_B": answer_b,
                        "answer_C": answer_c, "answer_D": answer_d,
                    })
    finally:
        await ollama.aclose()

    _summarize(rows, args)


def _mean(values: list[float]) -> float:
    clean = [v for v in values if v == v]  # odrzuć NaN
    return round(sum(clean) / len(clean), 4) if clean else float("nan")


def _summarize(rows: list[dict], args) -> None:
    factual = [r for r in rows if r["kind"] == "factual"]
    reasoning = [r for r in rows if r["kind"] == "reasoning"]
    docs = len({r["doc"] for r in rows})
    print(f"\n================ WYNIKI (prototyp F-34) — {docs} umów ================")
    if factual:
        print(f"Faktografia (n={len(factual)} pytań) — średni udział wartości gold w odpowiedzi:")
        print(f"  A (oryginał)                 : {_mean([r['score_A'] for r in factual])}")
        print(f"  B (brama, realistyczny fake) : {_mean([r['score_B'] for r in factual])}")
        print(f"  C (anonim., bez odtworzenia) : {_mean([r['score_C'] for r in factual])}")
        print(f"  D (tokeny + odtworzenie)     : {_mean([r.get('score_D', float('nan')) for r in factual])}")
    if reasoning:
        print("Rozumowanie — ROUGE-L vs oryginał (1.0 = identyczne):")
        print(f"  ROUGE-L(A,B)  brama (realist. fake) : {_mean([r['rougeL_AB'] for r in reasoning])}")
        print(f"  ROUGE-L(A,C)  anonim. bez odtw.     : {_mean([r['rougeL_AC'] for r in reasoning])}")
        print(f"  ROUGE-L(A,D)  tokeny + odtworzenie  : {_mean([r.get('rougeL_AD', float('nan')) for r in reasoning])}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nzapisano szczegóły do {out}")
    print("Interpretacja: B≈A → pseudonimizacja nie szkodzi; C → bez odtworzenia tracisz dane;")
    print("               B vs D → czy REALIZM substytutu ma znaczenie (oba mają odtworzenie).")


def _parse_args():
    parser = argparse.ArgumentParser(description="Prototyp jakości odpowiedzi LLM (F-34).")
    parser.add_argument("--sample", type=int, default=5)
    parser.add_argument("--corpus", default="gateway_eval/corpus/data/synthetic")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--model", default="ollama/qwen2.5:3b")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--out", default="eval-results/answer_quality_prototype.json")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(_parse_args()))
