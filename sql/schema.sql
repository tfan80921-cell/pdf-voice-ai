-- Run automatically by the app on startup (init_db).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    icon          TEXT NOT NULL DEFAULT '📦',
    system_instruction    TEXT NOT NULL DEFAULT '',
    operating_instruction TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notebooks (
    id          TEXT NOT NULL,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    domain      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, id)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id           BIGSERIAL PRIMARY KEY,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    notebook_id  TEXT NOT NULL,
    filename     TEXT NOT NULL,
    chunk_index  INT NOT NULL,
    content      TEXT NOT NULL,
    embedding    vector(384),
    doc_hash     TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, notebook_id)
        REFERENCES notebooks(project_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_project_notebook
    ON document_chunks (project_id, notebook_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_part
    ON document_chunks (project_id, notebook_id, filename, doc_hash, chunk_index);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE TABLE IF NOT EXISTS app_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
