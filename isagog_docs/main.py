"""
main.py

This is the main entry point for the FastAPI Document Management API.
It initializes the FastAPI application, adds CORS middleware, and includes
the API routers for documents and analysis.

"""
import os
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient
import uvicorn

from isagog_docs.core.config import Config
from isagog_docs.core.logging import LOGGING_CONFIG
from isagog_docs.services.documents import DocumentService
from isagog_docs.services.analysis import AnalysisService
from isagog_docs.api import api_router # Import the combined API router

logger = logging.getLogger(__name__)    

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-load settings
    app.state.config = Config()

    # Make sure upload directory exists
    Path(app.state.config.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Initialise to MongoDB
    try:
        app.state.client = AsyncMongoClient(app.state.config.MONGO_URI, uuidRepresentation='standard')
        app.state.db = app.state.client[app.state.config.MONGO_DB]
        await app.state.db.command('ping')
        logger.debug("Connected to MongoDB successfully!")

    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        # Re-raise the exception to prevent the application from starting
        raise

    app.state.collection = app.state.config.MONGO_COLLECTION

    # Initialise services
    app.state.document_service = DocumentService(
        collection = app.state.collection,
        upload_dir = app.state.config.UPLOAD_DIR,
        max_file_size_mb = app.state.config.MAX_FILE_SIZE_MB,
        max_file_size_bytes = app.state.config.MAX_FILE_SIZE_BYTES
    )

    app.state.analysis_service = AnalysisService(
        collection = app.state.collection,
        config = app.state.config
    )

    # Run the application
    yield

    # Clean up the connection
    if app.state.client:
        await app.state.client.close()
        logger.info("Closed MongoDB connection successfully.")


settings = Config()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the main API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Health"])
async def root():
    """Endpoint to return the API version."""
    return {
        "message": settings.PROJECT_DESCRIPTION,
        "version": settings.PROJECT_VERSION,
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify service status and dependencies."""
    upload_dir_ok = Path(settings.UPLOAD_DIR).exists() and os.access(Path(settings.UPLOAD_DIR), os.W_OK)
    
    # In a real application, you'd check MongoDB connection here
    # from app.core.database import get_database
    try:
        mongo_ok = app.state.db is not None
    except Exception:
        mongo_ok = False
    
    return {
        "status": "healthy" if (upload_dir_ok and mongo_ok) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "mongo_db_ok": mongo_ok,
        "upload_directory_ok": upload_dir_ok
    }

if __name__ == "__main__":

    uvicorn.run(app, 
                host = settings.APP_HOST, 
                port = settings.APP_PORT, 
                log_config = LOGGING_CONFIG
            )
