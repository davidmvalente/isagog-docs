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
from haystack.components.builders import PromptBuilder
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.validators import JsonSchemaValidator
from haystack.utils import Secret

from models import Analysis

logger = logging.getLogger(__name__)

class KnowledgeStubExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4"):
        # Initialize components
        self.generator = OpenRouterChatGenerator(
            api_key=Secret.from_token(api_key),
            model=model,
            generation_kwargs={
                "temperature": 0.0,
                "max_tokens": 10000,
                "response_format": {"type": "json_object"}
            }
        )
        
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
        pipeline.add_component("text_converter", TextFileToDocument())
        pipeline.add_component("pdf_converter", PyPDFToDocument())
        pipeline.add_component("docx_converter", DOCXToDocument())
        pipeline.add_component("csv_converter", CSVToDocument())
        pipeline.add_component("cleaner", DocumentCleaner())
        
        # Add entity extraction components
        pipeline.add_component("entity_prompt", PromptBuilder(template=entity_prompt))
        pipeline.add_component("entity_generator", self.generator)
        pipeline.add_component("entity_validator", JsonSchemaValidator(schema=self.entity_schema))
        
        # Add relation extraction components
        pipeline.add_component("relation_prompt", PromptBuilder(template=relation_prompt))
        pipeline.add_component("relation_generator", self.generator)
        pipeline.add_component("relation_validator", JsonSchemaValidator(schema=self.relation_schema))
                
        # Connect the components
        # File conversion to cleaner
        pipeline.connect("text_converter.documents", "cleaner.documents")
        pipeline.connect("pdf_converter.documents", "cleaner.documents")
        pipeline.connect("docx_converter.documents", "cleaner.documents")
        pipeline.connect("csv_converter.documents", "cleaner.documents")
        
        # Entity extraction chain
        pipeline.connect("cleaner.documents", "entity_prompt.text")
        pipeline.connect("entity_prompt", "entity_generator")
        pipeline.connect("entity_generator.replies", "entity_validator")
        
        # Relation extraction chain (uses both cleaned text and extracted entities)
        pipeline.connect("cleaner.documents", "relation_prompt.text")
        pipeline.connect("entity_validator.validated", "relation_prompt.entities")
        pipeline.connect("relation_prompt", "relation_generator")
        pipeline.connect("relation_generator.replies", "relation_validator")
        
        return pipeline

    def extract(self, path: Path) -> Optional[Analysis]:

        try:
            # Select the appropriate converter based on file type
            match path.suffix.lower():
                case ".txt":
                    result = self.pipeline.run(
                        {"text_converter": {"sources": [str(path)]}}
                    )
                case ".pdf":
                    result = self.pipeline.run(
                        {"pdf_converter": {"sources": [str(path)]}}
                    )
                case ".docx":
                    result = self.pipeline.run(
                        {"docx_converter": {"sources": [str(path)]}}
                    )
                case ".csv":
                    result = self.pipeline.run(
                        {"csv_converter": {"sources": [str(path)]}}
                    )
                case _:
                    logger.error(f"Unsupported file type: {path.suffix}")
                    return None
            
            return Analysis(
                entities=result.get("entity_validator", {}).get("validated", {}),
                relations=result.get("relation_validator", {}).get("validated", {})
            )

        except Exception as e:
            logger.error(f"Processing failed for {path}: {e}", stack_info=True)
            return None