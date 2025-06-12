"""
Simple document processing worker
"""
import asyncio
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import uuid

from processor import DocumentProcessor
from config import Config

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class FileHandler(FileSystemEventHandler):
    def __init__(self, processor: DocumentProcessor, skip_existing: bool = False):
        self.processor = processor
        self.skip_existing = skip_existing # TODO: do we need this?

    def _process_file(self, file_path: Path):
        """Wrapper for error handling"""
        try:
            if self._is_valid_document(file_path):
                logger.info(f"Processing document: {file_path.name}")
                self.processor.process_document(file_path)
            else:
                logger.info(f"Skipping invalid document: {file_path.name}")
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")

    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self.skip_existing and file_path.name in self.existing_files:
            logger.debug(f"Skipping existing file: {file_path.name}")
            return
            
        logger.info(f"Detected new document: {file_path.name}")
        self._process_file(file_path)

    # def on_modified(self, event):
    #     """Handle file modifications"""
    #     if event.is_directory:
    #         return

    #     file_path = Path(event.src_path)
    #     if self.skip_existing and file_path.name in self.existing_files:
    #         logger.debug(f"Skipping modification of existing file: {file_path.name}")
    #         return
            
    #     logger.info(f"Detected modified document: {file_path.name}")
    #     self._process_file(file_path)

    def _is_valid_document(self, file_path: Path) -> bool:
        """Validate document filename and extension"""
        logger.debug(f"Validating document: {file_path.name}")
        try:
            # Check if file is still present (might have been deleted)
            if not file_path.exists():
                logger.debug(f"File no longer exists: {file_path.name}")
                return False

            # Check UUID filename
            uuid.UUID(file_path.stem)
            
            # Check valid extension
            valid_extensions = {'.txt', '.pdf', '.docx', '.csv'}
            ext = file_path.suffix.lower()
            if ext not in valid_extensions:
                logger.debug(f"Invalid extension {ext} for file: {file_path.name}")
                return False
                
            return True
        
        except ValueError as e:
            logger.debug(f"Invalid UUID in filename {file_path.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating {file_path.name}: {e}")
            return False
        
async def main():
    logger.info("Starting document processor service (new files only mode)")
    
    config = Config()
    processor = DocumentProcessor(config)
    
    # Initialize upload directory
    uploads_dir = Path(config.uploads_dir)
    logger.info(f"Initializing uploads directory: {uploads_dir}")
    
    try:
        uploads_dir.mkdir(exist_ok=True)
        logger.debug(f"Directory {uploads_dir} ready")
    except Exception as e:
        logger.error(f"Failed to initialize uploads directory: {e}")
        raise
    
    # Start monitoring for new files only
    logger.info("Initializing file monitoring for new files only")
    try:
        handler = FileHandler(processor)
        observer = Observer()
        observer.schedule(handler, str(uploads_dir), recursive=False)
        observer.start()
        logger.info(f"Now monitoring for new files in: {uploads_dir}")
        
        # Main loop
        try:
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            observer.stop()
            logger.info("Stopping file observer")

        observer.join()
        logger.info("File observer stopped successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize file monitoring: {e}")
        raise
    

if __name__ == "__main__":
    asyncio.run(main())
    