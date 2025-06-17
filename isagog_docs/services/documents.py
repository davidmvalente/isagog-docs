"""
app/services/document.py

Contains business logic for document management, including file operations,
and interactions with the MongoDB document collection.
"""

import aiofiles
import mimetypes
from pathlib import Path
from uuid import UUID, uuid4
import logging
from datetime import datetime
from typing import Dict, List, Optional
from bson import ObjectId # Required for MongoDB _id

from fastapi import HTTPException, UploadFile

from isagog_docs.core.config import settings
from isagog_docs.core.database import get_documents_collection # Import the MongoDB collection getter
from isagog_docs.schemas.document import Document, DocumentUpdate

logger = logging.getLogger(__name__)

# Helper Functions
async def get_document_by_id_from_db(document_id: UUID) -> dict:
    """
    Retrieves a document from the MongoDB collection by its ID.
    Raises HTTPException if the document is not found.
    """
    documents_collection = get_documents_collection() 
    doc = await documents_collection.find_one({"_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

def get_file_extension(file_name: str) -> str:
    """Extracts the file extension from a given file_name."""
    return Path(file_name).suffix.lower()

def generate_unique_file_name(original_file_name: str, doc_id: UUID) -> str:
    """Generates a unique file_namee for storing the uploaded file."""
    file_ext = get_file_extension(original_file_name)
    return f"{doc_id}{file_ext}"

async def save_file_to_disk(file: UploadFile, filepath: Path) -> int:
    """
    Asynchronously saves an uploaded file to the filesystem.
    Checks against MAX_FILE_SIZE.
    """
    file_size = 0
    
    async with aiofiles.open(filepath, 'wb') as f:
        while chunk := await file.read(8192):  # Read in 8KB chunks
            file_size += len(chunk)
            if file_size > settings.MAX_FILE_SIZE_BYTES:
                # Clean up partial file if it exceeds size limit
                filepath.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413, 
                    detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
                )
            await f.write(chunk)
    
    return file_size

def delete_file_from_disk(file_path: str) -> None:
    """Deletes a file from the filesystem."""
    full_path = Path(settings.UPLOAD_DIR) / file_path
    if full_path.exists():
        full_path.unlink()

# CRUD Operations for Documents
async def create_document_service(
    file: UploadFile,
    title: str,
    author: str,
    description: Optional[str],
    tags: Optional[str] # Comma-separated string
) -> Document:
    """
    Handles the creation of a new document, including file upload
    and MongoDB record creation.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Parse tags from comma-separated string
    tag_list = []
    if tags:
        tag_list = [tag.strip().lower() for tag in tags.split(",") if tag.strip()]
    
    # Generate document ID and file path
    doc_id = uuid4()
    stored_file_name = generate_unique_file_name(file.filename, doc_id)
    file_path = Path(settings.UPLOAD_DIR) / stored_file_name
    
    try:
        # Save file
        file_size = await save_file_to_disk(file, file_path)
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        # Prepare document record for MongoDB
        now = datetime.utcnow()
        doc_dict = {
            "_id": doc_id, 
            "status" : "draft",
            "file_name": file.filename,
            "file_path": stored_file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "title": title,
            "description": description,
            "author": author,
            "tags": tag_list,
            "creation_date": now,
            "updated_date": now
        }
        
        documents_collection = get_documents_collection()
        # Insert the document into MongoDB
        result = await documents_collection.insert_one(doc_dict)
        
        # Add the MongoDB _id to the dictionary for the Pydantic response model
        doc_dict["_id"] = str(result.inserted_id)
        
        return Document(**doc_dict)
        
    except Exception as e:
        # Clean up file if something went wrong
        if file_path.exists():
            file_path.unlink()
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Failed to create document: {str(e)}", stack_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create document: {str(e)}")

async def get_all_documents_service() -> List[Document]:
    """Retrieves all documents from the MongoDB collection, sorted by creation date."""
    documents_collection = get_documents_collection()
    # Find all documents, sort by creation_date descending, and convert to list
    # Use to_list(length=None) to retrieve all documents from the cursor
    cursor = documents_collection.find().sort("creation_date", -1)
    docs = await cursor.to_list(length=None)
    # This will throw a Pydantic ValidationError if any documents are invalid
    # TODO: Handle this error gracefully, ignore invalid documents and log them
    return [Document(**doc) for doc in docs]

async def get_document_service(document_id: UUID) -> Document:
    """Retrieves a single document by ID from MongoDB."""
    doc = await get_document_by_id_from_db(document_id)
    return Document(**doc)

async def update_document_service(document_id: UUID, 
                                  document_update: DocumentUpdate) -> Document:
    """
    Updates metadata for an existing document in MongoDB.
    Does not modify the associated file.
    """
    documents_collection = get_documents_collection()
    
    # Get existing document to ensure it exists
    existing_doc = await get_document_by_id_from_db(document_id)
    
    update_data = document_update.model_dump(exclude_unset=True) 
    
    if not update_data:
        # No updates provided, return existing document
        return Document(**existing_doc)

    # Add updated_date
    update_data["updated_date"] = datetime.utcnow()
    
    # Update the document in MongoDB
    result = await documents_collection.update_one(
        {"_id": document_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Could not update document")
    
    # Retrieve the updated document to return the complete object
    updated_doc = await get_document_by_id_from_db(document_id)
    return Document(**updated_doc)

async def delete_document_service(document_id: UUID) -> None:
    """
    Deletes a document record from MongoDB and its associated file from the filesystem.
    """
    documents_collection = get_documents_collection()
    
    # Get document to retrieve file_path before deleting
    doc = await get_document_by_id_from_db(document_id)
    
    # Delete document record from MongoDB
    result = await documents_collection.delete_one({"_id": document_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from filesystem
    delete_file_from_disk(doc["file_path"])
