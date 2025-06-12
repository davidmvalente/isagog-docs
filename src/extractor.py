import logging
from pathlib import Path

from typing import Optional, List
from haystack import Pipeline
from haystack.components.converters import (
    TextFileToDocument,
    PyPDFToDocument,
    DOCXToDocument,
    CSVToDocument,
)
from haystack_integrations.components.generators.openrouter import OpenRouterChatGenerator
from haystack.components.builders import ChatPromptBuilder
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.routers import FileTypeRouter
from haystack.components.joiners import DocumentJoiner
from haystack.components.validators import JsonSchemaValidator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret

from models import KnowledgeStub, Entities, Relations

logger = logging.getLogger(__name__)

DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"   

class KnowledgeStubExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4"):
        # Initialize  
        self.api_key = Secret.from_token(api_key)
        self.model = model
        
        # Define JSON schemas
        self.entity_schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "surface": {"type": "string"},
                            "concept": {"type": "string"}
                        },
                        "required": ["surface", "concept"]
                    }
                }
            },
            "required": ["entities"]
        }
        
        self.relation_schema = {
            "type": "object",
            "properties": {
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {
                                "type": "object",
                                "properties": {
                                    "surface": {"type": "string"},
                                    "concept": {"type": "string"}
                                }
                            },
                            "predicate": {"type": "string"},
                            "argument": {
                                "type": "object",
                                "properties": {
                                    "surface": {"type": "string"},
                                    "concept": {"type": "string"}
                                }
                            },
                            "context": {"type": "string"}
                        },
                        "required": ["subject", "predicate", "argument"]
                    }
                }
            },
            "required": ["relations"]
        }
        
        # Create unified pipeline
        self.pipeline = self._create_pipeline()

    def _generator_factory(self) -> OpenRouterChatGenerator:
        return OpenRouterChatGenerator(
            api_key=self.api_key,
            model=self.model,
            generation_kwargs={
                "temperature": 0.0,
                "max_tokens": 10000,
                "response_format": {"type": "json_object"}
            }
        )

    def _create_pipeline(self) -> Pipeline:
        # Define prompts
        entity_prompt = """
        Extract entities from this text and classify them:
        
        Text: {{ text }}
        
        Return JSON:
        {
            "entities": [
                {"surface": "entity text", "concept": "Person|Place|Organization|Event|Concept"}
            ]
        }
        """
        
        relation_prompt = """
        Extract relationships from this text using these entities:
        
        Text: {{ text }}
        Entities: {{ entities }}
        
        Return JSON:
        {
            "relations": [
                {
                    "subject": {"surface": "text", "concept": "type"},
                    "predicate": "relationship",
                    "argument": {"surface": "text", "concept": "type"},
                    "context": "sentence with relationship"
                }
            ]
        }
        """
        
        # Create pipeline
        pipeline = Pipeline()
        
        # Add file converters
        # File type routing
        file_type_router = FileTypeRouter(mime_types=["text/plain", 
                                                      "application/pdf", 
                                                      DOCX_MIMETYPE])
        # TODO: Add "text/markdown" to the list of supported mime types
        pipeline.add_component("file_type_router", file_type_router)

        # Filetype convertor
        pipeline.add_component("txt_converter", TextFileToDocument())
        pipeline.add_component("pdf_converter", PyPDFToDocument())
        pipeline.add_component("docx_converter", DOCXToDocument())
        # TODO: pipeline.add_component("csv_converter", CSVToDocument())

        # Preprocessing components
        pipeline.add_component("document_joiner", DocumentJoiner())
        pipeline.add_component("document_cleaner", DocumentCleaner())

        
        # Add entity KnowledgeStub components
        pipeline.add_component("entity_prompt", 
                               ChatPromptBuilder(template=[ChatMessage.from_user(entity_prompt)],
                                                 required_variables="*"))
        pipeline.add_component("entity_generator", self._generator_factory())
        pipeline.add_component("entity_validator", JsonSchemaValidator(json_schema=self.entity_schema))
        
        # Add relation KnowledgeStub components
        pipeline.add_component("relation_prompt",
                                ChatPromptBuilder(template=[ChatMessage.from_user(relation_prompt)],
                                                  required_variables="*"))
        pipeline.add_component("relation_generator", self._generator_factory())
        pipeline.add_component("relation_validator", JsonSchemaValidator(json_schema=self.relation_schema))
                
        # Connect the components
        # Router to Converters
        pipeline.connect("file_type_router.text/plain", "txt_converter.sources")
        pipeline.connect("file_type_router.application/pdf", "pdf_converter.sources")
        pipeline.connect("file_type_router"+"."+DOCX_MIMETYPE, "docx_converter.sources")
        #TODO: Add pipeline.connect("file_type_router.text/markdown", "markdown_converter.sources")

        # Join documents from different possible sources
        pipeline.connect("txt_converter", "document_joiner.documents")
        pipeline.connect("pdf_converter", "document_joiner.documents")
        pipeline.connect("docx_converter", "document_joiner.documents")
        #TODO: Add pipeline.connect("markdown_converter", "document_joiner.documents_3")

        # Clean
        pipeline.connect("document_joiner", "document_cleaner")
        
        # Entity KnowledgeStub chain
        pipeline.connect("document_cleaner.documents", "entity_prompt.text")
        pipeline.connect("entity_prompt.prompt", "entity_generator.messages")
        pipeline.connect("entity_generator.replies", "entity_validator")
        
        # Relation KnowledgeStub chain (uses both cleaned text and extracted entities)
        pipeline.connect("document_cleaner.documents", "relation_prompt.text")
        pipeline.connect("entity_validator.validated", "relation_prompt.entities")
        pipeline.connect("relation_prompt.prompt", "relation_generator.messages")
        pipeline.connect("relation_generator.replies", "relation_validator")
        
        return pipeline

    def _to_KnowledgeStub(self, valid_entities: List[dict], valid_relations: List[dict]) -> KnowledgeStub:
        """
        Instantiates pydantic Entity and Relation models from validated dictionary data,
        then wraps them in an KnowledgeStub object.

        Args:
            valid_entities: A list of dictionaries representing validated entities.
            valid_relations: A list of dictionaries representing validated relations.

        Returns:
            An KnowledgeStub model containing lists of Entity and Relation models.
        """
        try:
            # Instantiate Entity and Relation models from validated dictionaries
            entities = Entities.model_validate_json(valid_entities._content.text)
            relations = Relations.model_validate_json(valid_relations._content.text)
            
            # Instantiate KnowledgeStub model
            return KnowledgeStub(entities=entities, relations=relations)   
        
        except Exception as e:
            # Log specific Pydantic validation errors if possible
            logger.error(f"Failed to instantiate Pydantic models: {e}", stack_info=True)
            raise ValueError("Data did not conform to Pydantic models.") from e


    def extract(self, path: Path) -> Optional[KnowledgeStub]:

        try:

            result = self.pipeline.run(
                {"file_type_router": {"sources": [str(path)]}}
            )

            valid_entities = result.get("entity_validator", {}).get("validated", [])
            logger.info(f"Valid entities: {valid_entities}")
            validation_errors = result.get("entity_validator", {}).get("validation_errors", [])
            if validation_errors:
                logger.warning(f"Entity validation errors: {validation_errors}")

            valid_relations = result.get("relation_validator", {}).get("validated", [])
            logger.info(f"Valid relations: {valid_relations}")
            validation_errors = result.get("relation_validator", {}).get("validation_errors", [])
            if validation_errors:
                logger.warning(f"Relation validation errors: {validation_errors}")
          
            return self._to_KnowledgeStub(valid_entities[0], valid_relations[0])

        except Exception as e:
            logger.error(f"Extract failed for {path}: {e}", stack_info=True)
            raise e from None