import pytest
import uuid
import asyncio
from datetime import datetime

# POST /documents/{document_id}/analysis/ - START ANALYSIS
@pytest.mark.anyio
async def test_start_analysis_document_not_found(async_client):
    response = await async_client.post(f"/documents/{uuid.uuid4()}/analysis/")
    assert response.status_code == 404

@pytest.mark.anyio
async def test_start_analysis_already_in_progress(async_client, create_document):
    doc_id = create_document(status="submitted")
    response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 409
    assert "already in progress" in response.text

@pytest.mark.anyio
async def test_start_analysis_document_deleted(async_client, create_document):
    doc_id = create_document(deleted=True)
    response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 410

@pytest.mark.anyio
async def test_start_analysis_already_exists(async_client, create_document):
    doc_id = create_document(
        status="completed",
        analysis={"result": "test", "last_updated": datetime.utcnow()}
    )
    response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 409
    assert "already exists" in response.text

# Concurrency test for analysis start
@pytest.mark.anyio
async def test_start_analysis_concurrency(async_client, create_document):
    doc_id = create_document()
    
    async def start_analysis():
        return await async_client.post(f"/documents/{doc_id}/analysis/")
    
    # Start multiple analysis requests simultaneously
    tasks = [asyncio.create_task(start_analysis()) for _ in range(3)]
    responses = await asyncio.gather(*tasks)
    
    # Only one should succeed (201), others should conflict (409)
    status_codes = [r.status_code for r in responses]
    assert 201 in status_codes
    assert status_codes.count(409) == 2

# GET /documents/{document_id}/analysis/ - GET ANALYSIS FOR REVIEW
@pytest.mark.anyio
async def test_get_analysis_document_not_found(async_client):
    response = await async_client.get(f"/documents/{uuid.uuid4()}/analysis/")
    assert response.status_code == 404

@pytest.mark.anyio
async def test_get_analysis_in_progress(async_client, create_document):
    doc_id = create_document(status="submitted")
    response = await async_client.get(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 409
    assert "in progress" in response.text

# PUT /documents/{document_id}/analysis/ - COMMIT ANALYSIS
@pytest.mark.anyio
async def test_commit_analysis_document_not_found(async_client):
    response = await async_client.put(f"/documents/{uuid.uuid4()}/analysis/", json={"is_approved": True})
    assert response.status_code == 404

@pytest.mark.anyio
async def test_commit_analysis_not_exists(async_client, create_document):
    doc_id = create_document(status="draft")
    response = await async_client.put(f"/documents/{doc_id}/analysis/", json={"is_approved": True})
    assert response.status_code == 404
    assert "No analysis" in response.text

@pytest.mark.anyio
async def test_commit_analysis_in_progress(async_client, create_document):
    doc_id = create_document(
        status="submitted",
        analysis={"result": "partial", "last_updated": datetime.utcnow()}
    )
    response = await async_client.put(f"/documents/{doc_id}/analysis/", json={"is_approved": True})
    assert response.status_code == 409
    assert "still in progress" in response.text

# Advanced concurrency tests
@pytest.mark.anyio
async def test_analysis_lifecycle_concurrency(async_client, create_document):
    # Create document
    doc_id = create_document()
    
    # Start analysis
    start_response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert start_response.status_code == 201
    
    # Simulate concurrent operations
    async def get_analysis():
        return await async_client.get(f"/documents/{doc_id}/analysis/")
    
    async def commit_analysis():
        return await async_client.put(
            f"/documents/{doc_id}/analysis/",
            json={"is_approved": True}
        )
    
    # Should get "in progress" error for both
    get_response, commit_response = await asyncio.gather(
        get_analysis(),
        commit_analysis()
    )
    
    assert get_response.status_code == 409
    assert commit_response.status_code == 409
    
"""     # Simulate analysis completion
    db.update_one(
        {"_id": doc_id},
        {"$set": {"status": "completed", "analysis.result": "final"}}
    )
    
    # Now should be able to get and commit
    get_response = await async_client.get(f"/documents/{doc_id}/analysis/")
    commit_response = await async_client.put(
        f"/documents/{doc_id}/analysis/",
        json={"is_approved": True}
    )
    
    assert get_response.status_code == 200
    assert isinstance(get_response.json(), dict)
    assert commit_response.status_code == 200
    
    # Verify status changed to approved
    doc = db.find_one({"_id": doc_id})
    assert doc["status"] == "approved"

# Test analysis status transitions
@pytest.mark.anyio
async def test_analysis_status_flow(async_client, create_document):
    doc_id = create_document()
    
    # Start analysis
    response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 201
    
    # Verify status changed to submitted
    doc = db.find_one({"_id": doc_id})
    assert doc["status"] == "submitted"
    
    # Simulate analysis failure
    db.update_one(
        {"_id": doc_id},
        {"$set": {"status": "failed"}}
    )
    
    # Should be able to restart
    response = await async_client.post(f"/documents/{doc_id}/analysis/")
    assert response.status_code == 201 """