"""
PDF Voice AI – FastAPI application.
Projects (Racks) → Notebooks → Files, with persona + operating instructions.
"""
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    UploadResponse,
    HealthResponse,
    ErrorResponse,
    RackCreate,
    RackUpdate,
    RackResponse,
    NotebookCreate,
    NotebookUpdate,
    NotebookResponse,
    TemplateSummary,
    InstantiateTemplateRequest,
    GenerateProjectRequest,
    GenerateProjectResponse,
)
from app.ai.factory import AIProviderFactory
from app.documents.manager import DocumentManager
from app.racks.manager import RackManager
from app.templates.catalog import TemplateCatalog
from app.templates.generator import ProjectGenerator

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("pdf-voice-ai")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI system: Projects → Notebooks → Files + voice chat",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

doc_manager = DocumentManager()
rack_manager = RackManager()
project_generator = ProjectGenerator(rack_manager, doc_manager)


def _notebook_to_response(rack_id: str, nb: dict) -> NotebookResponse:
    return NotebookResponse(
        id=nb["id"],
        rack_id=rack_id,
        name=nb["name"],
        description=nb.get("description", ""),
        domain=nb.get("domain", ""),
        document_count=doc_manager.document_count(rack_id, nb["id"]),
        created_at=nb.get("created_at", ""),
        updated_at=nb.get("updated_at", ""),
    )


def _rack_to_response(rack: dict) -> RackResponse:
    rid = rack["id"]
    notebooks = [
        _notebook_to_response(rid, nb) for nb in rack.get("notebooks", [])
    ]
    return RackResponse(
        id=rid,
        name=rack["name"],
        description=rack.get("description", ""),
        system_instruction=rack.get("system_instruction", ""),
        operating_instruction=rack.get("operating_instruction", ""),
        icon=rack.get("icon", "📦"),
        created_at=rack.get("created_at", ""),
        updated_at=rack.get("updated_at", ""),
        document_count=doc_manager.document_count(rid),
        notebooks=notebooks,
    )


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health():
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        racks=len(rack_manager.list_racks()),
        documents_indexed=doc_manager.document_count(),
        providers=AIProviderFactory.available_providers(),
    )


@app.get("/api/racks", response_model=list[RackResponse], tags=["Projects"])
async def list_racks():
    return [_rack_to_response(r) for r in rack_manager.list_racks()]


@app.post("/api/racks", response_model=RackResponse, status_code=201, tags=["Projects"])
async def create_rack(body: RackCreate):
    rack = rack_manager.create(
        name=body.name,
        description=body.description,
        system_instruction=body.system_instruction,
        operating_instruction=body.operating_instruction,
        icon=body.icon,
    )
    return _rack_to_response(rack)


@app.get("/api/racks/{rack_id}", response_model=RackResponse, tags=["Projects"])
async def get_rack(rack_id: str):
    rack = rack_manager.get(rack_id)
    if not rack:
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    return _rack_to_response(rack)


@app.put("/api/racks/{rack_id}", response_model=RackResponse, tags=["Projects"])
async def update_rack(rack_id: str, body: RackUpdate):
    rack = rack_manager.update(
        rack_id,
        name=body.name,
        description=body.description,
        system_instruction=body.system_instruction,
        operating_instruction=body.operating_instruction,
        icon=body.icon,
    )
    if not rack:
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    return _rack_to_response(rack)


@app.delete("/api/racks/{rack_id}", tags=["Projects"])
async def delete_rack(rack_id: str):
    if not rack_manager.delete(rack_id):
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    doc_manager.delete_rack_collection(rack_id)
    return {"success": True, "message": f"Proyecto '{rack_id}' eliminado"}


@app.get("/api/racks/{rack_id}/notebooks", response_model=list[NotebookResponse], tags=["Notebooks"])
async def list_notebooks(rack_id: str):
    if not rack_manager.get(rack_id):
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    return [_notebook_to_response(rack_id, nb) for nb in rack_manager.list_notebooks(rack_id)]


@app.post("/api/racks/{rack_id}/notebooks", response_model=NotebookResponse, status_code=201, tags=["Notebooks"])
async def create_notebook(rack_id: str, body: NotebookCreate):
    nb = rack_manager.create_notebook(rack_id, name=body.name, description=body.description, domain=body.domain)
    if not nb:
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    return _notebook_to_response(rack_id, nb)


@app.put("/api/racks/{rack_id}/notebooks/{notebook_id}", response_model=NotebookResponse, tags=["Notebooks"])
async def update_notebook(rack_id: str, notebook_id: str, body: NotebookUpdate):
    nb = rack_manager.update_notebook(rack_id, notebook_id, name=body.name, description=body.description, domain=body.domain)
    if not nb:
        raise HTTPException(status_code=404, detail="Cuaderno o proyecto no encontrado")
    return _notebook_to_response(rack_id, nb)


@app.delete("/api/racks/{rack_id}/notebooks/{notebook_id}", tags=["Notebooks"])
async def delete_notebook(rack_id: str, notebook_id: str):
    if not rack_manager.delete_notebook(rack_id, notebook_id):
        raise HTTPException(status_code=404, detail="Cuaderno o proyecto no encontrado")
    deleted = doc_manager.clear_notebook(rack_id, notebook_id)
    return {"success": True, "message": f"Cuaderno eliminado ({deleted} fragmentos borrados)"}


