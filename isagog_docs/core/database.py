"""
app/core/database.py

Manages the asynchronous MongoDB connection using Motor.
"""

from pymongo import AsyncMongoClient
from pymongo.database import Database
from pymongo.collection import Collection
import logging

# Global client and database instances
client: AsyncMongoClient = None
db: Database = None

logger = logging.getLogger(__name__)

class MongoDB():
    def __init__(self, client: AsyncMongoClient, db: Database):
        self.client = client
        self.db = db
        self.collection = db.get_collection(settings.MONGO_COLLECTION)

    async def connect(self, mongo_uri: str, mongo_db: str):
        """
        Initializes the asynchronous MongoDB client and database instance.
        This function should be called during application startup.
        """
        try:
            # Connect to MongoDB using the connection string from settings
            # Use standard UUID representation for _id
            self.client = AsyncMongoClient(mongo_uri, uuidRepresentation='standard')
            # Select the database specified in settings
            self.db = client[mongo_db]
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
