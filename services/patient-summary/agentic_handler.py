# Wrapper interface for LLM inference backends.
# Swap the backing implementation (Ollama, Claude API, etc.)
# without changing service logic.
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

import ollama

logger = logging.getLogger(__name__)


class AgenticHandler(ABC):
    """
    Abstract base class for LLM-based agents.

    Subclasses must implement the model-specific logic for sending messages
    and receiving responses.
    """

    def __init__(self, model_name: str, api_url: str, system_prompt: Optional[str] = None) -> None:
        """
        Initialize the agentic handler.

        Args:
            model_name: Name of the model to use (e.g., "mistral", "neural-chat")
            api_url: Base URL of the LLM API endpoint (e.g., "http://localhost:11434")
            system_prompt: Optional system prompt to guide the model's behavior
        """
        self.model_name = model_name
        self.api_url = api_url.rstrip("/")
        self.system_prompt = system_prompt

    @abstractmethod
    async def send_message(self, prompt: str) -> str:
        """
        Send a message to the LLM agent and await its response.

        Args:
            prompt: The prompt to send to the agent (system prompt applied automatically)

        Returns:
            str: The complete response from the agent
        """
        ...

    @abstractmethod
    async def complete(self, prompt: str) -> AsyncIterator[str]:
        """
        Stream completion tokens from the LLM agent.

        Args:
            prompt: The prompt to send to the agent (system prompt applied automatically)

        Yields:
            str: Completion tokens as they arrive
        """
        ...


class OllamaAgentHandler(AgenticHandler):
    """
    Handler for Ollama-based LLM agents.

    Uses the Ollama Python library to send messages and receive streamed or
    non-streamed responses.
    """

    def __init__(self, model_name: str, api_url: str, system_prompt: Optional[str] = None) -> None:
        """
        Initialize the Ollama handler.

        Args:
            model_name: Name of the model to use (e.g., "mistral", "neural-chat")
            api_url: Base URL of the Ollama API endpoint (e.g., "http://localhost:11434")
            system_prompt: Optional system prompt to guide the model's behavior
        """
        super().__init__(model_name, api_url, system_prompt)
        # Initialize Ollama client with the provided API URL/host
        self.client = ollama.AsyncClient(host=self.api_url)

    async def send_message(self, prompt: str) -> str:
        """
        Send a message to Ollama and await the full response.

        Args:
            prompt: The prompt/question to send

        Returns:
            str: The complete response from the model

        Raises:
            Exception: If the Ollama request fails
        """
        logger.info("send_message: model=%s prompt_len=%d", self.model_name, len(prompt))

        try:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await self.client.chat(
                model=self.model_name,
                messages=messages,
                stream=False,
            )
            return response.message.content
        except Exception as e:
            logger.error("send_message: Ollama error: %s", e)
            raise

    async def complete(self, prompt: str) -> AsyncIterator[str]:
        """
        Stream completion tokens from Ollama.

        Args:
            prompt: The prompt to send

        Yields:
            str: Completion tokens as they arrive from the API

        Raises:
            Exception: If the Ollama request fails
        """
        logger.info("complete: model=%s prompt_len=%d", self.model_name, len(prompt))

        try:
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": prompt})

            async for chunk in await self.client.chat(
                model=self.model_name,
                messages=messages,
                stream=True,
            ):
                if chunk.message.content:
                    yield chunk.message.content
        except Exception as e:
            logger.error("complete: Ollama error: %s", e)
            raise
