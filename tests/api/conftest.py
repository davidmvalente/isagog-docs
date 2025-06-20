import pytest
from pymongo import MongoClient
from isagog_docs.main import app
from httpx import AsyncClient
from isagog_docs.core.config import Config

settings = Config()

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Clean test collection before/after all tests"""
    client = MongoClient(settings.MONGO_URI)
    database = client.get_database(settings.MONGO_DB)
    if settings.MONGO_COLLECTION not in database.list_collection_names():
        database.create_collection(settings.MONGO_COLLECTION)
    # Clean the collection before tests
    collection = database[settings.MONGO_COLLECTION]
    collection.delete_many({})
    yield
    collection.delete_many({})

@pytest.fixture
async def async_client():
    """Async test client fixture"""
    async with AsyncClient(app=app, 
                           base_url="http://localhost:8000") as ac:
        yield ac

@pytest.fixture
def db():
    """Database connection fixture"""
    client = MongoClient(settings.MONGO_URI)
    database = client.get_database(settings.MONGO_DB)
    if settings.MONGO_COLLECTION not in database.list_collection_names():
        database.create_collection(settings.MONGO_COLLECTION)
    return database[settings.MONGO_COLLECTION]