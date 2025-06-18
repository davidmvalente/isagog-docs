import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import uuid
from httpx import AsyncClient, ASGITransport

from isagog_docs.main import app
from isagog_docs.services import analysis as analysis_service
from isagog_docs.core.config import settings

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:16001"
    ) as ac:
        yield ac

@pytest.fixture
def mock_db():
    """Mock MongoDB connection"""
    with patch('isagog_docs.services.analysis.get_database') as mock:
        yield mock

class TestAnalysisStart:
    @pytest.mark.anyio
    async def test_start_analysis_nonexistent_document(self, mock_db, async_client):
        """Test starting analysis for non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.post(f"/documents/{doc_id}/analysis/")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_start_analysis_already_exists(self, mock_db, async_client):
        """Test starting analysis when it already exists"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists
            {"document_id": doc_id, "status": "completed"}  # Analysis exists
        ]
        response = await async_client.post(f"/documents/{doc_id}/analysis/")
        assert response.status_code == 409

    @pytest.mark.anyio
    async def test_concurrent_analysis_start(self, mock_db, async_client):
        """Test starting analysis concurrently for same document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists
            None,  # No analysis first time
            {"document_id": doc_id, "status": "in_progress"}  # Analysis in progress second time
        ]
        
        responses = await asyncio.gather(
            async_client.post(f"/documents/{doc_id}/analysis/"),
            async_client.post(f"/documents/{doc_id}/analysis/")
        )
        assert any(r.status_code == 409 for r in responses)

    @pytest.mark.anyio
    async def test_analysis_document_deleted(self, mock_db, async_client):
        """Test document deletion while analysis in progress"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists initially
            None  # Document deleted during analysis
        ]
        
        analysis_task = async_client.post(f"/documents/{doc_id}/analysis/")
        delete_task = async_client.delete(f"/documents/{doc_id}")
        
        responses = await asyncio.gather(analysis_task, delete_task)
        assert any(r.status_code in [404, 409] for r in responses)

class TestAnalysisRetrieval:
    @pytest.mark.anyio
    async def test_get_analysis_nonexistent_document(self, mock_db, async_client):
        """Test getting analysis for non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.get(f"/documents/{doc_id}/analysis/")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_analysis_in_progress(self, mock_db, async_client):
        """Test getting analysis that is still in progress"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists
            {"document_id": doc_id, "status": "in_progress"}  # Analysis in progress
        ]
        response = await async_client.get(f"/documents/{doc_id}/analysis/")
        assert response.status_code == 202
        assert response.json()["status"] == "in_progress"

class TestAnalysisCommit:
    @pytest.mark.anyio
    async def test_commit_analysis_nonexistent_document(self, mock_db, async_client):
        """Test committing analysis for non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.put(
            f"/documents/{doc_id}/analysis/",
            json={"status": "completed", "result": {}}
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_commit_nonexistent_analysis(self, mock_db, async_client):
        """Test committing non-existing analysis"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists
            None  # Analysis doesn't exist
        ]
        response = await async_client.put(
            f"/documents/{doc_id}/analysis/",
            json={"status": "completed", "result": {}}
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_commit_analysis_in_progress(self, mock_db, async_client):
        """Test committing analysis that is still in progress"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.side_effect = [
            {"_id": doc_id},  # Document exists
            {"document_id": doc_id, "status": "in_progress"}  # Analysis in progress
        ]
        response = await async_client.put(
            f"/documents/{doc_id}/analysis/",
            json={"status": "completed", "result": {}}
        )
        assert response.status_code == 409