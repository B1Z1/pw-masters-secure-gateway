class EchoProvider(LLMProvider):
    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        content = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == "user"
            ),
            messages[-1].content if messages else "",
        )
        return CompletionResult(content=content, finish_reason="stop", provider="echo")

    async def health_check(self) -> bool:
        return True
