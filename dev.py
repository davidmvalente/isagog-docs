#! /bin/python
import uvicorn
import os

from isagog_docs.core.config import settings
from isagog_docs.core.logging import LOGGING_CONFIG

# 


# Override settings for development
settings.MONGO_DB = "dev"
settings.MONGO_COLLECTION = "dev-collection" 
settings.OPENROUTER_MODEL = "google/gemini-2.0-flash-001"
settings.UPLOAD_DIR = "./uploads"

if __name__ == "__main__":

    uvicorn.run("isagog_docs.main:app", 
                host = "0.0.0.0", 
                port = 8000,
                reload = True,
                log_config = LOGGING_CONFIG
            )