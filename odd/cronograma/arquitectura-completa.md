# PDF Voice AI — Cronograma, Arquitectura y Componentes (SIN CHROMADB)

## Reglas de Almacenamiento (Definidas en código)
- `DATABASE_URL` vacío → JSON local (`racks.json`) + **NO ChromaDB**.
- `DATABASE_URL` definido (Neon/pgvector) → Neon como única base de datos + embeddings `vector(384)` en `document_chunks`.
- ChromaDB fue removido del diseño operativo.

## 1. Chart del Sistema (Neon-Only / JSON Fallback)

```
┌───────────────────────────────┐
│  Usuario / Cliente             │ ← input: query + archivo PDF/texto
└──────────────┬────────────────┘
               │
               ▼
┌─────────────────────────────┐  HTTP / REST
│  FastAPI (main:app)         │ ← rate limit (SlowAPI), CORS
└────────────┬────────────────┘
             │
     ┌───────┼───────┐
     ▼       ▼       ▼
┌─────────┐ ┌──────┐ ┌───────────┐
│ Racks   │ │ Docs │ │ Templates │  ← managers (singleton)
│ Manager │ │ Mgr  │ │ Catalog   │
└────┬────┘ └──┬───┘ └─────┬─────┘
     │         │           │
     ▼         ▼           ▼
┌─────────┐ ┌──────────┐ ┌──────────┐
│ JSON/DB │ │  Neon    │ │ Catalog  │ ← datos / vectores
│ (local) │ │ (pgvector│ │ JSON     │
│ (si DB  │ │ si DB    │ │          │
│ vacío)  │ │ definida)│ │          │
└────┬────┘ └────┬─────┘ └─────┬────┘
     │           │            │
     └──────┬────┴────┬───────┘
            ▼         ▼
     ┌─────────────┐
     │ AI Factory  │  ← Gemini / DeepSeek / GLM
     │ (base.py)   │
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │ Prompt RAG  │  ← system + operating + contexto (Neon/JSON)
     │ Generation  │
     └──────┬──────┘
            ▼
     ┌─────────────┐
     │ Chat Response│ ← ChatResponse (Pydantic)
     └─────────────┘
```

## 2. Componentes, Módulos y Frameworks Explicados (SIN CHROMADB)

### 2.1 Framework: FastAPI (0.115.0) + Uvicorn (0.30.6)
- `run.py` → `uvicorn.run("app.main:app", ...)`
- `app/main.py` → `FastAPI(...)`, middleware `SlowAPIMiddleware`, `CORSMiddleware`
- Endpoints: `/api/health`, `/api/racks`, `/api/chat`, `/api/templates`, `/api/upload`

### 2.2 Modelo de Datos: Pydantic (2.9.2) + pydantic-settings (2.5.2)
- `app/schemas.py` → `RackCreate`, `RackResponse`, `NotebookResponse`, `ChatRequest`, `ChatResponse`, `UploadResponse`, `HealthResponse`, `GenerateProjectResponse`, `InstantTemplateRequest`
- Validación con `Field(min_length=..., max_length=...)`, `field_validator`

### 2.3 Base de Datos: SQLAlchemy (2.0.36) + asyncpg (0.30.0) + Neon (solo)
- `app/db.py` → `register_vector`, `create_async_engine`, `async_sessionmaker`
- `settings.DATABASE_URL` → define si se usa Neon (si vacío: solo JSON local)
- Tablas: `projects`, `notebooks`, `document_chunks`, `app_metadata`
- `pgvector.asyncpg.register_vector` registra tipo `vector(384)`
- Embeddings se almacenan directamente en `document_chunks.embedding` con `vector` type

### 2.4 Almacenamiento de Embeddings: SOLO pgvector en Neon
- `document_chunks.embedding` → tipo `vector(384)`
- Modelo `all-MiniLM-L6-v2` produce embeddings de 384 dimensiones
- Búsqueda con similitud coseno (`embedding <=> :embedding`)
- `CHROMA_PERSIST_DIR` y `CHROMA_COLLECTION_NAME` siguen en config pero NO se usan en código operativo

