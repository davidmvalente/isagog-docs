"""
app/services/analysis.py

Contains business logic for document analysis operations, interacting with MongoDB.
These functions are placeholders for actual analysis implementation.
"""

from uuid import UUID
from datetime import datetime
from fastapi import HTTPException

from isagog.components.readers import file_reader

from isagog_docs.core.database import get_documents_collection, get_analysis_collection
from isagog_docs.schemas.document import Document
from isagog_docs.schemas.analysis import AnalysisResponse, AnalysisResult, AnalysisCommit

async def _get_document_from_db(document_id: UUID) -> dict:
    """Helper to retrieve a document from the MongoDB documents collection."""
    documents_collection = get_documents_collection()
    doc = await documents_collection.find_one({"id": str(document_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

async def start_analysis_service(document_id: UUID) -> AnalysisResponse:
    """
    Initiates an analysis process for a given document in MongoDB.
    This is a placeholder for a real analysis job.
    """
    await _get_document_from_db(document_id) # Ensure document exists

    analysis_collection = get_analysis_collection()
    
    # Check if analysis is already pending for this document
    existing_analysis = await analysis_collection.find_one({
        "document_id": str(document_id),
        "status": "pending"
    })
    
    if existing_analysis:
        raise HTTPException(status_code=409, detail="Analysis already in progress for this document.")

    # Create a new analysis record
    analysis_data = AnalysisResponse(
        document_id=document_id,
        status="pending",
        last_updated=datetime.utcnow(),
        result=None
    )
    
    # Convert to dict for MongoDB insertion, handling UUID conversion
    analysis_dict = analysis_data.model_dump(by_alias=True)
    # Ensure document_id is stored as string for querying
    analysis_dict["document_id"] = str(analysis_data.document_id) 

    # Insert into MongoDB
    result = await analysis_collection.insert_one(analysis_dict)
    
    # Add the MongoDB _id to the response model
    analysis_data.id = str(result.inserted_id)

    return analysis_data

async def get_analysis_service(document_id: UUID) -> AnalysisResponse:
    """
    Retrieves the analysis status and results for a document from MongoDB.
    """
    await _get_document_from_db(document_id) # Ensure document exists

    analysis_collection = get_analysis_collection()
    analysis_data_doc = await analysis_collection.find_one({"document_id": str(document_id)})
    
    if not analysis_data_doc:
        raise HTTPException(status_code=404, detail="Analysis not found for this document.")
    
    return AnalysisResponse(**analysis_data_doc)

async def commit_analysis_service(document_id: UUID, commit_data: AnalysisCommit) -> AnalysisResponse:
    """
    Commits (approves/rejects) the analysis results for a document in MongoDB.
    This also updates the analysis status to 'completed' or 'reviewed'.
    """
    await _get_document_from_db(document_id) # Ensure document exists
    
    analysis_collection = get_analysis_collection()
    
    existing_analysis_doc = await analysis_collection.find_one({"document_id": str(document_id)})
    if not existing_analysis_doc:
        raise HTTPException(status_code=404, detail="Analysis not found for this document.")

    analysis_data = AnalysisResponse(**existing_analysis_doc)

    update_fields = {}
    if analysis_data.status == "pending":
        update_fields["status"] = "completed" if commit_data.is_approved else "reviewed"
        update_fields["last_updated"] = datetime.utcnow()
        if not analysis_data.result:
             # Simulate completing the analysis with some dummy data if pending
             update_fields["result"] = AnalysisResult(
                 extracted_text=f"Sample extracted text for document {document_id}",
                 keywords=["sample", "document", "analysis"],
                 summary="This is a sample summary generated after analysis.",
                 analysis_date=datetime.utcnow()
             ).model_dump() # Convert Pydantic model to dict for MongoDB

    else:
        # If analysis was already completed, just update review notes or similar
        update_fields["status"] = "reviewed"
        update_fields["last_updated"] = datetime.utcnow()
    
    # Update the analysis record in MongoDB
    result = await analysis_collection.update_one(
        {"document_id": str(document_id)},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Analysis record not found for update.")
    
    # Retrieve the updated analysis record to return
    updated_analysis_doc = await analysis_collection.find_one({"document_id": str(document_id)})
    return AnalysisResponse(**updated_analysis_doc)