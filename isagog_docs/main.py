"""
main.py

This is the main entry point for the FastAPI Document Management API.
It initializes the FastAPI application, adds CORS middleware, and includes
the API routers for documents and analysis.

"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from pathlib import Path
from datetime import datetime

from isagog_docs.core.config import settings
from isagog_docs.core.database import connect_to_mongo, get_database
from isagog_docs.api import api_router # Import the combined API router

# Ensure the UPLOAD_DIR exists
Path(settings.UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
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

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify service status and dependencies."""
    upload_dir_ok = Path(settings.UPLOADS_DIR).exists() and os.access(Path(settings.UPLOADS_DIR), os.W_OK)
    
    # In a real application, you'd check MongoDB connection here
    # from app.core.database import get_database
    try:
        await connect_to_mongo()
    except Exception:
        mongo_ok = False
    
    return {
        "status": "healthy" if upload_dir_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "mongo_db_ok": mongo_ok,
        "upload_directory_ok": upload_dir_ok
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
