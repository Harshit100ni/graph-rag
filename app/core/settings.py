from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Where to read env vars & .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Models
    chat_model: str = Field(default="gpt-4.1",
                            validation_alias=AliasChoices("OPENAI_MODEL", "CHAT_MODEL"))
    emb_model: str = Field(default="text-embedding-3-large",
                           validation_alias=AliasChoices("EMB_MODEL", "EMBEDDING_MODEL"))

    # OpenAI
    openai_key: str = Field(validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_KEY"))

    # Neo4j
    neo4j_uri: str = Field(validation_alias=AliasChoices("NEO4J_URI", "NEO4J_URL"))
    neo4j_user: str = Field(validation_alias="NEO4J_USER")
    neo4j_pass: str = Field(validation_alias=AliasChoices("NEO4J_PASSWORD", "NEO4J_PASS"))

    # Vector index
    vector_index: str = Field(default="emb_card_idx", validation_alias="VECTOR_INDEX")

settings = Settings()