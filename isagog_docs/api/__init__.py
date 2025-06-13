"""
app/api/__init__.py

Combines all API routers into a single APIRouter instance for main.py.
"""

from fastapi import APIRouter

from isagog_docs.api.endpoints import documents, analysis

api_router = APIRouter()
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(analysis.router, tags=["Analysis"])
