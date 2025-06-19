import os
import logging
from pathlib import Path
from typing import Optional
import toml
from isagog.components.utilities.prompting import Prompt
from isagog.components.analyzers.analyzer import Frame

logger = logging.getLogger(__name__)

_CONCEPT_PROMPT_IT = Prompt(  
    name="concept_analysis",
    language="it",
    output_format="json",
    description="Un prompt per analizzare entità e relazioni in un testo",
    version="1.0",
    template="""
Sei un assistente competente ed esperto, in grado di identificare entità e relazioni in un testo in {{language}}.

Istruzioni:
1. Identifica le entità nel testo, concentrandoti (ma non limitandoti) sui seguenti:
** Concetti **
{{concepts}}
2. Identifica le relazioni tra le entità nel testo, concentrandoti (ma non limitandoti) sulle seguenti:
** Relazioni **
{{relations}}
3. Se un'entità o una relazione rilevante non rientra in queste categorie, introducine una nuova con un nome adeguato.
4. Le relazioni devono essere espresse come soggetto, predicato e argomento (oggetto).
5. Il predicato deve essere una frase concisa in {{language}} (massimo 3 parole).
6. Per le relazioni, aggiungi il passaggio in cui la relazione è menzionata (contesto).
   Il contesto deve essere un passaggio testuale completo che esplicitamente affermi o chiaramente implichi la relazione.

Formato di output:
Fornisci l'output in {{language}} utilizzando il seguente formato JSON:

{  
  "entities": [
   {"surface": "Entity Name", "concept": "Entity Type"}, 
   ...
  ],
  "relations": [
   { 
    "subject": {"surface": "Entity Name", "concept": "Type"}, 
    "predicate": "predicate sentence",
    "argument": {"surface": "Entity Name", "concept": "Type"}, 
    "context": "context passage"
   },
   ...
  ]
} 

Example:
{ 
  "entities": [
   { 
    "surface": "Mario Rossi",
    "concept": "Person"
   },
   { 
    "surface": "Milano",
    "concept": "City"
   },
   { 
    "surface": "Corriere della Sera",
    "concept": "Organization"
   }],
  "relations": [
   { 
    "subject": { 
      "surface": "Mario Rossi",
      "concept": "Person"
    },
    "predicate": "è inviato da",
    "argument": { 
      "surface": "Corriere della Sera",
      "concept": "Organization"
    },
    "context": "Mario Rossi è inviato dal Corriere della Sera a Milano."
   },
   { 
    "subject": { 
      "surface": "Mario Rossi",
      "concept": "Person"
    },
    "predicate": "è inviato a",
    "argument": { 
      "surface": "Milano",
      "concept": "City"
    },
    "context": "Mario Rossi è inviato dal Corriere della Sera a Milano."
   }
  ]
} 
Ricorda di restituire solo la struttura JSON, senza testo aggiuntivo prima o dopo.

Testo:

{{text}} 
"""
)

_MAXXI_CONCEPT_FRAME_IT = Frame(
    name="maxxi_concept_frame",
    language="it",
    description="Frame per l'analisi dei concetti e delle relazioni nel contesto del MAXXI",
    version="1.0",
    concepts=[
        "Persona", "Organizzazione", "Luogo", "Evento", "Situazione", 
        "Oggetto", "Concetto", "Qualità", "Data", "Periodo", "Numero"
    ],
    relations=[
        "(Oggetto) è parte di (Oggetto)",
        "(Concetto) è un tipo di (Concetto)", 
        "(Persona) è membro di (Organizzazione)",
        "(Evento) ha luogo in (Luogo)",
        "(Oggetto) si trova in (Luogo)",
        "(Persona, Organizzazione) partecipa a (Evento, Situazione)",
        "(Evento) è il risultato di (Evento)",
        "(Oggetto) appartiene a (Organizzazione)",
        "(Concetto) si riferisce a (Concetto)",
        "(Persona, Organizzazione, Luogo, Evento, Situazione, Oggetto) ha qualità (Qualità)"
    ]
)


