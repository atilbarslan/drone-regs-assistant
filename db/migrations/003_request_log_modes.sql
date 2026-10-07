-- Structured answers: record which mode was answered, why, and how the answer was shaped.

ALTER TABLE request_log
    ADD COLUMN mode text CHECK (mode IN ('EU', 'TR', 'compare')),
    -- explicit (the user chose it), detected (from the question), default (neither)
    ADD COLUMN mode_source text CHECK (mode_source IN ('explicit', 'detected', 'default')),
    ADD COLUMN top_k integer,
    ADD COLUMN facts_count integer,
    ADD COLUMN sections_count integer,
    ADD COLUMN depends_on_count integer;