### 2.5 AI Providers: google-generativeai (0.8.2) + openai (1.51.0)
- `app/ai/base.py` → `BaseAIProvider` (abstract)
- `app/ai/factory.py` → `_REGISTRY` con `GEMINI`, `DEEPSEEK`, `GLM`
- `app/ai/gemini_provider.py` → `genai.configure`, `GenerativeModel`
- `app/ai/openai_compatible.py` → `DeepSeekProvider`, `GLMProvider` (OpenAI SDK)

### 2.6 Procesamiento de Documentos: PyPDF (5.0.1) + sentence-transformers (3.1.1)
- `DocumentManager` (`app/documents/manager.py`): extracción PDF/texto, chunking, embeddings
- Chunking: `re.sub`, split en `. ` o `\n\n`, overlap `CHUNK_OVERLAP`
- Embeddings: `SentenceTransformer.encode(..., show_progress_bar=False)`
- NO usa ChromaDB para persistencia de embeddings

### 2.7 Almacenamiento Híbrido (Sin ChromaDB): Neon / JSON
- Si `DATABASE_URL` definido: `DocumentManager` usa `ingest_file_async` con `db.execute(...)` insertando en `document_chunks`
- Si `DATABASE_URL` vacío: `DocumentManager` usa `ingest_file` que persiste localmente (JSON) — NO hay base vectorial local, el contexto se recupera de `document_chunks` si hay DB, o se simula con datos locales
- Nota: Si no hay Neon y no hay datos indexados, `get_context_string` devuelve vacío → el chat no funciona sin documentos

### 2.8 Gestión de Proyectos (Racks): Singleton Manager
- `app/racks/manager.py` → `RackManager`
- `self._store_path` = `BASE_DIR / "racks.json"` (local si no hay Neon)
- `_load()` / `_save()` manejan JSON
- `initialize_async()` migra datos locales (`racks.json`, `document_chunks`) a Neon UNA VEZ (marcadores: `local_projects_migrated`, `local_chunks_migrated`)
- `list_racks_async()`, `get_async()` usan `_fetch_neon_racks()` con SQL

### 2.9 Sistema de Plantillas: Catalog + Generator
- `app/templates/catalog.py` → `TEMPLATES` dict con 4 proyectos pre-construidos
- `vet-avicola-200`: persona veterinario, 3 cuadernos (Vacunación, Nutrición, Manejo)
- `consejero-juridico`: persona jurídico, 2 cuadernos (Contratos, Laboral)
- `nutricionista-deportivo`: persona nutricionista, 3 cuadernos (Requerimientos, Menús, Suplementación)
- `mantenimiento-industrial`: persona técnico, 3 cuadernos (Seguridad/LOTO, Mecánicos, Eléctricos)
- `generate_from_brief()`: usa AI para generar JSON con `name`, `system_instruction`, `operating_instruction`, `notebooks` (cada uno con `seed_content` de al menos 300 palabras)

### 2.10 Chat y RAG (Retrieval Augmented Generation)
- `POST /api/chat`
- Recupera contexto de `document_chunks` o datos locales
- `build_rag_prompt()` en `BaseAIProvider`: combina `system_instruction`, `operating_instruction`, `notebook_catalog_text`, y contexto recuperado
- Generación con `provider.generate()` (async con `asyncio.to_thread` para Gemini)
- Respuesta formateada como `ChatResponse`

### 2.11 Configuración: Settings (BaseSettings)
- `app/config.py` → `Settings`
- `DATABASE_URL`: define Neon (vacío = modo local con JSON)
- `MAX_UPLOAD_SIZE_MB`: 50 MB
- `MAX_PDF_PAGES`: 500
- `CHUNK_SIZE`: 1000, `CHUNK_OVERLAP`: 200, `TOP_K_RESULTS`: 5
- `ALLOWED_EXTENSIONS`: `.pdf`, `.txt`, `.md`, `.csv`, `.json`, `.log`

### 2.12 Rate Limiting: SlowAPI
- `SlowAPIMiddleware` con `limiter.limit("10/minute")` aplicado a `/api/chat`

