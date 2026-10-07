-- Documents (one per source in sources.yaml) and their chunks, with a vector embedding for
-- semantic search and a tsvector for full-text search.

CREATE EXTENSION IF NOT EXISTS vector;

-- Full-text search configuration per chunk language. Immutable, so it can be used in the
-- generated tsvector column below.
CREATE FUNCTION ts_config_for(language text) RETURNS regconfig
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    RETURN CASE language
        WHEN 'tr' THEN 'pg_catalog.turkish'::regconfig
        ELSE 'pg_catalog.english'::regconfig
    END;

CREATE TABLE documents (
    id text PRIMARY KEY,  -- source id from sources.yaml
    title text NOT NULL,
    jurisdiction text NOT NULL CHECK (jurisdiction IN ('EU', 'TR')),
    language text NOT NULL CHECK (language IN ('en', 'tr')),
    version text NOT NULL,
    published text NOT NULL,
    citation_url text NOT NULL,
    sha256 text NOT NULL,  -- of the file the text was parsed from
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id text NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    ordinal integer NOT NULL,  -- position of the chunk in its document
    section_ref text NOT NULL,
    heading text NOT NULL,
    page integer,
    chunk_index integer NOT NULL,  -- position within its section
    language text NOT NULL CHECK (language IN ('en', 'tr')),
    text text NOT NULL,
    -- sha256 of section_ref, heading, page, chunk_index, language and text. A chunk whose hash
    -- is already stored keeps its embedding when the sources are loaded again.
    content_hash text NOT NULL,
    -- 768 dimensions: pgvector's HNSW index supports up to 2000 for the vector type.
    embedding vector(768),
    embedding_model text,
    embedded_at timestamptz,
    -- The reference weighs most (A), then the heading (B), then the text (D), so a query for
    -- "UAS.OPEN.020" or "Madde 12" ranks that section above passages that only mention it.
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector(ts_config_for(language), section_ref), 'A')
        || setweight(to_tsvector(ts_config_for(language), heading), 'B')
        || setweight(to_tsvector(ts_config_for(language), text), 'D')
    ) STORED,
    UNIQUE (document_id, content_hash),
    CHECK ((embedding IS NULL) = (embedding_model IS NULL))
);

CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX chunks_document_ordinal ON chunks (document_id, ordinal);
