class ChatMessage(BaseModel):
    """Pojedynczy komunikat rozmowy zgodny z konwencją OpenAI."""

    role: str
    content: str


@dataclass(frozen=True)
class CompletionResult:
    """Wartość zwracana przez port dostawcy.

    Adapter sam podaje nazwę dostawcy oraz finish_reason znormalizowany do
    słownika OpenAI, dzięki czemu endpoint pozostaje niezależny od dostawcy.
    """

    content: str
    finish_reason: str  # znormalizowane: „stop" | „length"
    provider: str  # „openai" | „anthropic" | „ollama" | „echo"


class LLMProviderError(Exception):
    """Błąd dostawcy z czytelnym komunikatem i dyskryminatorem kind (mapowanym na HTTP)."""

    def __init__(self, message: str, *, kind: ProviderErrorKind) -> None:
        super().__init__(message)
        self.kind: ProviderErrorKind = kind


class LLMProvider(abc.ABC):
    """Abstrakcyjny dostawca: przyjmuje tablicę komunikatów, zwraca odpowiedź modelu."""

    @abc.abstractmethod
    async def complete(
        self, messages: list[ChatMessage], *, model: str
    ) -> CompletionResult:
        """Zwraca odpowiedź asystenta albo zgłasza LLMProviderError przy błędzie."""

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Lekka sonda dostępności (zarezerwowana dla przyszłego /health)."""
