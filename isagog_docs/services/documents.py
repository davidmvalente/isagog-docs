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
from typing import List, Optional

from pymongo.collection import Collection
from fastapi import HTTPException, UploadFile

from isagog_docs.schemas.document import Document, DocumentUpdate

logger = logging.getLogger(__name__)


class DocumentService:
    """Service class for handling document operations including file management and database interactions."""
    
    def __init__(self, collection: Collection, 
                 upload_dir: Path, 
                 max_file_size_mb: int,
                 max_file_size_bytes: int):
        
        self.collection = collection
        self.UPLOAD_DIR = upload_dir
        self.MAX_FILE_SIZE_MB = max_file_size_mb
        self.MAX_FILE_SIZE_BYTES = max_file_size_bytes
        
    # Helper Methods
    async def _get_document_by_id(self, document_id: UUID) -> dict:
        """
        Retrieves a document from the MongoDB collection by its ID.
        
        Args:
            document_id: UUID of the document to retrieve
            
        Returns:
            dict: Document data from MongoDB
            
        Raises:
            HTTPException: If document is not found (404)
        """
        doc = await self.collection.find_one({"_id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    def _get_file_extension(self, file_name: str) -> str:
        """
        Extracts the file extension from a given file name.
        
        Args:
            file_name: Name of the file
            
        Returns:
            str: File extension in lowercase (e.g., '.pdf', '.txt')
        """
        return Path(file_name).suffix.lower()

    def _generate_unique_filename(self, original_file_name: str, doc_id: UUID) -> str:
        """
        Generates a unique filename for storing the uploaded file.
        
        Args:
            original_file_name: Original name of the uploaded file
            doc_id: UUID of the document
            
        Returns:
            str: Unique filename combining doc_id and file extension
        """
        file_ext = self._get_file_extension(original_file_name)
        return f"{doc_id}{file_ext}"

    async def _save_file_to_disk(self, file: UploadFile, filepath: Path) -> int:
        """
        Asynchronously saves an uploaded file to the filesystem with size validation.
        
        Args:
            file: FastAPI UploadFile object
            filepath: Path where the file should be saved
            
        Returns:
            int: Total size of the saved file in bytes
            
        Raises:
            HTTPException: If file exceeds maximum size limit (413)
        """
        file_size = 0
        filepath.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        
        try:
            async with aiofiles.open(filepath, 'wb') as f:
                # Reset file pointer to beginning
                await file.seek(0)
                
                while chunk := await file.read(8192):  # Read in 8KB chunks
                    file_size += len(chunk)
                    if file_size > self.MAX_FILE_SIZE_BYTES:
                        # Clean up partial file if it exceeds size limit
                        filepath.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=413, 
                            detail=f"File too large. Maximum size: {self.MAX_FILE_SIZE_MB}MB"
                        )
                    await f.write(chunk)
        except Exception as e:
            # Clean up partial file on any error
            filepath.unlink(missing_ok=True)
            raise
        
        return file_size

    def _delete_file_from_disk(self, file_path: str) -> None:
        """
        Deletes a file from the filesystem.
        
        Args:
            file_path: Relative path to the file within the upload directory
        """
        full_path = Path(self.UPLOAD_DIR) / file_path
        if full_path.exists():
            try:
                full_path.unlink()
                logger.info(f"Successfully deleted file: {full_path}")
            except OSError as e:
                logger.error(f"Failed to delete file {full_path}: {e}")

    def _parse_tags(self, tags: Optional[str]) -> List[str]:
        """
        Parse comma-separated tags string into a list of cleaned tags.
        
        Args:
            tags: Comma-separated string of tags
            
        Returns:
            List[str]: List of cleaned, lowercase tags
        """
        if not tags:
            return []
        return [tag.strip().lower() for tag in tags.split(",") if tag.strip()]

    def _get_mime_type(self, filename: str) -> str:
        """
        Determine MIME type for a file.
        
        Args:
            filename: Name of the file
            
        Returns:
            str: MIME type or default 'application/octet-stream'
        """
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"

    # CRUD Operations for Documents
    async def create_document(
        self,
        file: UploadFile,
        title: str,
        author: str,
        description: Optional[str] = None,
        tags: Optional[str] = None  # Comma-separated string
    ) -> Document:
        """
        Creates a new document, including file upload and database record creation.
        
        Args:
            file: Uploaded file
            title: Document title
            author: Document author
            description: Optional document description
            tags: Optional comma-separated tags string
            
        Returns:
            Document: Created document object
            
        Raises:
            HTTPException: For various error conditions (400, 413, 500)
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Parse tags and generate identifiers
        tag_list = self._parse_tags(tags)
        doc_id = uuid4()
        stored_file_name = self._generate_unique_filename(file.filename, doc_id)
        file_path = Path(self.UPLOAD_DIR) / stored_file_name
        
        try:
            # Save file to disk
            file_size = await self._save_file_to_disk(file, file_path)
            
            # Prepare document record
            now = datetime.utcnow()
            doc_dict = {
                "_id": doc_id, 
                "status": "draft",
                "file_name": file.filename,
                "file_path": stored_file_name,
                "file_size": file_size,
                "mime_type": self._get_mime_type(file.filename),
                "title": title,
                "description": description,
                "author": author,
                "tags": tag_list,
                "creation_date": now,
                "updated_date": now
            }
            
            # Insert document into MongoDB
            await self.collection.insert_one(doc_dict)
            
            # Convert UUID to string for Pydantic model
            doc_dict["_id"] = str(doc_id)
            
            logger.info(f"Successfully created document: {doc_id}")
            return Document(**doc_dict)
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            # Clean up file and log error
            if file_path.exists():
                file_path.unlink()
            logger.error(f"Failed to create document: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to create document")

    async def get_all_documents(self) -> List[Document]:
        """
        Retrieves all documents from the MongoDB collection, sorted by creation date.
        
        Returns:
            List[Document]: List of all documents, newest first
        """
        try:
            cursor = self.collection.find().sort("creation_date", -1)
            docs = await cursor.to_list(length=None)
            
            # Filter out invalid documents and log them
            valid_documents = []
            for doc in docs:
                try:
                    doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
                    valid_documents.append(Document(**doc))
                except Exception as e:
                    logger.warning(f"Invalid document found with ID {doc.get('_id')}: {e}")
            
            return valid_documents
            
        except Exception as e:
            logger.error(f"Failed to retrieve documents: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")

    async def get_document(self, document_id: UUID) -> Document:
        """
        Retrieves a single document by ID.
        
        Args:
            document_id: UUID of the document to retrieve
            
        Returns:
            Document: The requested document
            
        Raises:
            HTTPException: If document is not found (404)
        """
        doc = await self._get_document_by_id(document_id)
        doc["_id"] = str(doc["_id"])
        return Document(**doc)

    async def update_document(
        self, 
        document_id: UUID, 
        document_update: DocumentUpdate
    ) -> Document:
        """
        Updates metadata for an existing document.
        
        Args:
            document_id: UUID of the document to update
            document_update: Update data
            
        Returns:
            Document: Updated document object
            
        Raises:
            HTTPException: If document is not found (404)
        """
        # Verify document exists
        existing_doc = await self._get_document_by_id(document_id)
        
        # Get update data, excluding unset fields
        update_data = document_update.model_dump(exclude_unset=True) 
        
        if not update_data:
            # No updates provided, return existing document
            existing_doc["_id"] = str(existing_doc["_id"])
            return Document(**existing_doc)

        # Add updated timestamp
        update_data["updated_date"] = datetime.utcnow()
        
        # Perform update
        result = await self.collection.update_one(
            {"_id": document_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Return updated document
        updated_doc = await self._get_document_by_id(document_id)
        updated_doc["_id"] = str(updated_doc["_id"])
        
        logger.info(f"Successfully updated document: {document_id}")
        return Document(**updated_doc)

    async def delete_document(self, document_id: UUID) -> None:
        """
        Deletes a document record and its associated file.
        
        Args:
            document_id: UUID of the document to delete
            
        Raises:
            HTTPException: If document is not found (404)
        """
        # Get document to retrieve file path
        doc = await self._get_document_by_id(document_id)
        
        # Delete from database
        result = await self.collection.delete_one({"_id": document_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete associated file
        self._delete_file_from_disk(doc["file_path"])
        
        logger.info(f"Successfully deleted document: {document_id}")

    async def get_documents_by_author(self, author: str) -> List[Document]:
        """
        Retrieves all documents by a specific author.
        
        Args:
            author: Author name to filter by
            
        Returns:
            List[Document]: List of documents by the author
        """
        try:
            cursor = self.collection.find({"author": author}).sort("creation_date", -1)
            docs = await cursor.to_list(length=None)
            
            valid_documents = []
            for doc in docs:
                try:
                    doc["_id"] = str(doc["_id"])
                    valid_documents.append(Document(**doc))
                except Exception as e:
                    logger.warning(f"Invalid document found with ID {doc.get('_id')}: {e}")
            
            return valid_documents
            
        except Exception as e:
            logger.error(f"Failed to retrieve documents by author {author}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")

    async def get_documents_by_tags(self, tags: List[str]) -> List[Document]:
        """
        Retrieves documents that contain any of the specified tags.
        
        Args:
            tags: List of tags to search for
            
        Returns:
            List[Document]: List of documents containing the tags
        """
        try:
            # Convert tags to lowercase for case-insensitive search
            normalized_tags = [tag.lower() for tag in tags]
            
            cursor = self.collection.find(
                {"tags": {"$in": normalized_tags}}
            ).sort("creation_date", -1)
            
            docs = await cursor.to_list(length=None)
            
            valid_documents = []
            for doc in docs:
                try:
                    doc["_id"] = str(doc["_id"])
                    valid_documents.append(Document(**doc))
                except Exception as e:
                    logger.warning(f"Invalid document found with ID {doc.get('_id')}: {e}")
            
            return valid_documents
            
        except Exception as e:
            logger.error(f"Failed to retrieve documents by tags: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to retrieve documents")