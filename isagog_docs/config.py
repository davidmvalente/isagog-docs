import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.upload_dir = os.getenv("UPLOAD_DIR", "/app/uploads")
        self.mongo_uri = secret_or_env("MONGODB_URI",_raise =True)
        self.openrouter_api_key = secret_or_env("OPENROUTER_API_KEY", _raise = True)
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
        self.db_name = "maxxi"
        self.collection_name = "docs"
        

def secret_or_env(secret_name: str, file_paths: Optional[list] = None, _raise: bool = False) -> str | None:
    """Get Secret from multiple files or environment variable"""
    logger.debug(f"Entering secret_or_env for secret: {secret_name}")

    if file_paths is None:
        file_paths = ["/run/secrets", "~/.secrets", "../secrets"]

    result: str | None = None
    for file_path in file_paths:
        expanded_path = os.path.expanduser(file_path)
        full_path = os.path.join(expanded_path, secret_name)
        try:
            with open(full_path) as f:
                logger.debug(f"Found secret {secret_name} in {file_path}")
                result = f.read().strip()
                logger.debug(f"Exiting secret_or_env for secret: {secret_name}")
                return result
        except (FileNotFoundError, PermissionError) as e:
            logger.debug("File open error: %s, %s", (file_path + "/" + secret_name), e)
            continue

    result = os.environ.get(secret_name)
    logger.debug(f"Falling back to environment variable for {secret_name}: {'found' if result else 'not found'}")
    if _raise and result is None:
        raise RuntimeError(f"Secret {secret_name} not found")
    return result
