"""
Pydantic models for request / response validation.
Hierarchy: Project (Rack) → Notebooks → Files
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AIProvider(str, Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GLM = "glm"


# ---------------------------------------------------------------------------
# Notebooks (cuadernos dentro de un proyecto)
# ---------------------------------------------------------------------------

class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    domain: str = Field(
        default="",
        max_length=200,
        description="Ámbito de conocimiento, ej: 'vacunación aviar', 'contratos laborales'",
    )


class NotebookUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    domain: Optional[str] = Field(None, max_length=200)


class NotebookResponse(BaseModel):
    id: str
    rack_id: str
    name: str
    description: str
    domain: str
    document_count: int = 0
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Racks / Projects
# ---------------------------------------------------------------------------

class RackCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    system_instruction: str = Field(
        default="",
        max_length=8000,
        description="Quién es el asistente (persona)",
    )
    operating_instruction: str = Field(
        default="",
        max_length=8000,
        description="Cómo debe usar los cuadernos (orquestación)",
    )
    icon: str = Field(default="📦", max_length=8)


class RackUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    system_instruction: Optional[str] = Field(None, max_length=8000)
    operating_instruction: Optional[str] = Field(None, max_length=8000)
    icon: Optional[str] = Field(None, max_length=8)


class RackResponse(BaseModel):
    id: str
    name: str
    description: str
    system_instruction: str
    operating_instruction: str
    icon: str
    created_at: str
    updated_at: str
    document_count: int = 0
    notebooks: list[NotebookResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat & Upload
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    rack_id: str = Field(..., min_length=1)
    notebook_ids: Optional[list[str]] = Field(
        None,
        description="Opcional: limitar la búsqueda a estos cuadernos. Si se omite, busca en todos.",
    )
    provider: AIProvider = Field(default=AIProvider.GEMINI)
    api_key: str = Field(..., min_length=10)
    model: Optional[str] = Field(None)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64, le=8192)
    language: Optional[str] = Field(None)

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class ChatResponse(BaseModel):
    answer: str
    provider: str
    model: str
    rack_id: str
    rack_name: str
    sources: list[str] = Field(default_factory=list)
    notebooks_used: list[str] = Field(default_factory=list)
    tokens_used: Optional[int] = None


class UploadResponse(BaseModel):
    success: bool
    filename: str
    pages: int
    chunks: int
    rack_id: str
    notebook_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    racks: int
    documents_indexed: int
    providers: list[str]


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


# ---------------------------------------------------------------------------
# Templates & auto-generation
# ---------------------------------------------------------------------------

class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    category: str
    notebook_count: int


class InstantiateTemplateRequest(BaseModel):
    name_override: Optional[str] = Field(
        None, description="Nombre personalizado del proyecto (opcional)"
    )
    seed_documents: bool = Field(
        True, description="Indexar documentos semilla de la plantilla"
    )


class GenerateProjectRequest(BaseModel):
    brief: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Descripción en lenguaje natural del proyecto a generar",
    )
    provider: AIProvider = Field(default=AIProvider.GEMINI)
    api_key: str = Field(..., min_length=10)
    model: Optional[str] = None
    language: str = Field(default="es", description="Idioma del contenido generado")
    num_notebooks: int = Field(default=3, ge=1, le=8)
    seed_documents: bool = Field(
        True, description="Indexar contenido semilla generado por la IA"
    )


class GenerateProjectResponse(BaseModel):
    success: bool
    message: str
    project: RackResponse