@app.post("/api/racks/{rack_id}/notebooks/{notebook_id}/upload", response_model=UploadResponse, tags=["Documents"])
async def upload_file(rack_id: str, notebook_id: str, file: UploadFile = File(...)):
    rack = rack_manager.get(rack_id)
    if not rack:
        raise HTTPException(status_code=404, detail=f"Proyecto '{rack_id}' no encontrado")
    nb = rack_manager.get_notebook(rack_id, notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail=f"Cuaderno '{notebook_id}' no encontrado")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    ext = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".txt", ".md", ".csv", ".json", ".log"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Formato no soportado: {ext}")
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"Archivo demasiado grande ({size_mb:.1f} MB)")
    safe_name = f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest = settings.UPLOAD_DIR / safe_name
    try:
        with open(dest, "wb") as f:
            f.write(content)
        result = doc_manager.ingest_file(dest, original_filename=file.filename, rack_id=rack_id, notebook_id=notebook_id)
        return UploadResponse(
            success=True,
            filename=result["filename"],
            pages=result["pages"],
            chunks=result["chunks"],
            rack_id=rack_id,
            notebook_id=notebook_id,
            message=f"Indexado en '{rack['name']}' / '{nb['name']}': {result['chunks']} fragmentos",
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {exc}")
    finally:
        if dest.exists():
            dest.unlink(missing_ok=True)


@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    rack = rack_manager.get(request.rack_id)
    if not rack:
        raise HTTPException(status_code=404, detail=f"Proyecto '{request.rack_id}' no encontrado.")
    count = doc_manager.document_count(request.rack_id)
    if count == 0:
        raise HTTPException(status_code=400, detail=f"El proyecto '{rack['name']}' no tiene documentos.")
    notebook_ids = request.notebook_ids
    if notebook_ids:
        valid = {nb["id"] for nb in rack.get("notebooks", [])}
        invalid = [n for n in notebook_ids if n not in valid]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Cuadernos no encontrados: {invalid}")
    context, sources, nbs_used = doc_manager.get_context_string(
        request.query, rack_id=request.rack_id, notebook_ids=notebook_ids,
    )
    if not context:
        raise HTTPException(status_code=400, detail="No se encontró contexto relevante.")
    try:
        provider = AIProviderFactory.create(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    catalog = rack_manager.notebook_catalog_text(request.rack_id)
    system_prompt, user_prompt = provider.build_rag_prompt(
        context=context,
        query=request.query,
        language=request.language,
        system_instruction=rack.get("system_instruction"),
        operating_instruction=rack.get("operating_instruction"),
        notebook_catalog=catalog,
    )
    try:
        answer, tokens = await provider.generate(system_prompt, user_prompt)
    except Exception as exc:
        logger.exception("AI provider error (%s)", request.provider)
        raise HTTPException(status_code=502, detail=f"Error del proveedor de IA: {exc}")
    id_to_name = {nb["id"]: nb["name"] for nb in rack.get("notebooks", [])}
    notebooks_used_names = [id_to_name.get(n, n) for n in nbs_used]
    return ChatResponse(
        answer=answer,
        provider=provider.provider_name,
        model=provider.model,
        rack_id=rack["id"],
        rack_name=rack["name"],
        sources=sources,
        notebooks_used=notebooks_used_names,
        tokens_used=tokens,
    )


@app.get("/api/templates", response_model=list[TemplateSummary], tags=["Templates"])
async def list_templates():
    return TemplateCatalog.list_summaries()


@app.get("/api/templates/{template_id}", tags=["Templates"])
async def get_template(template_id: str):
    tpl = TemplateCatalog.get(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail=f"Plantilla '{template_id}' no encontrada")
    notebooks = []
    for nb in tpl.get("notebooks", []):
        notebooks.append({
            "id": nb.get("id"),
            "name": nb["name"],
            "description": nb.get("description", ""),
            "domain": nb.get("domain", ""),
            "seed_file_count": len(nb.get("seed_files", [])),
        })
    return {
        "id": tpl["id"],
        "name": tpl["name"],
        "description": tpl["description"],
        "icon": tpl.get("icon", "📦"),
        "category": tpl.get("category", "general"),
        "system_instruction": tpl.get("system_instruction", ""),
        "operating_instruction": tpl.get("operating_instruction", ""),
        "notebooks": notebooks,
    }


@app.post("/api/templates/{template_id}/instantiate", response_model=GenerateProjectResponse, status_code=201, tags=["Templates"])
async def instantiate_template(template_id: str, body: InstantiateTemplateRequest = InstantiateTemplateRequest()):
    try:
        rack = project_generator.instantiate_template(
            template_id, name_override=body.name_override, seed_documents=body.seed_documents,
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as exc:
        logger.exception("Template instantiate failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return GenerateProjectResponse(
        success=True,
        message=f"Proyecto '{rack['name']}' creado desde plantilla '{template_id}'",
        project=_rack_to_response(rack),
    )


@app.post("/api/projects/generate", response_model=GenerateProjectResponse, status_code=201, tags=["Templates"])
async def generate_project(body: GenerateProjectRequest):
    try:
        rack = await project_generator.generate_from_brief(
            body.brief,
            api_key=body.api_key,
            provider=body.provider,
            model=body.model,
            language=body.language,
            seed_documents=body.seed_documents,
            num_notebooks=body.num_notebooks,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("AI project generation failed")
        raise HTTPException(status_code=502, detail=f"Error generando proyecto con IA: {exc}")
    return GenerateProjectResponse(
        success=True,
        message=f"Proyecto '{rack['name']}' generado con IA",
        project=_rack_to_response(rack),
    )


app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = settings.STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index)


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(settings.STATIC_DIR / "index.html")