### 2.13 Middleware: CORS
- `allow_origins` configurado en `ALLOWED_ORIGINS` (por defecto incluye `localhost:3000`, `127.0.0.1:3000`, `https://your-domain.com`)

### 2.14 Frontend: SPA Fallback
- `serve_frontend()` → `FileResponse(settings.STATIC_DIR / "index.html")`
- `spa_fallback()` → cualquier ruta no-API devuelve `index.html`
- `static/` debe contener los archivos del frontend (no incluidos en el repositorio)

### 2.15 Sistema de Memoria: Engram (Opcional)
- `mem_search`, `mem_save`, `mem_context`, etc.
- Documentación guardada previamente con `mem_save` (id 1): arquitectura completa

## 3. Cronograma del Proyecto (Actualizado — Sin ChromaDB)

```
Fase A: Configuración (30 min)
├── A1: Verificar .venv existe (.venv2 creado previamente)
├── A2: Confirmar .env (DATABASE_URL = vacío o Neon)
└── A3: Revisar app/config.py (DEBUG=False para producción)

Fase B: Inicialización del Sistema (30 min)
├── B1: Revisar racks.json (ejemplos pre-cargados: vet-avicola, consejero-juridico)
├── B2: Confirmar que DocumentManager no usa ChromaDB
│   └── Código: `_use_neon = is_neon_enabled()`
│   └── Si DATABASE_URL vacío: solo JSON local (sin embeddings locales)
└── B3: Confirmar pgvector en Neon (si DB definida)
    └── `register_vector` en app/db.py

Fase C: Pruebas Básicas (1 hora)
├── C1: python run.py (FastAPI inicia)
├── C2: curl /api/health → status ok, providers disponibles
├── C3: curl /api/racks → 2 proyectos (JSON local o Neon)
└── C4: curl /api/templates → 4 templates

Fase D: Flujo Completo (1-2 horas)
├── D1: POST /api/templates/vet-avicola-200/instantiate
│   └── Crea rack con 3 notebooks + seed files
├── D2: POST /api/racks/{id}/notebooks/{nb}/upload (archivo PDF)
│   └── Si DATABASE_URL vacío: archivo guardado en uploads/, texto extraído
│   └── Si DATABASE_URL definido: archivo extraído, chunks indexados en Neon
├── D3: POST /api/chat
│   └── Requiere api_key + provider
│   └── Recupera contexto de document_chunks (Neon) o datos locales
│   └── Genera respuesta con AI

Fase E: Verificación de Componentes (1 hora)
├── E1: DocumentManager
│   ├── ingest_file_async() → inserta en Neon (document_chunks)
│   ├── query_async() → busca con `<=>` en Neon (pgvector)
│   └── get_context_string_async() → formatea contexto para RAG
├── E2: RackManager
│   ├── initialize_async() → migra JSON a Neon (una vez)
│   ├── list_racks_async() → SELECT proyectos + LEFT JOIN notebooks
│   └── create_notebook_async() → INSERT en Neon
├── E3: AIProviderFactory
│   ├── create() → valida provider, crea instancia
│   ├── available_providers() → ["gemini", "deepseek", "glm"]
│   └── build_rag_prompt() → combina instrucciones + contexto + query

Fase F: Documentación y Entrega (Realizada)
├── F1: Archivo: odd/cronograma/arquitectura-completa.md (actualizado sin ChromaDB)
├── F2: Explicación de todos los componentes, módulos y frameworks
└── F3: Chart visual del sistema actualizado
```

## 4. Resumen de Archivos Clave (Sin ChromaDB)

