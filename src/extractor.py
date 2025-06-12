import logging
from pathlib import Path

from typing import Optional
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

from models import Analysis, Entity, Relation

logger = logging.getLogger(__name__)

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
        file_type_router = FileTypeRouter(mime_types=["text/plain", "application/pdf", "text/markdown"])
        pipeline.add_component("file_type_router", file_type_router)

        # Filetype convertor
        pipeline.add_component("txt_converter", TextFileToDocument())
        pipeline.add_component("pdf_converter", PyPDFToDocument())
        # TODO: pipeline.add_component("docx_converter", DOCXToDocument())
        # TODO: pipeline.add_component("csv_converter", CSVToDocument())

        # Preprocessing components
        pipeline.add_component("document_joiner", DocumentJoiner())
        pipeline.add_component("document_cleaner", DocumentCleaner())

        
        # Add entity extraction components
        pipeline.add_component("entity_prompt", 
                               ChatPromptBuilder(template=[ChatMessage.from_user(entity_prompt)],
                                                 required_variables="*"))
        pipeline.add_component("entity_generator", self._generator_factory())
        pipeline.add_component("entity_validator", JsonSchemaValidator(json_schema=self.entity_schema))
        
        # Add relation extraction components
        pipeline.add_component("relation_prompt",
                                ChatPromptBuilder(template=[ChatMessage.from_user(relation_prompt)],
                                                  required_variables="*"))
        pipeline.add_component("relation_generator", self._generator_factory())
        pipeline.add_component("relation_validator", JsonSchemaValidator(json_schema=self.relation_schema))
                
        # Connect the components
        # Router to Converters
        pipeline.connect("file_type_router.text/plain", "txt_converter.sources")
        pipeline.connect("file_type_router.application/pdf", "pdf_converter.sources")
        #TODO: pipeline.connect("file_type_router.text/markdown", "markdown_converter.sources")

        # Join documents from different possible sources
        pipeline.connect("txt_converter", "document_joiner.documents")
        pipeline.connect("pdf_converter", "document_joiner.documents")
        #TODO: pipeline.connect("markdown_converter", "document_joiner.documents_3")

        # Clean
        pipeline.connect("document_joiner", "document_cleaner")
        
        # Entity extraction chain
        pipeline.connect("document_cleaner.documents", "entity_prompt.text")
        pipeline.connect("entity_prompt.prompt", "entity_generator.messages")
        pipeline.connect("entity_generator.replies", "entity_validator")
        
        # Relation extraction chain (uses both cleaned text and extracted entities)
        pipeline.connect("document_cleaner.documents", "relation_prompt.text")
        pipeline.connect("entity_validator.validated", "relation_prompt.entities")
        pipeline.connect("relation_prompt.prompt", "relation_generator.messages")
        pipeline.connect("relation_generator.replies", "relation_validator")
        
        return pipeline

    def extract(self, path: Path) -> Optional[Analysis]:

        try:

            result = self.pipeline.run(
                {"file_type_router": {"sources": [str(path)]}}
            )

            valid_entities = result.get("entity_validator", {}).get("validated", [])
            validation_errors = result.get("entity_validator", {}).get("validation_errors", [])
            if validation_errors:
                logger.warning(f"Entity validation errors: {validation_errors}")

            valid_relations = result.get("relation_validator", {}).get("validated", [])
            validation_errors = result.get("relation_validator", {}).get("validation_errors", [])
            if validation_errors:
                logger.warning(f"Relation validation errors: {validation_errors}")
          
            return Analysis(
                entities=[ Entity(e) for e in valid_entities ],
                relations=[ Relation(r) for r in valid_relations ]
            )

        except Exception as e:
            logger.error(f"Processing failed for {path}: {e}", stack_info=True)
            raise e from None