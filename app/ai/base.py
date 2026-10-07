"""
Abstract base class for all AI providers.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseAIProvider(ABC):
    """Contract that every concrete provider must implement."""

    def __init__(self, api_key: str, model: Optional[str] = None, **kwargs):
        if not api_key or len(api_key) < 10:
            raise ValueError("A valid API key is required")
        self.api_key = api_key
        self.model = model or self.default_model
        self.temperature = kwargs.get("temperature", 0.3)
        self.max_tokens = kwargs.get("max_tokens", 2048)

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        ...

    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> tuple[str, Optional[int]]:
        """Returns (answer_text, tokens_used_or_None)."""
        ...

    def build_rag_prompt(
        self,
        context: str,
        query: str,
        language: Optional[str] = None,
        system_instruction: Optional[str] = None,
        operating_instruction: Optional[str] = None,
        notebook_catalog: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Build system + user prompts for multi-notebook RAG.

        - system_instruction  → quién es el asistente (persona)
        - operating_instruction → cómo debe usar los cuadernos
        - notebook_catalog    → lista de cuadernos disponibles
        - context             → fragmentos recuperados (ya etiquetados por cuaderno)
        """
        lang_instruction = ""
        if language:
            primary = language.split("-")[0].lower()
            if primary == "es":
                lang_instruction = " Responde siempre en español."
            elif primary == "en":
                lang_instruction = " Always answer in English."
            else:
                lang_instruction = f" Answer in the language corresponding to locale '{language}'."

        grounding = (
            "Responde ÚNICAMENTE basándote en el contexto de documentos proporcionado. "
            "Si la información no está en el contexto, di claramente que no la encuentras. "
            "Sé preciso, conciso y cita el cuaderno y el archivo de origen cuando sea posible."
        )

        parts: list[str] = []

        if system_instruction and system_instruction.strip():
            parts.append(system_instruction.strip())
        else:
            parts.append("Eres un asistente experto en análisis de documentos.")

        if operating_instruction and operating_instruction.strip():
            parts.append(
                "### Instrucciones de funcionamiento del proyecto\n"
                + operating_instruction.strip()
            )

        if notebook_catalog and notebook_catalog.strip():
            parts.append(
                "### Cuadernos disponibles en este proyecto\n"
                + notebook_catalog.strip()
            )

        parts.append(grounding + lang_instruction)
        system = "\n\n".join(parts)

        user = (
            f"### Contexto recuperado de los cuadernos:\n{context}\n\n"
            f"### Pregunta del usuario:\n{query}\n\n"
            "### Respuesta:"
        )
        return system, user
