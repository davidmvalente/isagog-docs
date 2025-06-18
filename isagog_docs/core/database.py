"""
app/core/database.py

Manages the asynchronous MongoDB connection using Motor.
"""

from pymongo import AsyncMongoClient
from pymongo.database import Database
from pymongo.collection import Collection
import logging

from isagog_docs.core.config import settings

# Global client and database instances
client: AsyncMongoClient = None
db: Database = None

logger = logging.getLogger(__name__)

async def connect_to_mongo():
    """
    Initializes the asynchronous MongoDB client and database instance.
    This function should be called during application startup.
    """
    global client, db
    try:
        # Connect to MongoDB using the connection string from settings
        # Use standard UUID representation for _id
        client = AsyncMongoClient(settings.MONGO_URI, uuidRepresentation='standard')
        # Select the database specified in settings
        db = client[settings.MONGO_DB]
        
        # Ping the database to verify connection
        await db.command('ping')
        logging.debug("Connected to MongoDB successfully!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        # Re-raise the exception to prevent the application from starting
        raise

async def close_mongo_connection():
    """
    Closes the asynchronous MongoDB client connection.
    This function should be called during application shutdown.
    """
    global client
    if client:
        await client.close()
        logger.info("Closed MongoDB connection.")

def get_database() -> Database:
    """
    Returns the MongoDB database instance.
    Raises an error if the database connection has not been established.
    """
    if db is None:
        raise RuntimeError("MongoDB database not connected. Call connect_to_mongo() first.")
    return db

def get_documents_collection() -> Collection:
    """
    Returns the 'documents' collection from the MongoDB database.
    """
    return get_database().get_collection(settings.MONGO_COLLECTION)

def get_analysis_collection() -> Collection:
    """
    Returns the 'analysis' collection from the MongoDB database, 
    which is the same collection of the documents.
    """
    return get_database().get_collection(settings.MONGO_COLLECTION)
