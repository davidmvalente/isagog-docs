"""
app/api/endpoints/documents.py

Defines FastAPI endpoints for document management (CRUD operations).
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
from uuid import UUID

from isagog_docs.schemas.document import Document, DocumentUpdate
from isagog_docs.services.documents import DocumentService
from isagog_docs.core.config import Config
from pathlib import Path

router = APIRouter(prefix="/documents")

# Singleton service instance
def get_document_service(request: Request) -> DocumentService:
    """Get singleton instance of DocumentService."""  
    return request.app.state.document_service

def get_app_config(request: Request) -> Config:
    """Get singleton instance of Config."""  
    return request.app.state.config

@router.post("/", response_model=Document, status_code=201, tags=["Documents"])
async def create_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    service = Depends(get_document_service)
):
    """
    **Create a new document with file upload.**

    Allows uploading a file along with its metadata (title, author, description, tags).
    The file is saved to the configured upload directory, and a document record
    is created in the database.
    """
    return await service.create_document(
        file=file,
        title=title,
        author=author,
        description=description,
        tags=tags
    )

@router.get("/", response_model=List[Document], tags=["Documents"])
async def list_documents(service = Depends(get_document_service)):
    """
    **List all documents.**

    Retrieves a list of all documents currently stored in the database,
    sorted by creation date (newest first).
    """
    return await service.get_all_documents()

@router.get("/{document_id}", response_model=Document, tags=["Documents"])
async def get_document(document_id: UUID, service = Depends(get_document_service)):
    """
    **Get a specific document by ID.**

    Retrieves the full metadata for a single document using its unique ID.
    """
    return await service.get_document(document_id)

@router.get("/{document_id}/download", tags=["Documents"])
async def download_document(document_id: UUID, 
                            service = Depends(get_document_service),
                            settings = Depends(get_app_config)):
    """
    **Download the file associated with a document.**

    Allows users to download the original uploaded file using the document's ID.
    Returns a FileResponse with the correct file_name and MIME type.
    """
    doc: Document = await service.get_document(document_id)
    file_path = Path(settings.UPLOAD_DIR) / doc.file_path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=str(file_path),
        filename=doc.file_name,
        media_type=doc.mime_type
    )

@router.put("/{document_id}", response_model=Document, tags=["Documents"])
async def update_document(document_id: UUID, document_update: DocumentUpdate, service = Depends(get_document_service)):
    """
    **Update document metadata (not the file).**

    Allows updating existing metadata for a document, such as its title,
    description, author, or tags. The associated file is not modified.
    """
    return await service.update_document(document_id, document_update)

@router.delete("/{document_id}", status_code=204, tags=["Documents"])
async def delete_document(document_id: UUID, service = Depends(get_document_service)):
    """
    **Delete a document and its associated file.**

    Removes a document record from the database and permanently deletes
    its corresponding file from the filesystem.
    """
    await service.delete_document(document_id)
    return None
