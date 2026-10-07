"""
Instantiate built-in templates and generate custom projects via AI.
"""
from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from app.templates.catalog import TemplateCatalog
from app.racks.manager import RackManager
from app.documents.manager import DocumentManager
from app.ai.factory import AIProviderFactory
from app.schemas import AIProvider

logger = logging.getLogger(__name__)


class ProjectGenerator:
    """Creates full projects from templates or from a natural-language brief."""

    def __init__(
        self,
        rack_manager: Optional[RackManager] = None,
        doc_manager: Optional[DocumentManager] = None,
    ):
        self.racks = rack_manager or RackManager()
        self.docs = doc_manager or DocumentManager()

    # ------------------------------------------------------------------
    # Instantiate a built-in template
    # ------------------------------------------------------------------

    def instantiate_template(
        self,
        template_id: str,
        *,
        name_override: Optional[str] = None,
        seed_documents: bool = True,
    ) -> dict:
        """
        Create a Project + Notebooks from a catalog template.
        Optionally index seed text files into ChromaDB.
        Returns the rack dict enriched with notebook list.
        """
        tpl = TemplateCatalog.get(template_id)
        if not tpl:
            raise ValueError(
                f"Plantilla '{template_id}' no encontrada. "
                f"Disponibles: {TemplateCatalog.ids()}"
            )

        # Avoid id collision: if template id already exists, create with suffix
        desired_id = tpl["id"]
        if self.racks.get(desired_id):
            desired_id = None  # let manager slugify a unique id from name

        rack = self.racks.create(
            name=name_override or tpl["name"],
            description=tpl.get("description", ""),
            system_instruction=tpl.get("system_instruction", ""),
            operating_instruction=tpl.get("operating_instruction", ""),
            icon=tpl.get("icon", "📦"),
            rack_id=desired_id,
        )
        rack_id = rack["id"]

        created_notebooks = []
        for nb_def in tpl.get("notebooks", []):
            nb = self.racks.create_notebook(
                rack_id,
                name=nb_def["name"],
                description=nb_def.get("description", ""),
                domain=nb_def.get("domain", ""),
                notebook_id=nb_def.get("id"),
            )
            if not nb:
                continue
            created_notebooks.append(nb)

            if seed_documents:
                for seed in nb_def.get("seed_files", []):
                    self._ingest_text(
                        rack_id=rack_id,
                        notebook_id=nb["id"],
                        filename=seed["filename"],
                        content=seed["content"],
                    )

        # Reload
        rack = self.racks.get(rack_id)
        logger.info(
            "Instantiated template '%s' → project '%s' with %d notebooks",
            template_id,
            rack_id,
            len(created_notebooks),
        )
        return rack

    # ------------------------------------------------------------------
    # AI-powered generation from a brief
    # ------------------------------------------------------------------

    async def generate_from_brief(
        self,
        brief: str,
        *,
        api_key: str,
        provider: AIProvider | str = AIProvider.GEMINI,
        model: Optional[str] = None,
        language: str = "es",
        seed_documents: bool = True,
        num_notebooks: int = 3,
    ) -> dict:
        """
        Use an LLM to design a project (persona, operating rules, notebooks,
        and seed content) from a short natural-language brief, then persist it.
        """
        if num_notebooks < 1 or num_notebooks > 8:
            raise ValueError("num_notebooks must be between 1 and 8")

        provider_instance = AIProviderFactory.create(
            provider=provider,
            api_key=api_key,
            model=model,
            temperature=0.4,
            max_tokens=4096,
        )

        system = (
            "Eres un arquitecto de sistemas de conocimiento (RAG). "
            "Diseñas proyectos especializados con persona, reglas de uso de cuadernos "
            "y contenido semilla práctico. Respondes SOLO con JSON válido, sin markdown."
        )
        user = f"""Diseña un proyecto completo a partir de este brief del usuario:

\"\"\"{brief.strip()}\"\"\"

Responde ÚNICAMENTE con un JSON con esta estructura exacta:
{{
  "name": "nombre corto del proyecto",
  "icon": "un emoji",
  "description": "descripción de 1-2 frases",
  "system_instruction": "instrucción de persona completa (quién es, cómo responde, límites)",
  "operating_instruction": "cómo debe usar cada cuaderno y cómo combinarlos",
  "notebooks": [
    {{
      "name": "nombre del cuaderno",
      "domain": "ámbito de conocimiento",
      "description": "descripción corta",
      "seed_content": "texto operativo concreto (protocolos, tablas, checklists) de al menos 300 palabras, listo para indexar"
    }}
  ]
}}

Reglas:
- Idioma del contenido: {"español" if language.startswith("es") else language}.
- Exactamente {num_notebooks} cuadernos.
- seed_content debe ser útil en el día a día, con números y umbrales cuando aplique.
- No inventes leyes ni dosis farmacéuticas concretas de marcas; usa rangos orientativos y advierte verificar con la fuente oficial.
- JSON puro, sin comentarios ni bloques de código.
"""

        raw_text, _tokens = await provider_instance.generate(system, user)
        data = self._parse_json_response(raw_text)

        # Persist
        rack = self.racks.create(
            name=data.get("name") or "Proyecto generado",
            description=data.get("description", ""),
            system_instruction=data.get("system_instruction", ""),
            operating_instruction=data.get("operating_instruction", ""),
            icon=data.get("icon") or "📦",
        )
        rack_id = rack["id"]

        for nb_data in data.get("notebooks", [])[:num_notebooks]:
            nb = self.racks.create_notebook(
                rack_id,
                name=nb_data.get("name") or "Cuaderno",
                description=nb_data.get("description", ""),
                domain=nb_data.get("domain", ""),
            )
            if not nb:
                continue
            if seed_documents and nb_data.get("seed_content"):
                safe_name = re.sub(r"[^\w\-]+", "_", nb["name"].lower())[:40]
                self._ingest_text(
                    rack_id=rack_id,
                    notebook_id=nb["id"],
                    filename=f"{safe_name}_seed.txt",
                    content=nb_data["seed_content"],
                )

        rack = self.racks.get(rack_id)
        logger.info("AI-generated project '%s' from brief", rack_id)
        return rack

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ingest_text(
        self, rack_id: str, notebook_id: str, filename: str, content: str
    ) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            self.docs.ingest_file(
                tmp_path,
                original_filename=filename,
                rack_id=rack_id,
                notebook_id=notebook_id,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Extract JSON from model output (handles accidental markdown fences)."""
        text = text.strip()
        # Strip ```json ... ```
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        # Find first { ... last }
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("El modelo no devolvió JSON válido")
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido del modelo: {exc}") from exc
