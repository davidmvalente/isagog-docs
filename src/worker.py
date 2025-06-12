"""
Simple document processing worker
"""
import asyncio
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from processor import DocumentProcessor
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileHandler(FileSystemEventHandler):
    def __init__(self, processor: DocumentProcessor):
        self.processor = processor
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if self._is_valid_document(file_path):
            logger.info(f"New document: {file_path}")
            asyncio.create_task(self.processor.process_document(file_path))
    
    def _is_valid_document(self, file_path: Path) -> bool:
        try:
            # Check UUID filename
            import uuid
            uuid.UUID(file_path.stem)
            return file_path.suffix.lower() in {'.txt', '.pdf', '.docx', '.csv'}
        except ValueError:
            return False

async def main():
    config = Config()
    processor = DocumentProcessor(config)
    
    # Process existing files
    uploads_dir = Path(config.uploads_dir)
    uploads_dir.mkdir(exist_ok=True)
    
    for file_path in uploads_dir.glob("*"):
        if file_path.is_file():
            handler = FileHandler(processor)
            if handler._is_valid_document(file_path):
                await processor.process_document(file_path)
    
    # Start monitoring
    handler = FileHandler(processor)
    observer = Observer()
    observer.schedule(handler, str(uploads_dir), recursive=False)
    observer.start()
    
    logger.info(f"Monitoring {uploads_dir}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        observer.stop()
        observer.join()

if __name__ == "__main__":
    asyncio.run(main())