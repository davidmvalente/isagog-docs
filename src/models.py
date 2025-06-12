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

    def __len__(self):
        return len(self.relations)  

class Entities(BaseModel):
    entities: List[Entity]

    def __len__(self):
        return len(self.entities)

class KnowledgeStub(BaseModel):
    entities: Entities
    relations: Relations
