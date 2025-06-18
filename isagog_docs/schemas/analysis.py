"""
app/schemas/analysis.py

Defines Pydantic models for Analysis-related data, used for
request body validation and response serialization for analysis endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from isagog.components.analyzers.analyzer import Analysis as AnalysisResult

class AnalysisResponse(BaseModel):
    """
    Response model for retrieving document analysis.
    """
    document_id: UUID = Field(..., description="ID of the document that was analyzed")
    status: str = Field(..., description="Current status of the analysis (e.g., 'pending', 'completed', 'failed')")
    result: Optional[AnalysisResult] = Field(None, description="The detailed analysis result, if completed")
    last_updated: datetime = Field(..., description="Timestamp of the last update to the analysis record")

class AnalysisCommit(BaseModel):
    """
    Request model for committing analysis results.
    This could be used when a user reviews and approves analysis.
    """
    is_approved: bool = Field(..., description="Whether the analysis results are approved by the user")
    notes: Optional[str] = Field(None, description="Optional notes from the user regarding the analysis")
    # You might also include fields from AnalysisResult if the user can modify them before committing
    # e.g., modified_extracted_text: Optional[str] = None

class AnalysisError(Exception):
    """Custom exception for analysis-related errors."""
    pass