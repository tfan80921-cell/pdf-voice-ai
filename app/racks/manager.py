"""
Rack (Project) + Notebook manager.

Hierarchy:
  Project (Rack)
    ── system_instruction   → quién es
    ── operating_instruction → cómo usar los cuadernos
    ── Notebooks[]
          ── files (PDF / texto) en ChromaDB con metadata notebook_id
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:48] or uuid.uuid4().hex[:12]


class RackManager:
    """CRUD for Projects (Racks) and their Notebooks."""

    _instance: Optional["RackManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._store_path = settings.BASE_DIR / "racks.json"
        self._racks: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                self._racks = {r["id"]: r for r in data.get("racks", [])}
                for r in self._racks.values():
                    r.setdefault("notebooks", [])
                    r.setdefault("operating_instruction", "")
                    r.setdefault("system_instruction", r.get("system_instruction", ""))
                logger.info("Loaded %d projects from disk", len(self._racks))
            except Exception as exc:
                logger.error("Failed to load racks.json: %s", exc)
                self._racks = {}
        else:
            self._seed_examples()
            self._save()

    def _save(self) -> None:
        payload = {
            "version": 2,
            "updated_at": _now(),
            "racks": list(self._racks.values()),
        }
        self._store_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _seed_examples(self) -> None:
        vet_id = "vet-avicola"
        legal_id = "consejero-juridico"

        self._racks[vet_id] = {
            "id": vet_id,
            "name": "Veterinario Avícola",
            "description": "Especialista en sanidad, nutrición y manejo de aves de corral.",
            "icon": "🐔",
            "system_instruction": (
                "Eres un veterinario avícola con más de 20 años de experiencia. "
                "Respondes de forma clara, profesional y basada en evidencia. "
                "Prioriza bienestar animal, bioseguridad y rentabilidad del productor."
            ),
            "operating_instruction": (
                "Tienes varios cuadernos de conocimiento. Úsalos así:\n"
                "- Cuaderno 'Vacunación y Bioseguridad': protocolos de vacunas, calendarios y medidas de bioseguridad.\n"
                "- Cuaderno 'Nutrición': formulaciones, requerimientos nutricionales y problemas metabólicos.\n"
                "- Cuaderno 'Manejo y Producción': densidades, ventilación, iluminación y parámetros productivos.\n"
                "Si la pregunta cruza varios ámbitos, combina información de los cuadernos relevantes. "
                "Si un cuaderno no tiene información útil, indícalo y no inventes datos."
            ),
            "notebooks": [
                {
                    "id": "vacunacion-bioseguridad",
                    "name": "Vacunación y Bioseguridad",
                    "description": "Protocolos de vacunas, calendarios y bioseguridad",
                    "domain": "vacunación aviar, bioseguridad",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
                {
                    "id": "nutricion",
                    "name": "Nutrición",
                    "description": "Formulaciones y requerimientos nutricionales",
                    "domain": "nutrición aviar",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
                {
                    "id": "manejo-produccion",
                    "name": "Manejo y Producción",
                    "description": "Densidades, ventilación, iluminación y producción",
                    "domain": "manejo productivo avícola",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            ],
            "created_at": _now(),
            "updated_at": _now(),
        }

        self._racks[legal_id] = {
            "id": legal_id,
            "name": "Consejero Jurídico",
            "description": "Asesor legal que interpreta documentos y normativa.",
            "icon": "⚖️",
            "system_instruction": (
                "Eres un consejero jurídico experto. Analizas contratos, leyes y "
                "reglamentos con rigor. Nunca inventas normativa. Si algo no está "
                "en el contexto, dilo claramente y recomienda consultar la fuente oficial."
            ),
            "operating_instruction": (
                "Tienes cuadernos por área legal. Úsalos así:\n"
                "- Cuaderno 'Contratos': cláusulas, modelos y jurisprudencia contractual.\n"
                "- Cuaderno 'Normativa Laboral': estatuto de los trabajadores, convenios.\n"
                "Cita siempre el cuaderno y el documento de origen cuando sea posible."
            ),
            "notebooks": [
                {
                    "id": "contratos",
                    "name": "Contratos",
                    "description": "Cláusulas, modelos y jurisprudencia contractual",
                    "domain": "derecho contractual",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
                {
                    "id": "normativa-laboral",
                    "name": "Normativa Laboral",
                    "description": "Estatuto de los trabajadores y convenios",
                    "domain": "derecho laboral",
                    "created_at": _now(),
                    "updated_at": _now(),
                },
            ],
            "created_at": _now(),
            "updated_at": _now(),
        }
        logger.info("Seeded 2 example projects with notebooks")

    def list_racks(self) -> list[dict]:
        return sorted(self._racks.values(), key=lambda r: r.get("name", ""))

    def get(self, rack_id: str) -> Optional[dict]:
        return self._racks.get(rack_id)

    def create(
        self,
        name: str,
        description: str = "",
        system_instruction: str = "",
        operating_instruction: str = "",
        icon: str = "📦",
        rack_id: Optional[str] = None,
    ) -> dict:
        rid = rack_id or _slugify(name)
        base = rid
        counter = 1
        while rid in self._racks:
            rid = f"{base}-{counter}"
            counter += 1

        now = _now()
        rack = {
            "id": rid,
            "name": name.strip(),
            "description": description.strip(),
            "system_instruction": system_instruction.strip()
            or "Eres un asistente experto. Responde basándote únicamente en el contexto de los documentos proporcionados.",
            "operating_instruction": operating_instruction.strip(),
            "icon": icon or "📦",
            "notebooks": [],
            "created_at": now,
            "updated_at": now,
        }
        self._racks[rid] = rack
        self._save()
        logger.info("Created project '%s' (%s)", rack["name"], rid)
        return rack

    def update(self, rack_id: str, **fields) -> Optional[dict]:
        rack = self._racks.get(rack_id)
        if not rack:
            return None
        allowed = {
            "name",
            "description",
            "system_instruction",
            "operating_instruction",
            "icon",
        }
        for k, v in fields.items():
            if k in allowed and v is not None:
                rack[k] = v.strip() if isinstance(v, str) else v
        rack["updated_at"] = _now()
        self._save()
        return rack

    def delete(self, rack_id: str) -> bool:
        if rack_id not in self._racks:
            return False
        del self._racks[rack_id]
        self._save()
        logger.info("Deleted project %s", rack_id)
        return True

    def list_notebooks(self, rack_id: str) -> list[dict]:
        rack = self._racks.get(rack_id)
        if not rack:
            return []
        return list(rack.get("notebooks", []))

    def get_notebook(self, rack_id: str, notebook_id: str) -> Optional[dict]:
        for nb in self.list_notebooks(rack_id):
            if nb["id"] == notebook_id:
                return nb
        return None

    def create_notebook(
        self,
        rack_id: str,
        name: str,
        description: str = "",
        domain: str = "",
        notebook_id: Optional[str] = None,
    ) -> Optional[dict]:
        rack = self._racks.get(rack_id)
        if not rack:
            return None

        nid = notebook_id or _slugify(name)
        existing_ids = {nb["id"] for nb in rack.get("notebooks", [])}
        base = nid
        counter = 1
        while nid in existing_ids:
            nid = f"{base}-{counter}"
            counter += 1

        now = _now()
        nb = {
            "id": nid,
            "name": name.strip(),
            "description": description.strip(),
            "domain": domain.strip(),
            "created_at": now,
            "updated_at": now,
        }
        rack.setdefault("notebooks", []).append(nb)
        rack["updated_at"] = now
        self._save()
        logger.info("Created notebook '%s' in project %s", nb["name"], rack_id)
        return nb

    def update_notebook(
        self, rack_id: str, notebook_id: str, **fields
    ) -> Optional[dict]:
        rack = self._racks.get(rack_id)
        if not rack:
            return None
        for nb in rack.get("notebooks", []):
            if nb["id"] == notebook_id:
                allowed = {"name", "description", "domain"}
                for k, v in fields.items():
                    if k in allowed and v is not None:
                        nb[k] = v.strip() if isinstance(v, str) else v
                nb["updated_at"] = _now()
                rack["updated_at"] = _now()
                self._save()
                return nb
        return None

    def delete_notebook(self, rack_id: str, notebook_id: str) -> bool:
        rack = self._racks.get(rack_id)
        if not rack:
            return False
        notebooks = rack.get("notebooks", [])
        new_list = [nb for nb in notebooks if nb["id"] != notebook_id]
        if len(new_list) == len(notebooks):
            return False
        rack["notebooks"] = new_list
        rack["updated_at"] = _now()
        self._save()
        logger.info("Deleted notebook %s from project %s", notebook_id, rack_id)
        return True

    def notebook_catalog_text(self, rack_id: str) -> str:
        notebooks = self.list_notebooks(rack_id)
        if not notebooks:
            return "Este proyecto aún no tiene cuadernos."
        lines = []
        for nb in notebooks:
            domain = f" (dominio: {nb['domain']})" if nb.get("domain") else ""
            desc = f" – {nb['description']}" if nb.get("description") else ""
            lines.append(f"- Cuaderno '{nb['name']}'{domain}{desc}")
        return "\n".join(lines)
