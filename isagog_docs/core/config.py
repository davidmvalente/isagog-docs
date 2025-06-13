import os
import logging
from pathlib import Path
from typing import Optional
import toml

logger = logging.getLogger(__name__)

def secret_or_env(secret_name: str, file_paths: Optional[list] = None, _raise: bool = False) -> str | None:
    """Get secret from multiple files or environment variable."""
    logger.debug(f"Entering secret_or_env for secret: {secret_name}")

    if file_paths is None:
        file_paths = ["/run/secrets", "~/.secrets", "../secrets"]

    for file_path in file_paths:
        expanded_path = os.path.expanduser(file_path)
        full_path = os.path.join(expanded_path, secret_name)
        try:
            with open(full_path) as f:
                logger.debug(f"Found secret {secret_name} in {file_path}")
                return f.read().strip()
        except (FileNotFoundError, PermissionError) as e:
            logger.debug("File open error: %s, %s", (file_path + "/" + secret_name), e)

    result = os.environ.get(secret_name)
    logger.debug(f"Falling back to environment variable for {secret_name}: {'found' if result else 'not found'}")
    if _raise and result is None:
        raise RuntimeError(f"Secret {secret_name} not found")
    return result

class Config:
    """Application configuration loaded from secrets, environment, and static values."""

    def __init__(self):
        # Load project metadata from pyproject.toml
        metadata = toml.load("./pyproject.toml")["tool"]["poetry"]

        # Project metadata
        self.PROJECT_NAME = metadata["name"]
        self.PROJECT_DESCRIPTION = metadata["description"]
        self.PROJECT_VERSION = metadata["version"]
        self.API_V1_STR = "/api/v1"

        # Directories and limits
        self.UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/uploads"))
        self.MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

        # MongoDB
        self.MONGO_URI = secret_or_env("MONGODB_URI", _raise=True)
        self.MONGO_DB_NAME = "maxxi"
        self.MONGO_COLLECTION_NAME = "docs"

        # OpenRouter
        self.OPENROUTER_API_KEY = secret_or_env("OPENROUTER_API_KEY", _raise=True)
        self.OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")

    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_file_size_mb * 1024 * 1024

# Singleton config instance
settings = Config()
