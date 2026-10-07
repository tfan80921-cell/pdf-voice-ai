"""
OpenAI-compatible providers (DeepSeek, GLM / Zhipu AI).
Both expose an OpenAI-style chat completions endpoint.
"""
from typing import Optional

from openai import AsyncOpenAI

from .base import BaseAIProvider
from app.config import settings


class DeepSeekProvider(BaseAIProvider):
    BASE_URL = "https://api.deepseek.com/v1"

    @property
    def provider_name(self) -> str:
        return "deepseek"

    @property
    def default_model(self) -> str:
        return settings.DEFAULT_MODEL_DEEPSEEK

    def __init__(self, api_key: str, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL,
            timeout=60.0,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, Optional[int]]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else None
        return text.strip(), tokens


class GLMProvider(BaseAIProvider):
    """
    Zhipu AI (GLM) – OpenAI-compatible endpoint.
    Official base URL: https://open.bigmodel.cn/api/paas/v4/
    """
    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"

    @property
    def provider_name(self) -> str:
        return "glm"

    @property
    def default_model(self) -> str:
        return settings.DEFAULT_MODEL_GLM

    def __init__(self, api_key: str, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, model, **kwargs)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.BASE_URL,
            timeout=60.0,
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, Optional[int]]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else None
        return text.strip(), tokens
