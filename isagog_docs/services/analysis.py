"""
app/services/analysis.py

Contains business logic for document analysis operations and upload to MongoDB.
"""
import logging
from uuid import UUID
from typing import List
from datetime import datetime
from fastapi import HTTPException
from pathlib import Path

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
    
    llm_factory = lambda: OpenRouterProxy(api_key = settings.OPENROUTER_API_KEY, model = settings.OPENROUTER_MODEL)

    p.add_component("file_reader", FileReader())
    p.add_component("document_cleaner", DocumentCleaner())
    p.add_component("doc_content", DocumentToString())  
    p.add_component("relations", ConceptAnalyzer(llm_generator=llm_factory(), frame=DEFAULT_FRAME_EN))
    p.add_component("situations", SituationAnalyzer(llm_generator=llm_factory(), frame=DAVIDSON_FRAME_EN))
    # Connect 
    p.connect("file_reader", "document_cleaner")
    p.connect("document_cleaner", "doc_content")
    p.connect("doc_content", "relations")    
    p.connect("doc_content", "situations")  
    return p

async def start_analysis_service(document_id: UUID) -> Document:
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
    if document["status"] == "submitted":
        raise HTTPException(status_code=409, detail="Analysis already in progress for this document.")
    
    target_file_path = Path(settings.UPLOAD_DIR) / document["file_path"]

    if not target_file_path.exists():
        _error_message = "The document was found, but the associated file could not be located on the server."
        "It may have been moved or deleted."
        raise HTTPException(status_code=424, detail=_error_message)

    # Create a new analysis pipeline
    pipeline = await analysis_pipeline_factory()

    # Add the document to the pipeline
    try:
        # Start analysis
        await analysis_collection.update_one(
            {"_id": document_id},
            {"$set": {"status": "submitted"}}
        )

        results = pipeline.run(
            {"file_reader": 
                {"file_paths": [target_file_path]}
            }
        )

        _analysis = {    
            'situations' : results['situations'].get('analysis', {}).get("situations", []),
            'relations' : results['relations'].get('analysis', {}).get("relations", [])
        }

        # merge unique entities
        _situations_entities = results['situations'].get('analysis', {}).get("entities", [])
        _relations_entities = results['relations'].get('analysis', {}).get("entities", [])
        _unique_entities = set(tuple(sorted(entity.items())) for entity in _situations_entities + _relations_entities)

        _analysis["entities"]  = [
            dict(entity_tuple) for entity_tuple in _unique_entities
        ]

        document.update(analysis=_analysis, status="completed"))
        
    except Exception as e:
        document.update(analysis=None, status="failed")
        logger.error(f"Failed to analyze document: {e}", stack_info=True)
    
    finally:
        # Update the analysis record in MongoDB
        await analysis_collection.update_one(
            {"_id": document_id},
            {"$set": {"status": document["status"], 
                      "analysis": document["analysis"], 
                      "updated_at": datetime.utcnow()}}
        )
    
    if document["status"] == "failed":
        raise HTTPException(status_code=408, detail=f"Analysis failed for document {document_id}")
    
    return Document(**document)

async def get_analysis_service(document_id: UUID) -> Document:
    """
    Retrieves the analysis status and results for a document from MongoDB.
    """

    analysis_collection = get_analysis_collection()
    document = await analysis_collection.find_one({
        "_id": document_id,
    })
    
    if not document:
        raise HTTPException(status_code=404, detail="Document analysis not found.")
    
    return Document(**document)

async def commit_analysis_service(document_id: UUID, edited_document: Document) -> Document:
    """
    Commits (approves/rejects) the analysis results for a document in MongoDB.
    This also updates the analysis status to 'completed' or 'reviewed'.
    """
    raise HTTPException(status_code=501, detail=f"Method not yet implemented")
