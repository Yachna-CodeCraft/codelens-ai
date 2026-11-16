from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "codelens"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    repos_dir: str = "temp_repos"
    max_file_bytes: int = 200_000
    max_files: int = 2000
    chunk_lines: int = 60
    chunk_overlap: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
