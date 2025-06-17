"""
app/services/analysis.py

Contains business logic for document analysis operations and upload to MongoDB.
"""
import logging
from uuid import UUID
from typing import List
from datetime import datetime
from fastapi import HTTPException

from haystack import Pipeline, component
from haystack import Document as HaystackDocument
from haystack.components.preprocessors import DocumentCleaner

from isagog.components.analyzers.analyzer import Frame
from isagog.components.proxy.openrouter_proxy import OpenRouterProxy
from isagog.components.readers.file_reader import FileReader
from isagog.components.analyzers.concept_analyzer import ConceptAnalyzer
from isagog.components.analyzers.situation_analyzer import SituationAnalyzer

from isagog_docs.core.database import get_documents_collection, get_analysis_collection
from isagog_docs.core.config import settings
from isagog_docs.schemas.document import Document
from isagog_docs.schemas.analysis import AnalysisResponse, AnalysisResult, AnalysisCommit

logger = logging.getLogger(__name__)

@component
class DocumentToString:
    @component.output_types(text=str)
    def run(self, documents: List[HaystackDocument]):
        # Concatenate the text of the first documents
        combined_text = documents[0].content
        return {"text": combined_text}

DEFAULT_FRAME_EN = Frame(
        name="default",
        version="0.2",
        language="en",
        description="Default frame for entities and relations",
        concepts=["Person", "Organization", "Place", "Event", "Situation",  "Object", "Concept", "Quality", "Date", "Period", "Number",],
        relations=["(Object) is part of (Object)", 
                   "(Concept) is a kind of (Concept)", 
                   "(Person) is member of (Organization)", 
                   "(Event) takes place in (Place)", 
                   "(Object) is located in (Place)", 
                   "(Person, Organization) takes part in (Event, Situation)", 
                   "(Event) is result of (Event)", 
                   "(Object) belongs to (Organization)", 
                   "(Concept) refers to (Concept)", 
                   "(Person) has quality (Quality)", 
                   "(Object) has quality (Quality)", 
                   "(Concept) has quality (Quality)", 
                   "(Person, Organization, Place, Event, Situation,  Object) has quality (Quality)",                    
                  ]
    )

DAVIDSON_FRAME_EN = Frame(
    name="davidson_frame_en",
    concepts=["Person", "Organization", "Location"],
    situations=["Event", "Action", "State"],
    roles=["subject", "object", "agent", "patient", "location"],
    version="1.0",
    language="en",
    description="A frame for Davidson's analysis in English"
)

async def analysis_pipeline_factory() -> Pipeline:
    p = Pipeline()  
    
    llm = OpenRouterProxy(api_key = settings.OPENROUTER_API_KEY)
    p.add_component("file_reader", FileReader())
    p.add_component("document_cleaner", DocumentCleaner())
    p.add_component("doc_content", DocumentToString())
    p.add_component("relations", ConceptAnalyzer(llm_generator=llm, frame=DEFAULT_FRAME_EN))
    p.add_component("situations", SituationAnalyzer(llm_generator=llm, frame=DAVIDSON_FRAME_EN))
    # Connect 
    p.connect("file_reader", "document_cleaner")
    p.connect("document_cleaner", "doc_content")
    p.connect("doc_content", "relations")    
    p.connect("doc_content", "situations")  
    return p

async def start_analysis_service(document_id: UUID) -> AnalysisResponse:
    """
    Initiates an analysis process for a given document in MongoDB.
    This is a placeholder for a real analysis job.
    """
    analysis_collection = get_analysis_collection() # equal to the documents collection
    
    # Ensure document exists
    document = await analysis_collection.find_one({
        "_id": document_id,
    })

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if analysis is already pending for this document
    if document.get("status") == "pending":
        raise HTTPException(status_code=409, detail="Analysis already in progress for this document.")

    # Create a new analysis pipeline
    pipeline = await analysis_pipeline_factory()

    # Add the document to the pipeline
    results = pipeline.run({"file_reader": {"file_paths": [document["file_path"]]}})

    logger.info(f"Analysis results: {results}")

    # # Convert to dict for MongoDB insertion, handling UUID conversion
    # analysis_dict = result.model_dump(by_alias=True)
    # # Ensure document_id is stored as string for querying
    # analysis_dict["document_id"] = str(document._id) 

    # # Insert into MongoDB
    # result = await analysis_collection.insert_one(analysis_dict)
    
    # # Add the MongoDB _id to the response model
    # results.id = str(result.inserted_id)

    return {"OK": document._id}

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