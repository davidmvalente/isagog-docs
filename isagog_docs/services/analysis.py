"""
app/services/analysis.py

Contains business logic for document analysis operations and upload to MongoDB.
"""
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException
from pymongo.collection import Collection
from haystack import Pipeline, component
from haystack import Document as HaystackDocument
from haystack.components.preprocessors import DocumentCleaner

from isagog.components.proxy.openrouter_proxy import OpenRouterProxy
from isagog.components.readers.file_reader import FileReader
from isagog.components.analyzers.concept_analyzer import ConceptAnalyzer  
from isagog.components.analyzers.situation_analyzer import SituationAnalyzer

from isagog_docs.core.config import Config
from isagog_docs.schemas.document import Document

logger = logging.getLogger(__name__)

@component
class DocumentToString:
    """Component to extract text content from Haystack documents."""
    
    @component.output_types(text=str)
    def run(self, documents: List[HaystackDocument]) -> Dict[str, str]:
        """Extract text from the first document in the list."""
        if not documents:
            return {"text": ""}
        return {"text": documents[0].content}



class AnalysisPipelineBuilder:
    """Builder class for creating analysis pipelines."""
    
    def __init__(self, config: Config):
        self.config = config
        self.pipeline = Pipeline()
        self._llm_factory = lambda: OpenRouterProxy(
            api_key=self.config.OPENROUTER_API_KEY,
            model=self.config.OPENROUTER_MODEL,
            temperature=self.config.OPENROUTER_TEMPERATURE,
        )
    
    def build(self) -> Pipeline:
        """Build and configure the analysis pipeline."""
        self._add_components()
        self._connect_components()
        return self.pipeline
    
    def _add_components(self) -> None:
        """Add all required components to the pipeline."""
        components = {
            "file_reader": FileReader(),
            "document_cleaner": DocumentCleaner(),
            "doc_content": DocumentToString(),
            "relations": ConceptAnalyzer(
                llm_generator=self._llm_factory(),
                prompt=self.config.CONCEPT_PROMPT,
                frame=self.config.CONCEPT_FRAME
            ),
            "situations": SituationAnalyzer(
                llm_generator=self._llm_factory(),
                prompt=self.config.SITUATION_PROMPT,
                frame=self.config.SITUATION_FRAME
            )
        }
        
        for name, component in components.items():
            self.pipeline.add_component(name, component)
    
    def _connect_components(self) -> None:
        """Connect pipeline components."""
        connections = [
            ("file_reader", "document_cleaner"),
            ("document_cleaner", "doc_content"),
            ("doc_content", "relations"),
            ("doc_content", "situations")
        ]
        
        for source, target in connections:
            self.pipeline.connect(source, target)


