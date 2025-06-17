"""
app/schemas/document.py

Defines Pydantic models for Document and DocumentUpdate, used for
request body validation and response serialization.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from uuid import UUID
from enum import Enum
from datetime import datetime

from isagog.components.analyzers.analyzer import Analysis as AnalysisResult

class DocumentUpdate(BaseModel):
    """
    Pydantic model for updating existing document metadata.
    All fields are optional.
    """
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[List[str]] = Field(None)

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Ensures tags are stripped of whitespace and lowercased."""
        if v is not None:
            return [tag.strip().lower() for tag in v if tag.strip()]
        return v

class DocumentStatus(str, Enum):
    draft = "draft" # document was created and uploaded
    submitted = "submitted" # analysis is in progress
    completed = "completed" # analysis is complete
    failed = "failed" # analysis failed
    approved = "approved" # analysis was reviewed and approved

class Document(BaseModel):
    """
    Pydantic model representing a complete document,
    including file metadata and timestamps.
    """
    id: UUID = Field(..., description="Unique document identifier", alias="_id")
    status: DocumentStatus = Field(DocumentStatus.draft, description="Current status of the document")
    file_name: str = Field(..., description="Original file_name uploaded by the user")
    file_path: str = Field(..., description="Path to the stored file on the server (relative to UPLOAD_DIR)")
    file_size: int = Field(..., description="Size of the uploaded file in bytes")
    mime_type: str = Field(..., description="MIME type of the file (e.g., application/pdf)")
    title: str = Field(..., description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    author: str = Field(..., description="Document author")
    tags: List[str] = Field(default_factory=list, description="List of associated tags")
    analysis : Optional[AnalysisResult] = Field(None, description="Analysis results for the document")
    creation_date: datetime = Field(..., description="Timestamp of document creation")
    updated_date: datetime = Field(..., description="Timestamp of last document update")

    class Config:
        """Pydantic configuration for JSON encoding."""
        # This will ensure UUID and datetime objects are properly serialized to JSON
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }
        # Allow population by field name (e.g., 'id') or alias ('_id' for MongoDB)
        # This is useful if your MongoDB _id field maps to 'id' in Pydantic.
        populate_by_name = True
        arbitrary_types_allowed = True # Allow types like Path if needed
