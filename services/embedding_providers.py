from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Optional


class EmbeddingProvider(ABC):
    """
    Abstract base class for all embedding providers.
    """

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for the given text.
        """
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embeddings via the official Python client.

    Requires:
    - OPENAI_API_KEY
    - Optional: OPENAI_EMBEDDING_MODEL (default: text-embedding-3-small)
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    def embed(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(model=self._model, input=text)
        return list(resp.data[0].embedding)


class GeminiEmbeddingProvider(EmbeddingProvider):
    """
    Google Gemini embeddings via google-generativeai.

    Requires:
    - GOOGLE_API_KEY
    - Optional: GEMINI_EMBEDDING_MODEL (default: models/text-embedding-004)
    """

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set.")

        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")
        self._model = genai.GenerativeModel(model_name)

    def embed(self, text: str) -> List[float]:
        resp = self._model.embed_content(content=text)
        return list(resp.embedding.values)


class AnthropicEmbeddingProvider(EmbeddingProvider):
    """
    Anthropic embeddings (Claude) via anthropic client.

    Requires:
    - ANTHROPIC_API_KEY
    - Optional: ANTHROPIC_EMBEDDING_MODEL
    """

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.getenv("ANTHROPIC_EMBEDDING_MODEL", "claude-3-haiku-20240307")

    def embed(self, text: str) -> List[float]:
        # Note: API shape may evolve; this assumes an embeddings endpoint exists.
        resp = self._client.embeddings.create(model=self._model, input=text)
        return list(resp.data[0].embedding)


def get_provider_from_env() -> Optional[EmbeddingProvider]:
    """
    Select an embedding provider based on the EMBEDDING_PROVIDER env var.

    EMBEDDING_PROVIDER can be one of: openai, gemini, anthropic.
    If unset or invalid, returns None and the caller should treat this as
    "no external embeddings configured".
    """
    provider_name = os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
    if not provider_name:
        return None

    try:
        if provider_name == "openai":
            return OpenAIEmbeddingProvider()
        if provider_name in ("gemini", "google"):
            return GeminiEmbeddingProvider()
        if provider_name in ("claude", "anthropic"):
            return AnthropicEmbeddingProvider()
    except RuntimeError:
        # Missing credentials or misconfiguration; treat as "no provider".
        return None

    return None