class AnalysisService:
    """Service class for handling document analysis operations."""
    
    def __init__(self, collection: Collection, config: Config):
        self.analysis_collection = collection
        self.config = config
        self.pipeline = AnalysisPipelineBuilder(config).build()

    async def start_analysis(self, document_id: UUID) -> Document:
        """
        Initiates an analysis process for a given document in MongoDB.
        
        Args:
            document_id: UUID of the document to analyze
            
        Returns:
            Document: The analyzed document
            
        Raises:
            HTTPException: If document not found, analysis in progress, or file missing
        """
        document = await self._get_document_or_raise(document_id)
        # Check if analysis is already pending for this document
        if document["status"] == "submitted":
            raise HTTPException(
                status_code=409,
                detail="Analysis already in progress for this document."
            )
        
        file_path = self._get_file_path(document)
        self._validate_file_exists(file_path)
        
        await self._update_document_status(document_id, "submitted")
        
        try:
            analysis_results = await self._run_analysis_pipeline(file_path)
            processed_analysis = self._process_analysis_results(analysis_results)
            
            document.update(analysis=processed_analysis, status="completed")
            
        except Exception as e:
            document.update(analysis=None, status="failed")
            logger.error(f"Failed to analyze document {document_id}: {e}", exc_info=True)
            
        finally:
            await self._update_document_analysis(document_id, document)
        
        if document["status"] == "failed":
            raise HTTPException(
                status_code=408, 
                detail=f"Analysis failed for document {document_id}"
            )
        
        return Document(**document)
    
    async def get_analysis(self, document_id: UUID) -> Document:
        """
        Retrieves the analysis status and results for a document from MongoDB.
        
        Args:
            document_id: UUID of the document
            
        Returns:
            Document: The document with analysis results
        """
        document = await self.analysis_collection.find_one({"_id": document_id})
        
        if not document:
            raise HTTPException(
                status_code=404, 
                detail="Document analysis not found."
            )
        
        return Document(**document)
    
    async def commit_analysis(self, document_id: UUID, edited_document: Document) -> Document:
        """
        Commits (approves/rejects) the analysis results for a document in MongoDB.
        
        Args:
            document_id: UUID of the document
            edited_document: The edited document to commit
            
        Returns:
            Document: The committed document
            
        Raises:
            HTTPException: Method not yet implemented
        """
        raise HTTPException(
            status_code=501, 
            detail="Method not yet implemented"
        )
    
    async def _get_document_or_raise(self, document_id: UUID) -> Dict[str, Any]:
        """Get document from database or raise HTTPException if not found."""
        document = await self.analysis_collection.find_one({"_id": document_id})
        
        if not document:
            raise HTTPException(
                status_code=404, 
                detail="Document not found"
            )
        
        return document
    
    def _validate_analysis_can_start(self, document: Dict[str, Any]) -> None:
        """Validate that analysis can be started for the document."""
        if document["status"] == "submitted":
            raise HTTPException(
                status_code=409,
                detail="Analysis already in progress for this document."
            )
    
    def _get_file_path(self, document: Dict[str, Any]) -> Path:
        """Get the file path for the document."""
        return Path(self.config.UPLOAD_DIR) / document["file_path"]
    
    def _validate_file_exists(self, file_path: Path) -> None:
        """Validate that the file exists on the filesystem."""
        if not file_path.exists():
            error_message = (
                "The document was found, but the associated file could not be "
                "located on the server. It may have been moved or deleted."
            )
            raise HTTPException(status_code=424, detail=error_message)
    
    async def _update_document_status(self, document_id: UUID, status: str) -> None:
        """Update document status in the database."""
        await self.analysis_collection.update_one(
            {"_id": document_id},
            {"$set": {"status": str, 
                      "updated_at": datetime.utcnow()}}
        )
    
    async def _run_analysis_pipeline(self, file_path: Path) -> Dict[str, Any]:
        """Run the analysis pipeline on the given file."""
        
        return self.pipeline.run({
            "file_reader": {"file_paths": [file_path]}
        })
    
    def _process_analysis_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Process and merge analysis results."""
        situations_data = results.get('situations', {}).get('analysis', {})
        relations_data = results.get('relations', {}).get('analysis', {})
        
        analysis = {
            'situations': situations_data.get("situations", []),
            'relations': relations_data.get("relations", [])
        }
        
        # Merge unique entities
        situations_entities = situations_data.get("entities", [])
        relations_entities = relations_data.get("entities", [])
        
        unique_entities = self._merge_unique_entities(
            situations_entities, 
            relations_entities
        )
        
        analysis["entities"] = unique_entities
        return analysis
    
    def _merge_unique_entities(
        self, 
        situations_entities: List[Dict], 
        relations_entities: List[Dict]
    ) -> List[Dict]:
        """Merge and deduplicate entities from different analysis components."""
        all_entities = situations_entities + relations_entities
        unique_entity_tuples: Set[Tuple] = set(
            tuple(sorted(entity.items())) for entity in all_entities
        )
        
        return [dict(entity_tuple) for entity_tuple in unique_entity_tuples]
    
    async def _update_document_analysis(
        self, 
        document_id: UUID, 
        document: Dict[str, Any]
    ) -> None:
        """Update document analysis results in the database."""
        await self.analysis_collection.update_one(
            {"_id": document_id},
            {
                "$set": {
                    "status": document["status"],
                    "analysis": document["analysis"]
                }
            }
        )
