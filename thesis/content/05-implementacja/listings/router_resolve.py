class LLMRouter(LLMProvider):
    ...

    def _resolve(self, model: str) -> tuple[str, str]:
        """Zwraca (prefiks, model-do-wysłania) albo zgłasza unknown_model.

        Prefiks „ollama/" jest usuwany z wysyłanej nazwy modelu; pozostałe
        prefiksy pozostawiają nazwę bez zmian.
        """
        for prefix in self._factories:
            if model.startswith(prefix):
                if prefix == _OLLAMA_PREFIX:
                    return prefix, model[len(_OLLAMA_PREFIX) :]
                return prefix, model
        recognized_prefixes = ", ".join(self._factories)
        raise LLMProviderError(
            f"Unknown model '{model}'. Recognized prefixes: {recognized_prefixes}",
            kind="unknown_model",
        )
