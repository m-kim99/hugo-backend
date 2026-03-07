from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    supabase_host: str
    supabase_port: int = 5432
    supabase_db: str = "postgres"
    supabase_user: str = "postgres"
    supabase_password: str
    
    # OpenAI
    openai_api_key: str
    
    # Server
    port: int = 8000
    cors_origins: str
    
    # App
    default_user_id: str
    api_title: str
    system_prompt_template: str
    available_models: str
    
    # Mem0 LLM
    mem0_llm_model: str = "gpt-4o-mini"
    mem0_llm_temperature: float = 0.7
    mem0_llm_max_tokens: int = 2000
    
    # Mem0 Embedder
    mem0_embedder_model: str = "text-embedding-3-small"
    
    class Config:
        env_file = ".env"

settings = Settings()

MEM0_CONFIG = {
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "dbname": settings.supabase_db,
            "host": settings.supabase_host,
            "port": str(settings.supabase_port),
            "user": settings.supabase_user,
            "password": settings.supabase_password
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": settings.mem0_llm_model,
            "temperature": settings.mem0_llm_temperature,
            "max_tokens": settings.mem0_llm_max_tokens
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": settings.mem0_embedder_model
        }
    }
}
