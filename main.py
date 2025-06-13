from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from datetime import datetime
from uuid import UUID, uuid4
import uvicorn
import os
from pathlib import Path
import mimetypes
import aiofiles

app = FastAPI(
    title="Document Management API",
    description="A CRUD API for document management with file upload",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# In-memory storage (replace with database in production)
documents_db: Dict[str, dict] = {}

# File configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Pydantic Models
class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[List[str]] = Field(None)

    @field_validator('tags')
    def validate_tags(cls, v):
        if v is not None:
            return [tag.strip().lower() for tag in v if tag.strip()]
        return v

class Document(BaseModel):
    id: UUID = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    filetype: str = Field(..., description="File extension")
    title: str = Field(..., description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    author: str = Field(..., description="Document author")
    tags: List[str] = Field(default_factory=list, description="List of tags")
    creation_date: datetime = Field(..., description="Document creation timestamp")
    updated_date: datetime = Field(..., description="Document last update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

# Helper Functions
def get_document_by_id(document_id: UUID) -> dict:
    """Get document by ID from storage"""
    doc = documents_db.get(str(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

def get_file_extension(filename: str) -> str:
    """Get file extension from filename"""
    return Path(filename).suffix.lower()

def generate_unique_filename(original_filename: str, doc_id: UUID) -> str:
    """Generate unique filename for storage"""
    file_ext = get_file_extension(original_filename)
    return f"{doc_id}{file_ext}"

async def save_file(file: UploadFile, filepath: Path) -> int:
    """Save uploaded file to filesystem and return file size"""
    file_size = 0
    
    async with aiofiles.open(filepath, 'wb') as f:
        while chunk := await file.read(8192):  # Read in 8KB chunks
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                # Clean up partial file
                filepath.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, 
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
                )
            await f.write(chunk)
    
    return file_size

def delete_file(file_path: str) -> None:
    """Delete file from filesystem"""
    full_path = UPLOAD_DIR / file_path
    if full_path.exists():
        full_path.unlink()

# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Document Management API",
        "version": "1.0.0",
        "endpoints": {
            "create": "POST /documents/",
            "list": "GET /documents/",
            "get": "GET /documents/{id}",
            "update": "PUT /documents/{id}",
            "delete": "DELETE /documents/{id}"
        }
    }

@app.post("/documents/{document_id}/analysis", status_code=201, tags=["Analysis"])
async def start_analysis(document_id: UUID):
    """Start analysis for a document"""
    doc = get_document_by_id(document_id)

    raise NotImplementedError

@app.get("/documents/{document_id}/analysis", tags=["Analysis"])
async def review_analysis(document_id: UUID, response_model=Document):
    """Get analysis for a document for user review"""
    doc = get_document_by_id(document_id)
    
    
    raise NotImplementedError

@app.put("/documents/{document_id}/analysis", tags=["Analysis"])
async def commit_analysis(document_id: UUID, analysis: Document):
    """Get analysis for a document for user review"""
    doc = get_document_by_id(document_id)
    
    # TODO: Get analysis result
    raise NotImplementedError


# Document API Endpoints

@app.post("/documents/", response_model=Document, status_code=201, tags=["Documents"])
async def create_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)  # Comma-separated tags
):
    """Create a new document with file upload"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Parse tags
    tag_list = []
    if tags:
        tag_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
    
    # Generate document ID and file path
    doc_id = uuid4()
    stored_filename = generate_unique_filename(file.filename, doc_id)
    file_path = UPLOAD_DIR / stored_filename
    
    try:
        # Save file
        file_size = await save_file(file, file_path)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Create document record
        now = datetime.utcnow()
        doc_dict = {
            "id": doc_id,
            "filename": file.filename,
            "filetype": get_file_extension(file.filename),
            "file_path": stored_filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "title": title,
            "description": description,
            "author": author,
            "tags": tag_list,
            "creation_date": now,
            "updated_date": now
        }
        
        documents_db[str(doc_id)] = doc_dict
        
        return Document(**doc_dict)
        
    except Exception as e:
        # Clean up file if something went wrong
        if file_path.exists():
            file_path.unlink()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

@app.get("/documents/", response_model=List[Document], tags=["Documents"])
async def list_documents():
    """List all documents"""
    docs = list(documents_db.values())
    # Sort by creation date (newest first)
    docs.sort(key=lambda x: x["creation_date"], reverse=True)
    return [Document(**doc) for doc in docs]

@app.get("/documents/{document_id}", response_model=Document, tags=["Documents"])
async def get_document(document_id: UUID):
    """Get a specific document by ID"""
    doc = get_document_by_id(document_id)
    return Document(**doc)

@app.get("/documents/{document_id}/download", tags=["Documents"])
async def download_document(document_id: UUID):
    """Download the file associated with a document"""
    doc = get_document_by_id(document_id)
    file_path = UPLOAD_DIR / doc["file_path"]
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=str(file_path),
        filename=doc["filename"],
        media_type=doc["mime_type"]
    )

@app.put("/documents/{document_id}", response_model=Document, tags=["Documents"])
async def update_document(document_id: UUID, document_update: DocumentUpdate):
    """Update document metadata (not the file)"""
    doc = get_document_by_id(document_id)
    
    # Update only provided fields
    update_data = document_update.dict(exclude_unset=True)
    
    if update_data:
        for field, value in update_data.items():
            if field == "tags" and value is not None:
                doc[field] = [tag.strip().lower() for tag in value if tag.strip()]
            else:
                doc[field] = value
        
        doc["updated_date"] = datetime.utcnow()
        documents_db[str(document_id)] = doc
    
    return Document(**doc)

@app.delete("/documents/{document_id}", status_code=204, tags=["Documents"])
async def delete_document(document_id: UUID):
    """Delete a document and its associated file"""
    doc = get_document_by_id(document_id)
    
    # Delete file from filesystem
    delete_file(doc["file_path"])
    
    # Delete document record
    del documents_db[str(document_id)]
    
    return None

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    upload_dir_ok = UPLOAD_DIR.exists() and os.access(UPLOAD_DIR, os.W_OK)
    
    return {
        "status": "healthy" if upload_dir_ok else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "documents_count": len(documents_db),
        "upload_directory_ok": upload_dir_ok
    }

if __name__ == "__main__":
    uvicorn.run(isagog_docs.main:app, host="0.0.0.0", port=8000, reload=True)