import time
import logging
from pathlib import Path

from pymongo import MongoClient

from config import Config
from extractor import KnowledgeStubExtractor

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, config: Config):
        self.config = config
        self.mongo_client = MongoClient(config.mongo_uri)
        self.db = self.mongo_client[config.db_name]
        self.collection = self.db[config.collection_name]
        
        self.extractor = KnowledgeStubExtractor(config.openrouter_api_key, 
                                            config.openrouter_model)
        
    
    def process_document(self, file_path: Path) -> bool:
        document_id = file_path.stem
        start_time = time.time()
        
        try:
            logger.info(f"Processing {file_path}")
        
            # Extract knowledge
            analysis = self.extractor.extract(file_path)
                        
            # Save knowledge stub to MongoDB
            self.collection.replace_one(
                {"_id": document_id},
                {
                    "analysis": analysis.model_dump(),
                    "status": "ready"
                },
                upsert=True
            )
            
            logger.info(f"Processed {document_id}: {len(analysis.entities)} entities, {len(analysis.relations)} relations in {round(time.time() - start_time, 2)} seconds") 
            return True
        
        except Exception as e:
            logger.error(f"Failed to process {document_id}: {e}")
            self._log_error(document_id, str(e))
            return False
        
    def _log_error(self, document_id: str, error: str):
        """Log processing error"""

        try:
            logger.error(f"Failed to process {document_id}: {error}", stack_info=True)
            self.collection.replace_one(
                {"_id": document_id},
                {"$set": {"processing_status": "failed", "error": error}},
                upsert=True
            )
            # self.db.processing_errors.insert_one(error_record)
        except Exception as e:
            logger.error(f"Failed to log error: {e}", stack_info=True)