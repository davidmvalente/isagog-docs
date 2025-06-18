import pytest
from httpx import AsyncClient
from uuid import UUID, uuid4
#from pathlib import Path
from fastapi import status

from isagog_docs.core.config import settings

# Struttura base dei test per gli endpoints dei documenti
# Deprecato, utilizzare api/test_documents.py

@pytest.mark.anyio
class TestDocumentEndpoints:
    
    """
    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path):
        # Setup per sovrascrivere la directory di upload durante i test
        self.original_upload_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = str(tmp_path / "test_uploads")
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
       """
        
    async def test_create_document(self, async_client: AsyncClient):
        # TODO: Mock del servizio o test end-to-end
        test_file = ("test.pdf", b"dummy content", "application/pdf")
        payload = {
            "title": "Test Document",
            "author": "Test Author",
            "description": "Test Description",
            "tags": "tag1,tag2"
        }
        
        files = {"file": test_file}
        response = await async_client.post("/documents/", data=payload, files=files)
        
        assert response.status_code == status.HTTP_201_CREATED
        # Verifica struttura della risposta
        assert "id" in response.json()
        # TODO: Verifica aggiuntiva del file salvato

    async def test_list_documents(self, async_client: AsyncClient):
        response = await async_client.get("/documents/")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
        # TODO: Verifica dati specifici dopo creazione test fixture

    async def test_get_document_valid_id(self, async_client: AsyncClient, sample_document_id: UUID):
        response = await async_client.get(f"/documents/{sample_document_id}")
        assert response.status_code == status.HTTP_200_OK
        document = response.json()
        assert document["id"] == str(sample_document_id)
        # TODO: Verifica campi aggiuntivi

    async def test_get_document_invalid_id(self, async_client: AsyncClient):
        invalid_id = uuid4()
        response = await async_client.get(f"/documents/{invalid_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_download_document(self, async_client: AsyncClient, sample_document_id: UUID):
        response = await async_client.get(f"/documents/{sample_document_id}/download")
        assert response.status_code == status.HTTP_200_OK
        assert "content-disposition" in response.headers
        # TODO: Verifica contenuto del file

    async def test_download_missing_file(self, async_client: AsyncClient, sample_document_id: UUID):
        # Simula file mancante eliminando il file dopo la creazione
        # TODO: Implementa la logica di setup appropriata
        response = await async_client.get(f"/documents/{sample_document_id}/download")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_document(self, async_client: AsyncClient, sample_document_id: UUID):
        update_payload = {
            "title": "Updated Title",
            "author": "Updated Author",
            "description": "Updated description",
            "tags": "new_tag"
        }
        response = await async_client.put(
            f"/documents/{sample_document_id}",
            json=update_payload
        )
        assert response.status_code == status.HTTP_200_OK
        updated_doc = response.json()
        assert updated_doc["title"] == "Updated Title"
        # TODO: Verifica altri campi aggiornati

    async def test_delete_document(self, async_client: AsyncClient, sample_document_id: UUID):
        response = await async_client.delete(f"/documents/{sample_document_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verifica che il documento sia stato rimosso
        get_response = await async_client.get(f"/documents/{sample_document_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    # Fixture per documenti pre-esistenti
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