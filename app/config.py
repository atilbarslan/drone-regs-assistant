"""Application settings, read from environment variables and an optional .env file."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": .env may hold values for later steps that this class does not declare.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SecretStr keeps the password in the connection string out of reprs and logs.
    database_url: SecretStr
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    # Seconds /health waits for the database (getting a connection plus SELECT 1).
    health_db_timeout: float = 2.0

    # Gemini. Only needed by code that calls the API; tests use a fake embedder.
    gemini_api_key: SecretStr | None = None
    gemini_generation_model: str = "gemini-3.5-flash-lite"
    # minimal | low | medium | high; unset keeps the model's default (minimal for
    # gemini-3.5-flash-lite, per ai.google.dev/gemini-api/docs/thinking).
    gemini_thinking_level: str | None = None
    gemini_embedding_model: str = "gemini-embedding-2"
    # Must match the vector(768) column in db/migrations/001_initial.sql.
    gemini_embedding_dimensions: int = 768
    gemini_timeout_seconds: float = 60.0

    # Local debugging only (DEBUG_RAW=1): write each answer's passages and the model's raw reply,
    # with the question, to this directory (outside git). See app/debug.py.
    debug_raw: bool = False
    debug_raw_dir: Path = Path("data/debug")

    # Hybrid search: candidates taken from each of vector and full-text search, the RRF
    # constant, and how many fused results are returned.
    search_candidates: int = 30
    search_rrf_k: int = 60
    search_top_k: int = 8
    # More passages for list questions ("hangi belgeler", "what do I need", "steps").
    search_top_k_list: int = 14
    # Compare mode searches each source separately; at least this many passages from each.
    search_compare_per_side: int = 6
    # Core sections of each jurisdiction (app/search.py) added to: no question ("off"), list
    # questions ("list") or every question ("all").
    search_core_sections: Literal["off", "list", "all"] = "off"

    # /api/ask limits. Each question makes one embedding and one generation request; the free
    # tier allows 500 generation requests a day for gemini-3.5-flash-lite (15 per minute), and
    # part of that is kept for evaluation and development.
    ask_global_per_minute: int = 12
    ask_global_per_day: int = 300
    ask_ip_per_minute: int = 3
    ask_ip_per_day: int = 20
    # Proxies in front of the app that append to X-Forwarded-For (app/ask.py: client_ip).
    # 0: no proxy, use the direct peer. Measured on the host before setting it.
    forwarded_trusted_hops: int = Field(default=0, ge=0)

    # Embedding the sources (python -m ingest.embed). The free tier limits for
    # gemini-embedding-2 were 100 requests and 30,000 tokens per minute and 1,000 requests per
    # day (Google AI Studio, 2026-10-06). Each text in a batch counts as one request, per minute
    # (measured with a 429) and per day (AI Studio showed 816 for the 816 texts sent that day).
    # Token pacing is the bottleneck, so stay under the per-minute limits with some margin.
    embed_tokens_per_minute: int = 25_000
    embed_requests_per_minute: int = 90
    embed_batch_max_items: int = 20
    embed_batch_max_tokens: int = 8_000  # estimated tokens per batch
    embed_max_retries: int = 6
    embed_backoff_base_seconds: float = 2.0
    embed_backoff_max_seconds: float = 120.0