_SITUATION_PROMPT_IT = Prompt(  
    name="davidson_analysis_it",
    language="it",
    variables=["text", "language", "concepts", "situations", "roles"],
    output_format="json",
    description="Un prompt per analizzare eventi e i loro partecipanti in un testo.",
    version="1.0",
    template="""
Sei un assistente esperto e utile che può identificare situazioni, eventi e le entità che vi prendono parte.
Ti verrà presentato un testo in lingua {{language}}.

Istruzioni:
1. Identifica le entità nel testo, concentrandoti (ma non limitandoti) sui seguenti tipi:
** Tipi di entità **
{{concepts}}
2. Identifica eventi e situazioni nel testo, concentrandoti (ma non limitandoti) sui seguenti tipi:
** Tipi di situazioni **
{{situations}}
3. Se un'entità o una situazione rilevante non rientra in queste categorie, introduci una nuova categoria con un nome appropriato.
4. Per ogni entità, fornisci il suo nome e il tipo.
5. Per ogni situazione:
   a) fornisci una breve descrizione e il passaggio in cui è menzionata (verbatim).
   b) identifica le entità che vi prendono parte e il ruolo che hanno nella situazione, secondo i seguenti predicati:
     {{roles}}

Formato di output:
Fornisci l'output utilizzando il seguente formato JSON:
** Formato **
{  
  "entities": [
   {"surface": "entity name", "concept": "entity kind"}, 
   ...
  ],
  "situations": [
   { 
    "description" : "descrizione della situazione",
    "concept" : "tipo di situazione",
    "passage" : "passaggio della situazione",
    "entities": [
     { 
      "surface": "nome dell'entità",
      "concept": "tipo dell'entità",
      "role": "ruolo nella situazione"
     },
     ...
    ]
   },
   ...
  ]
} 

Usa esclusivamente la lingua {{language}} per i nomi delle entità e le descrizioni delle situazioni.

** Esempio **
Il seguente è un esempio del formato di output atteso.
Esempio:
{ 
  "entities": [
   { 
    "surface": "Mario Rossi",
    "concept": "Person"
   },
   { 
    "surface": "Milano",
    "concept": "City"
   },
   { 
    "surface": "Corriere della Sera",
    "concept": "Organization"
   }],
  "situations": [
   { 
    "description": "invio di Mario Rossi a Milano",
    "concept": "Event",
    "passage": "Mario Rossi è inviato dal Corriere della Sera a Milano.",
    "entities": [
     {
      "surface": "Mario Rossi",
      "concept": "Person",
      "role": "subject"
     },
     {
      "surface": "Corriere della Sera",
      "concept": "Organization",
      "role": "agent"
     },
    {
        "surface": "Milano",
        "concept": "City",
        "role": "location"
    } 
    ]
  ]
} 
** Nota **
Ricorda di fornire solo la struttura JSON senza testo aggiuntivo prima o dopo.

** Testo **

{{text}} 
"""
)


_SITUATIION_FRAME_IT = Frame(
            name="davidson_frame_it",
            concepts=["Persona", "Organizzazione", "Luogo"],
            situations=["Evento", "Azione", "Stato"],
            roles=["subject", "object", "agent", "patient", "location"],
            version="1.0",
            language="it",
            description="A frame for Davidson's analysis in Italian"
        )


def secret_or_env(secret_name: str, file_paths: Optional[list] = None, _raise: bool = False) -> str | None:
    """Get secret from multiple files or environment variable."""
    logger.debug(f"Entering secret_or_env for secret: {secret_name}")

    if file_paths is None:
        file_paths = ["/run/secrets", "~/.secrets", "../secrets"]

    for file_path in file_paths:
        expanded_path = os.path.expanduser(file_path)
        full_path = os.path.join(expanded_path, secret_name)
        try:
            with open(full_path) as f:
                logger.debug(f"Found secret {secret_name} in {file_path}")
                return f.read().strip()
        except (FileNotFoundError, PermissionError) as e:
            logger.debug("File open error: %s, %s", (file_path + "/" + secret_name), e)

    result = os.environ.get(secret_name)
    logger.debug(f"Falling back to environment variable for {secret_name}: {'found' if result else 'not found'}")
    if _raise and result is None:
        raise RuntimeError(f"Secret {secret_name} not found")
    return result

class Config:
    """Application configuration loaded from secrets, environment, and static values."""

    def __init__(self):
        # Load project metadata from pyproject.toml
        metadata = toml.load("./pyproject.toml")["tool"]["poetry"]

        # Project metadata
        self.PROJECT_NAME = metadata["name"]
        self.PROJECT_DESCRIPTION = metadata["description"]
        self.PROJECT_VERSION = metadata["version"]
        self.API_V1_STR = "/api/v1"
        self.APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
        self.APP_PORT = int(os.getenv("APP_PORT", "8000")) 
        self.APP_WORKERS = int(os.getenv("APP_WORKERS", "4"))

        # Directories and limits
        self.UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))
        self.MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
        self.MAX_FILE_SIZE_BYTES = self.MAX_FILE_SIZE_MB * 1024 * 1024

        # MongoDB
        self.MONGO_URI = secret_or_env("MONGO_URI", _raise=True)
        self.MONGO_DB = os.getenv("MONGO_DB", "dev")
        self.MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "docs")

        # OpenRouter
        self.OPENROUTER_API_KEY = secret_or_env("OPENROUTER_API_KEY", _raise=True)
        self.OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
        self.OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.1"))

        # Prompting
        self.CONCEPT_PROMPT = _CONCEPT_PROMPT_IT
        self.CONCEPT_FRAME = _MAXXI_CONCEPT_FRAME_IT
        self.SITUATION_PROMPT = _SITUATION_PROMPT_IT
        self.SITUATION_FRAME = _SITUATIION_FRAME_IT

# Singleton config instance
settings = Config()
