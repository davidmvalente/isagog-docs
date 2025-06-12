from typing import List
from pydantic import BaseModel

class Entity(BaseModel):
    surface: str
    concept: str

class Relation(BaseModel):
    subject: Entity
    predicate: str
    argument: Entity
    context: str

class Relations(BaseModel):
    relations: List[Relation]

class Entities(BaseModel):
    entities: List[Entity]

class KnowledgeStub(BaseModel):
    entities: Entities
    relations: Relations
