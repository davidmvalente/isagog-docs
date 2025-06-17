"""
app/api/endpoints/analysis.py

Defines FastAPI endpoints for document analysis operations.
These endpoints interact with the analysis service.
"""

from fastapi import APIRouter, HTTPException
from uuid import UUID

from isagog_docs.schemas.analysis import AnalysisResponse, AnalysisCommit
from isagog_docs.services import analysis as analysis_service

router = APIRouter(prefix="/documents/{document_id}/analysis")

@router.post("/", status_code=201, response_model=AnalysisResponse, tags=["Analysis"])
async def start_analysis(document_id: UUID):
    """
    **Start analysis for a document.**

    Initiates an asynchronous analysis process for the specified document.
    Returns the initial status of the analysis.
    """
    return await analysis_service.start_analysis_service(document_id)

@router.get("/", response_model=AnalysisResponse, tags=["Analysis"])
async def get_analysis(document_id: UUID):
    """
    **Get analysis for a document for user review.**

    Retrieves the current status and results of the analysis for a document.
    """
    return await analysis_service.get_analysis_service(document_id)

@router.put("/", response_model=AnalysisResponse, tags=["Analysis"])
async def commit_analysis(document_id: UUID, commit_data: AnalysisCommit):
    """
    **Commit analysis for a document.**

    Allows a user to commit (e.g., approve or reject) the results of a document analysis.
    """
    return await analysis_service.commit_analysis_service(document_id, commit_data)
