import pytest
import uuid
import asyncio
from datetime import datetime

# Helper to create test document in DB
def create_test_document(db, **overrides):
    doc = {
        "_id": uuid.uuid4(),
        "status": "draft",
        "file_name": "test.pdf",
        "file_path": "/uploads/test.pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "title": "Test Document",
        "description": "Test description",
        "author": "Test Author",
        "tags": ["test"],
        "creation_date": datetime.utcnow(),
        "updated_date": datetime.utcnow(),
        "deleted": False
    } | overrides
    db.insert_one(doc)
    return doc["_id"]

# POST /documents/
@pytest.mark.anyio
async def test_create_document_missing_file(async_client):
    response = await async_client.post("/documents/", json={"title": "Test"})
    assert response.status_code == 422
    assert "file" in response.text

@pytest.mark.anyio
async def test_create_document_invalid_filetype(async_client):
    files = {"file": ("test.txt", b"content", "text/plain")}
    data = {
        "title": "Test",
        "author": "Author",
        "description": "Description",
        "tags": ["tag1"]
    }
    response = await async_client.post("/documents/", data=data, files=files)
    assert response.status_code == 400
    assert "Unsupported file type" in response.text

@pytest.mark.anyio
async def test_create_document_missing_metadata(async_client):
    files = {"file": ("test.pdf", b"content", "application/pdf")}
    response = await async_client.post("/documents/", files=files, data={})
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "title"] for e in errors)

@pytest.mark.anyio
async def test_create_document_invalid_metadata(async_client):
    files = {"file": ("test.pdf", b"content", "application/pdf")}
    data = {
        "title": "",  # Invalid min_length
        "author": "A" * 101,  # Exceeds max_length
        "tags": ["   ", ""]  # Empty tags
    }
    response = await async_client.post("/documents/", files=files, data=data)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(e["loc"] == ["body", "title"] for e in errors)
    assert any(e["loc"] == ["body", "author"] for e in errors)

# GET /documents/
@pytest.mark.anyio
async def test_list_documents_empty(async_client):
    response = await async_client.get("/documents/")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.anyio
async def test_list_documents_invalid_data(async_client, db):
    # Create document with invalid status
    db.insert_one({
        "_id": uuid.uuid4(),
        "status": "invalid_status",
        "title": "Invalid Document"
    })
    response = await async_client.get("/documents/")
    assert response.status_code == 500
    assert "Invalid document status" in response.text

# GET /documents/{document_id}
@pytest.mark.anyio
async def test_get_document_not_found(async_client):
    response = await async_client.get(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404

@pytest.mark.anyio
async def test_get_deleted_document(async_client, db):
    doc_id = create_test_document(db, deleted=True)
    response = await async_client.get(f"/documents/{doc_id}")
    assert response.status_code == 410

# GET /documents/{document_id}/download
@pytest.mark.anyio
async def test_download_missing_document(async_client):
    response = await async_client.get(f"/documents/{uuid.uuid4()}/download")
    assert response.status_code == 404

@pytest.mark.anyio
async def test_download_deleted_document(async_client, db):
    doc_id = create_test_document(db, deleted=True)
    response = await async_client.get(f"/documents/{doc_id}/download")
    assert response.status_code == 410

# PUT /documents/{document_id}
@pytest.mark.anyio
async def test_update_missing_document(async_client):
    response = await async_client.put(f"/documents/{uuid.uuid4()}", json={"title": "New Title"})
    assert response.status_code == 404

@pytest.mark.anyio
async def test_update_deleted_document(async_client, db):
    doc_id = create_test_document(db, deleted=True)
    response = await async_client.put(f"/documents/{doc_id}", json={"title": "New Title"})
    assert response.status_code == 410

@pytest.mark.anyio
async def test_update_invalid_metadata(async_client, db):
    doc_id = create_test_document(db)
    
    # Test invalid title
    response = await async_client.put(f"/documents/{doc_id}", json={"title": ""})
    assert response.status_code == 422
    
    # Test invalid tags
    response = await async_client.put(f"/documents/{doc_id}", json={"tags": ["   ", ""]})
    assert response.status_code == 422

# DELETE /documents/{document_id}
@pytest.mark.anyio
async def test_delete_missing_document(async_client):
    response = await async_client.delete(f"/documents/{uuid.uuid4()}")
    assert response.status_code == 404

@pytest.mark.anyio
async def test_delete_already_deleted(async_client, db):
    doc_id = create_test_document(db, deleted=True)
    response = await async_client.delete(f"/documents/{doc_id}")
    assert response.status_code == 410

# Concurrency tests
@pytest.mark.anyio
async def test_concurrent_operations(async_client, db):
    # Create initial document
    doc_id = create_test_document(db)
    
    # Simulate concurrent update and download
    update_task = async_client.put(f"/documents/{doc_id}", json={"title": "Updated"})
    download_task = async_client.get(f"/documents/{doc_id}/download")
    
    update_response, download_response = await asyncio.gather(update_task, download_task)
    
    assert update_response.status_code == 200
    assert download_response.status_code == 200
    
    # Verify update was applied
    doc = db.find_one({"_id": doc_id})
    assert doc["title"] == "Updated"