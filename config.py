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
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'  # Railway 추가 변수 무시

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
            "model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small"
        }
    }
}
