import pytest
from httpx import AsyncClient
from uuid import UUID, uuid4
from unittest.mock import AsyncMock
from fastapi import status

# Struttura base dei test per gli endpoints di analisi
# Deprecato, utilizzare api/test_analysis.py

@pytest.mark.anyio
class TestAnalysisEndpoints:
    async def test_start_analysis_valid_document(
        self, 
        async_client: AsyncClient,
        sample_document_id: UUID
    ):
        """Test avvio analisi per documento esistente"""
        response = await async_client.post(
            f"/documents/{sample_document_id}/analysis/"
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "status" in response_data
        assert "results" in response_data
        assert "document_id" in response_data
        assert response_data["document_id"] == str(sample_document_id)

    async def test_start_analysis_invalid_document(
        self, 
        async_client: AsyncClient
    ):
        """Test avvio analisi per documento inesistente"""
        invalid_id = uuid4()
        response = await async_client.post(
            f"/documents/{invalid_id}/analysis/"
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "detail" in response.json()

    async def test_get_analysis_valid(
        self, 
        async_client: AsyncClient, 
        sample_analysis_data: dict
    ):
        """Test recupero analisi esistente"""
        document_id = sample_analysis_data["document_id"]
        response = await async_client.get(
            f"/documents/{document_id}/analysis/"
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["document_id"] == str(document_id)
        assert response_data["status"] == sample_analysis_data["status"]

    async def test_get_analysis_not_found(
        self, 
        async_client: AsyncClient, 
        sample_document_id: UUID
    ):
        """Test recupero analisi non esistente"""
        response = await async_client.get(
            f"/documents/{sample_document_id}/analysis/"
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_commit_analysis_valid(
        self, 
        async_client: AsyncClient, 
        sample_analysis_data: dict
    ):
        """Test commit di un'analisi esistente"""
        document_id = sample_analysis_data["document_id"]
        commit_payload = {
            "status": "approved",
            "feedback": "Looks good",
            "notes": "Additional notes"
        }
        
        response = await async_client.put(
            f"/documents/{document_id}/analysis/",
            json=commit_payload
        )
        
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["status"] == "approved"
        assert response_data["feedback"] == "Looks good"

    async def test_commit_analysis_invalid_status(
        self, 
        async_client: AsyncClient, 
        sample_analysis_data: dict
    ):
        """Test commit con stato non valido"""
        document_id = sample_analysis_data["document_id"]
        commit_payload = {
            "status": "invalid_status",
            "feedback": "Invalid status test"
        }
        
        response = await async_client.put(
            f"/documents/{document_id}/analysis/",
            json=commit_payload
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_commit_analysis_not_found(
        self, 
        async_client: AsyncClient, 
        sample_document_id: UUID
    ):
        """Test commit per analisi inesistente"""
        commit_payload = {
            "status": "approved",
            "feedback": "Trying to commit non-existing analysis"
        }
        
        response = await async_client.put(
            f"/documents/{sample_document_id}/analysis/",
            json=commit_payload
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Fixture per documento esistente (da riutilizzare dai test dei documenti)
    @pytest.fixture
    async def sample_document_id(self, async_client: AsyncClient) -> UUID:
        """Crea un documento di test e restituisce il suo ID"""
        test_file = ("sample.pdf", b"sample content", "application/pdf")
        payload = {
            "title": "Sample Document",
            "author": "Sample Author",
            "tags": "sample_tag"
        }
        response = await async_client.post("/documents/", data=payload, files={"file": test_file})
        return UUID(response.json()["id"])

    # Fixture per analisi esistente
    @pytest.fixture
    async def sample_analysis_data(self, async_client: AsyncClient, sample_document_id: UUID) -> dict:
        """Crea un'analisi di test e restituisce i suoi dati"""
        response = await async_client.post(
            f"/documents/{sample_document_id}/analysis/"
        )
        return response.json()