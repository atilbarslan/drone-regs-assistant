-- One row per /api/ask request, for usage and latency figures. On purpose there is no question
-- text and no IP address here.

CREATE TABLE request_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    lang text NOT NULL CHECK (lang IN ('tr', 'en')),
    jurisdiction text CHECK (jurisdiction IN ('EU', 'TR', 'both', 'none')),
    retrieved_chunks integer,
    cited_chunks integer,
    embedding_model text,
    generation_model text,
    embedding_tokens integer,
    prompt_tokens integer,
    output_tokens integer,
    thinking_tokens integer,
    retrieval_ms integer,  -- query embedding plus database search
    generation_ms integer,
    total_ms integer NOT NULL,
    refused boolean,
    -- NULL when the request succeeded; otherwise what stopped it, e.g. "rate_limited:ip_minute",
    -- "provider_quota:daily", "provider_error", "uncited_answer", "internal".
    error_type text
);

CREATE INDEX request_log_created_at ON request_log (created_at);