| Archivo / Directorio | Rol | Framework / Librería | Datos / Estado |
|---|---|---|---|
| `run.py` | Entry point | uvicorn, FastAPI | `python run.py` inicia servidor |
| `app/main.py` | API principal | FastAPI, SlowAPI, pydantic | Endpoints REST |
| `app/config.py` | Configuración | pydantic-settings | `DATABASE_URL` define modo |
| `app/schemas.py` | Modelos | Pydantic | Validación y respuesta |
| `app/ai/` | AI providers | google-generativeai, openai | Gemini, DeepSeek, GLM |
| `app/documents/manager.py` | Documentos | sentence-transformers, PyPDF | Indexación RAG (Neon/JSON) |
| `app/racks/manager.py` | Proyectos | SQLAlchemy, JSON | Racks + notebooks |
| `app/templates/catalog.py` | Plantillas | JSON + generación AI | 4 templates pre-construidos |
| `tests/test_app.py` | Tests | pytest, TestClient | Cobertura básica |
| `.env` / `.env.example` | Entorno | python-dotenv | `DATABASE_URL` para Neon |
| `sql/` | Esquemas DB | SQL (PostgreSQL) | `projects`, `notebooks`, `document_chunks` |
| `chroma_db/` | Directorio persistente | (NO USADO) | Existe en disco pero NO referenciado en código |

## 5. Dependencias Críticas y Versiones (Actualizadas)

```
Python: 3.12
FastAPI: 0.115.0 (servidor web REST)
Pydantic: 2.9.2 (esquemas y validación)
Pydantic-Settings: 2.5.2 (configuración desde .env)
Uvicorn: 0.30.6 (servidor ASGI)
SQLAlchemy: 2.0.36 (ORM async)
AsyncPG: 0.30.0 (PostgreSQL async)
Pgvector: 0.3.6 (extensión PostgreSQL para embeddings)
Google-GenerativeAI: 0.8.2 (Gemini SDK)
OpenAI SDK: 1.51.0 (DeepSeek, GLM compatible)
Sentence-Transformers: 3.1.1 (embeddings locales)
Torch: 2.14.1 (motor de transformers)
PyPDF: 5.0.1 (extracción de texto PDF)
Httpx: 0.27.2 (cliente HTTP async)
Aiofiles: 24.1.0 (archivos async)
Python-Dotenv: 1.0.1 (carga .env)
```

## 6. Notas de Diseño (Sin ChromaDB — Confirmado)

- **NO ChromaDB**: El código `DocumentManager` nunca crea `PersistentClient` ni `Collection`. La constante `CHROMA_COLLECTION_NAME` y `CHROMA_PERSIST_DIR` existen en `config.py` pero NO se usan en `documents/manager.py` para persistencia.
- **Embeddings en Neon**: `document_chunks.embedding` usa tipo `vector` (384 dimensiones, `all-MiniLM-L6-v2`). La búsqueda usa `embedding <=> :embedding` (distancia coseno) con `ORDER BY ... LIMIT :limit`.
- **Modo Local (sin Neon)**: Si `DATABASE_URL` vacío, los proyectos se guardan en JSON (`racks.json`). Los documentos subidos se guardan temporalmente en `uploads/` y se extraen para contexto, pero NO se indexan en una base vectorial (no hay almacenamiento de embeddings local). El chat funcionará con datos locales solo si hay datos en memoria, pero sin embeddings persistentes no hay recuperación RAG efectiva sin Neon.
- **Migración automática**: `RackManager.initialize_async()` y `DocumentManager.initialize_async()` verifican `is_neon_enabled()` y migran datos locales (`racks.json`) a Neon una sola vez usando marcadores `local_*_migrated`.
- **Singleton**: `DocumentManager.__new__` y `RackManager.__new__` garantizan instancia única para evitar duplicación de recursos.
- **Async/Sync dual**: `DocumentManager` ofrece métodos async (`ingest_file_async`, `query_async`) y sync (`ingest_file`, `query`) con `asyncio.to_thread()` para operaciones bloqueantes (embeddings).
- **Plantillas con contenido operativo**: Cada template (`vet-avicola-200`, etc.) incluye texto operativo con números, calendarios y protocolos — no son estructuras vacías.

## 7. Próximos Pasos Confirmados (Según Usuario)

- Confirmado: ChromaDB NO se usa.
- Almacenamiento: Solo Neon (si `DATABASE_URL` definido) o JSON local (si vacío).
- Embeddings: Solo en `document_chunks` (Neon, `vector(384)`).
- El archivo `chroma_db/` puede eliminarse o ignorarse — no afecta la ejecución.
