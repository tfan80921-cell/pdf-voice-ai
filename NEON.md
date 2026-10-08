# Neon setup (CLI)

## Qué necesitas

1. **Cuenta en [Neon](https://console.neon.tech)** (free tier vale).
2. **API Key** de Neon (Console → Account settings → API Keys → Create).
3. En tu máquina: **Node.js** para el CLI `neonctl`.

Este entorno de Grok **no puede autenticarse** en tu cuenta Neon. Tú creas el proyecto con el CLI; la app solo necesita `DATABASE_URL`.

---

## 1. Instalar CLI (en tu PC)

```bash
npm install -g neonctl
# o
npx neonctl@latest --help
```

## 2. Login

```bash
neonctl auth
# se abre el navegador y guarda el token
```

O con API key (CI / headless):

```bash
export NEON_API_KEY="napi_xxxxxxxx"
```

## 3. Crear proyecto

```bash
neonctl projects create --name pdf-voice-ai --region-id aws-eu-central-1

# Listar y copiar el id
neonctl projects list
```

## 4. Connection string

```bash
neonctl connection-string --project-id <PROJECT_ID> --role-name neondb_owner --database-name neondb
```

Copia la URL `postgresql://...@ep-....neon.tech/neondb?sslmode=require`.

## 5. Configurar la app

En la raíz del repo:

```bash
cp .env.example .env
```

Edita `.env`:

```env
DATABASE_URL=postgresql://USER:PASSWORD@ep-XXXX.region.aws.neon.tech/neondb?sslmode=require
```

## 6. Arrancar

```bash
pip install -r requirements.txt
python run.py
```

Al arrancar, la app:

- detecta `DATABASE_URL`
- ejecuta `CREATE EXTENSION vector` y crea tablas (`projects`, `notebooks`, `document_chunks`)
- usa **Neon + pgvector** en lugar de `racks.json` + Chroma

Comprueba:

```bash
curl http://localhost:8000/api/health
```

---

## Sin Neon (local)

Si **no** pones `DATABASE_URL`, sigue funcionando con JSON + Chroma en disco (como antes).

---

## pgvector

La dimensión del embedding es **384** (`all-MiniLM-L6-v2`).  
Si cambias de modelo, altera el `vector(384)` en `app/db.py`.
