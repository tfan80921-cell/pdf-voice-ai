"""
Google Gemini provider using the official google-generativeai SDK.
"""
import asyncio
from typing import Optional

import google.generativeai as genai

from .base import BaseAIProvider
from app.config import settings


class GeminiProvider(BaseAIProvider):
    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return settings.DEFAULT_MODEL_GEMINI

    def __init__(self, api_key: str, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(
            model_name=self.model,
            generation_config=genai.types.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, Optional[int]]:
        # google-generativeai is synchronous; run in thread pool
        def _sync_call() -> tuple[str, Optional[int]]:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = self._model.generate_content(full_prompt)
            text = response.text or ""
            # Gemini usage metadata is available in newer SDKs
            tokens = None
            try:
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    tokens = response.usage_metadata.total_token_count
            except Exception:
                pass
            return text.strip(), tokens

        return await asyncio.to_thread(_sync_call)
