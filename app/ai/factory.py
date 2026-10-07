"""
Factory Pattern – creates the correct AI provider at runtime
without the rest of the application knowing concrete classes.
"""
from typing import Optional

from .base import BaseAIProvider
from .gemini_provider import GeminiProvider
from .openai_compatible import DeepSeekProvider, GLMProvider
from app.schemas import AIProvider


class AIProviderFactory:
    """
    Central factory. Add a new provider by:
      1. Implementing BaseAIProvider
      2. Registering it in _REGISTRY
    """

    _REGISTRY = {
        AIProvider.GEMINI: GeminiProvider,
        AIProvider.DEEPSEEK: DeepSeekProvider,
        AIProvider.GLM: GLMProvider,
    }

    @classmethod
    def create(
        cls,
        provider: AIProvider | str,
        api_key: str,
        model: Optional[str] = None,
        **kwargs,
    ) -> BaseAIProvider:
        if isinstance(provider, str):
            try:
                provider = AIProvider(provider.lower())
            except ValueError:
                raise ValueError(
                    f"Unknown provider '{provider}'. "
                    f"Supported: {[p.value for p in AIProvider]}"
                )

        concrete = cls._REGISTRY.get(provider)
        if concrete is None:
            raise ValueError(f"Provider {provider} is registered but has no implementation")

        return concrete(api_key=api_key, model=model, **kwargs)

    @classmethod
    def available_providers(cls) -> list[str]:
        return [p.value for p in cls._REGISTRY.keys()]
