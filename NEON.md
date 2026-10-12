# Configuración de Neon

## Crear el proyecto en Ohio

Neon no permite cambiar directamente la región de un proyecto existente. Para usar otra región, crea un proyecto nuevo; el proyecto original y sus datos permanecen intactos hasta que los migres y verifiques.

Este proyecto usa `aws-us-east-2` (Ohio). Instala el CLI actual y autentícate:

```bash
npm install -g neon@latest
neon auth
```

Crea el proyecto y copia su ID:

```bash
neon projects create --name pdf-voice-ai --region-id aws-us-east-2 --no-secrets
neon projects list
```

`--no-secrets` evita imprimir credenciales en la terminal. Enlaza el repositorio al ID del proyecto nuevo y trae la URL de conexión a `.env`:

```bash
cp .env.example .env
neon link --project-id <PROJECT_ID> --branch main --yes --no-config
neon env pull --project-id <PROJECT_ID> --branch main --env DATABASE_URL --file .env
```

`.env` contiene credenciales y está excluido de Git. No compartas ni publiques ese archivo.

## Migrar desde otra región

Crear un proyecto en Ohio no copia el esquema ni los datos del proyecto anterior. Mantén el proyecto original hasta confirmar la migración. Si contiene datos, migra la base de datos con herramientas PostgreSQL (`pg_dump`/`pg_restore`) usando las URLs de origen y destino, y verifica las tablas antes de retirar el proyecto antiguo.

Con `DATABASE_URL` configurado, la app conecta a Neon al arrancar y crea la extensión `vector` y las tablas (`projects`, `notebooks`, `document_chunks`). Los proyectos, cuadernos y fragmentos nuevos se guardan en Neon; la búsqueda de documentos usa similitud coseno en pgvector.

En el primer arranque, si hay datos locales, la app migra `racks.json` y los fragmentos de ChromaDB a Neon una sola vez. Conserva los archivos locales como respaldo. Si el proyecto Neon está vacío y no existe `racks.json`, se crean los dos proyectos de ejemplo habituales. Los marcadores de migración evitan repetir esta carga en arranques posteriores.

Al quitar `DATABASE_URL`, la app vuelve a JSON/ChromaDB, pero los cambios hechos mientras Neon estaba activo no se sincronizan de regreso a esos archivos.

La dimensión de los embeddings es **384** (`all-MiniLM-L6-v2`); si cambia el modelo, actualiza `vector(384)` en `app/db.py`.

## Arrancar y comprobar

```bash
pip install -r requirements.txt
python run.py
curl http://localhost:8000/api/health
```

Si no configuras `DATABASE_URL`, la app sigue funcionando localmente con JSON y ChromaDB.

## QA automatizado

Instala las dependencias de desarrollo y ejecuta las pruebas unitarias:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Las pruebas unitarias no modifican Neon. Las pruebas HTTP y de persistencia se omiten salvo que habilites explícitamente la variable indicada abajo.

Para ejecutar además el flujo completo contra Neon —crear proyecto/cuadernos temporales, subir dos veces un PDF de prueba, comprobar idempotencia y aislamiento de pgvector, y verificar la limpieza— habilítalo explícitamente:

```bash
PDF_VOICE_AI_RUN_NEON_E2E=1 pytest -q -m neon_e2e
```

Esta prueba usa `DATABASE_URL` y elimina sus propios registros temporales al terminar. Ejecútala únicamente contra una base de pruebas o un proyecto Neon donde tengas autorización para crear y borrar esos registros.
