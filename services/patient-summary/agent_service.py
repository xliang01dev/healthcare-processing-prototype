# Wrapper interface for LLM inference backends.
# Swap the backing implementation (Ollama, static dictionary, Anthropic Claude API)
# without changing service logic.
from abc import ABC, abstractmethod
from typing import AsyncIterator


class AgentService(ABC):
    @abstractmethod
    async def complete(self, prompt: str, context: dict) -> AsyncIterator[str]:
        ...
