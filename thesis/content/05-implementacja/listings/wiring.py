@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()

    return LLMRouter(
        {
            "gpt-": lambda: OpenAIProvider(settings.openai_api_key),
            "claude-": lambda: AnthropicProvider(
                settings.anthropic_api_key, settings.anthropic_max_tokens
            ),
            "ollama/": lambda: OllamaProvider(
                settings.ollama_base_url, settings.ollama_timeout
            ),
        },
        default_model=settings.default_model,
    )
