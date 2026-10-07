# PDF Voice AI – Proyectos, Cuadernos y Voz

Sistema de IA agnóstico (Gemini / DeepSeek / GLM) para chat de voz sobre documentos, organizado como:

```
Proyecto (Rack)
├── Instrucción de persona        → quién es el asistente
├── Instrucción de funcionamiento → cómo debe usar los cuadernos
└── Cuadernos (2, 3, 4, 5…)
    ├── Cuaderno A  → archivos PDF / texto de un dominio
    ├── Cuaderno B  → …
    └── …
```

Equivalente a **Gems de Gemini** con notebooks múltiples y reglas de orquestación.

## Arranque

```bash
cd pdf-voice-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Abre http://localhost:8000

## Generación automática de proyectos

### Plantillas listas

```bash
curl http://localhost:8000/api/templates
curl -X POST http://localhost:8000/api/templates/vet-avicola-200/instantiate -H "Content-Type: application/json" -d '{"seed_documents": true}'
```

Plantillas incluidas:
- `vet-avicola-200` — lote experimental ~200 aves
- `consejero-juridico` — contratos y normativa laboral
- `nutricionista-deportivo` — requerimientos, menús y suplementación
- `mantenimiento-industrial` — LOTO, mecánico y eléctrico

## Licencia

MIT
