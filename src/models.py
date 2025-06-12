from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

class Entity(BaseModel):
    surface: str
    concept: str

class Relation(BaseModel):
    subject: Entity
    predicate: str
    argument: Entity
    context: str

class Analysis(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
