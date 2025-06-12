import os

class Config:
    def __init__(self):
        self.uploads_dir = os.getenv("UPLOADS_DIR", "/app/uploads")
        self.mongo_uri = read_secret_or_env("MONGO_URI")
        self.openrouter_api_key = read_secret_or_env("OPENROUTER_API_KEY", )
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "gpt-4")
        self.db_name = "maxxi"
        self.collection_name = "docs"
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable required")
        
def read_secret_or_env(name: str) -> str:
    """Read a secret from the secrets file or environment variable"""
    try:
        return os.environ[name]
    except KeyError:
        with open(f"/run/secrets/{name}", "r") as f:
            secret = f.read().strip()
            if not secret:
                raise ValueError(f"Secret {name} not found")