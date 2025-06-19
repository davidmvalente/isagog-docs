import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import UploadFile, HTTPException
import uuid
from httpx import AsyncClient, ASGITransport

from isagog_docs.main import app

@pytest.fixture
def mock_db():
    """Mock MongoDB connection"""
    with patch('isagog_docs.core.database.get_database') as mock:
        yield mock

@pytest.fixture
def mock_fs():
    """Mock filesystem operations"""
    with patch('pathlib.Path.exists') as exists_mock:
        with patch('pathlib.Path.unlink') as unlink_mock:
            exists_mock.return_value = True
            yield exists_mock, unlink_mock

@pytest.fixture
def test_file():
    """Create a test file for uploads"""
    content = b"test content"
    return {
        "file": ("test.txt", content, "text/plain")
    }

@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost:16001"
    ) as ac:
        yield ac

class TestDocumentCreation:
    @pytest.mark.anyio
    async def test_create_document_no_file(self, mock_db, async_client):
        """Test creating document without file"""
        response = await async_client.post(
            "/documents/",
            data={"title": "Test", "author": "Test Author"}
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_create_document_invalid_filetype(self, mock_db, async_client):
        """Test creating document with invalid file type"""
        files = {
            "file": ("test.exe", b"content", "application/x-msdownload")
        }
        response = await async_client.post(
            "/documents/",
            files=files,
            data={"title": "Test", "author": "Test Author"}
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    @pytest.mark.anyio
    async def test_create_document_missing_metadata(self, mock_db, async_client, test_file):
        """Test creating document with missing required metadata"""
        response = await async_client.post(
            "/documents/",
            files=test_file,
            data={}  # Missing title and author
        )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_create_document_invalid_metadata(self, mock_db, async_client, test_file):
        """Test creating document with invalid metadata"""
        response = await async_client.post(
            "/documents/",
            files=test_file,
            data={
                "title": "a" * 1000,  # Too long
                "author": "",  # Empty
            }
        )
        assert response.status_code == 422

class TestDocumentListing:
    @pytest.mark.anyio
    async def test_list_empty_documents(self, mock_db, async_client):
        """Test listing documents when database is empty"""
        mock_db.find.return_value = []
        response = await async_client.get("/documents/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.anyio
    async def test_list_with_invalid_document(self, mock_db, async_client):
        """Test listing when database contains invalid document"""
        mock_db.find.return_value = [{"_id": "invalid", "metadata": None}]
        response = await async_client.get("/documents/")
        assert response.status_code == 500

    @pytest.mark.anyio
    async def test_list_concurrent_modification(self, mock_db, async_client):
        """Test listing while concurrent modifications are happening"""
        # Simulate concurrent operations
        responses = await asyncio.gather(
            async_client.get("/documents/"),
            async_client.post(
                "/documents/",
                files={"file": ("test.txt", b"content", "text/plain")},
                data={"title": "Test", "author": "Author"}
            ),
            async_client.get("/documents/")
        )
        assert all(response.status_code in [200, 201] for response in responses)

class TestDocumentRetrieval:
    @pytest.mark.anyio
    async def test_get_nonexistent_document(self, mock_db, async_client):
        """Test getting non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.get(f"/documents/{doc_id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_deleted_document(self, mock_db, async_client):
        """Test getting a deleted document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"deleted": True}
        response = await async_client.get(f"/documents/{doc_id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_get_document_bad_metadata(self, mock_db, async_client):
        """Test getting document with corrupted metadata"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"_id": doc_id, "metadata": None}
        response = await async_client.get(f"/documents/{doc_id}")
        assert response.status_code == 500

class TestDocumentDownload:
    @pytest.mark.anyio
    async def test_download_nonexistent_document(self, mock_db, mock_fs, async_client):
        """Test downloading non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.get(f"/documents/{doc_id}/download")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_download_deleted_document(self, mock_db, mock_fs, async_client):
        """Test downloading deleted document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"deleted": True}
        response = await async_client.get(f"/documents/{doc_id}/download")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_download_missing_file(self, mock_db, mock_fs, async_client):
        """Test downloading when file is missing from filesystem"""
        exists_mock, _ = mock_fs
        exists_mock.return_value = False
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {
            "_id": doc_id,
            "file_path": "test.txt"
        }
        response = await async_client.get(f"/documents/{doc_id}/download")
        assert response.status_code == 404

class TestDocumentUpdate:
    @pytest.mark.anyio
    async def test_update_nonexistent_document(self, mock_db, async_client):
        """Test updating non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.put(
            f"/documents/{doc_id}",
            json={"title": "Updated"}
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_update_deleted_document(self, mock_db, async_client):
        """Test updating deleted document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"deleted": True}
        response = await async_client.put(
            f"/documents/{doc_id}",
            json={"title": "Updated"}
        )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_update_invalid_metadata(self, mock_db, async_client):
        """Test updating with invalid metadata"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"_id": doc_id}
        response = await async_client.put(
            f"/documents/{doc_id}",
            json={"title": "a" * 1000}  # Too long
        )
        assert response.status_code == 422

class TestDocumentDeletion:
    @pytest.mark.anyio
    async def test_delete_nonexistent_document(self, mock_db, async_client):
        """Test deleting non-existing document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = None
        response = await async_client.delete(f"/documents/{doc_id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_already_deleted(self, mock_db, async_client):
        """Test deleting already deleted document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"deleted": True}
        response = await async_client.delete(f"/documents/{doc_id}")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_concurrent_deletion(self, mock_db, async_client):
        """Test concurrent deletion of same document"""
        doc_id = str(uuid.uuid4())
        mock_db.find_one.return_value = {"_id": doc_id}
        
        responses = await asyncio.gather(
            async_client.delete(f"/documents/{doc_id}"),
            async_client.delete(f"/documents/{doc_id}")
        )
        assert any(r.status_code == 404 for r in responses)  # At least one should fail