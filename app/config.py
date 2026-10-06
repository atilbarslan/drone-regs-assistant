"""Application settings, read from environment variables and an optional .env file."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": .env also holds values for later steps (Gemini key and model names) that
    # this class does not declare yet.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SecretStr keeps the password in the connection string out of reprs and logs.
    database_url: SecretStr
    db_pool_min_size: int = 1
    db_pool_max_size: int = 5
    # Seconds /health waits for the database (getting a connection plus SELECT 1).
    health_db_timeout: float = 2.0
