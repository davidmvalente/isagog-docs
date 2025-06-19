# Isagog Documents Management API

This is a simple API for managing documents and their associated analysis.

## API Endpoints

### Document Management

- `GET /documents/`: List all documents
- `GET /documents/{document_id}`: Get a specific document by ID
- `GET /documents/{document_id}/download`: Download the file associated with a document
- `POST /documents/`: Create a new document with file upload
- `PUT /documents/{document_id}`: Update document metadata (not the file)
- `DELETE /documents/{document_id}`: Delete a document and its associated file

### Analysis

- `POST /documents/{document_id}/analysis`: Start analysis for a document
- `GET /documents/{document_id}/analysis`: Get analysis for a document for user review              
- `PUT /documents/{document_id}/analysis`: Commit analysis for a document   

## Development

### Prerequisites

- Python 3.11
- Poetry
- (Optional) Docker

### Setup

1. Clone the repository
2. Install dependencies with `poetry install`
3. Setup a tunnel to the MongoDB database, if not using Docker

```
ssh -L 16003:localhost:16003 isagog
```

### Run 

```
poetry run uvicorn isagog_docs.main:app --reload
```


## Production

### Docker build

1. Build the Docker image with `docker build -t isagog-docs .`

### (Optional) Create mongodb database and unprivileged user

1. Create a new database named `isagog` with `mongodb`
2. Create a new user named `isagog` with `mongodb`
3.  Grant privileges to the user with `mongodb`
```
db.createUser(
    {
        user: "isagog",
        pwd: "password",
        roles: [
            {
                role: "readWrite",
                db: "isagog"
            }
        ]
    }
)
```
4.  Create a new role named `isagog` with `mongodb`
```
db.createRole(
    {
        role: "isagog",
        privileges: [
            {
                resource: { db: "isagog", collection: "docs" },
                                actions: ["find", "insert", "update", "remove"]
            }
        ],
        roles: []
    }
)
```

### Start

Start all services.

```
docker compose up -d
```