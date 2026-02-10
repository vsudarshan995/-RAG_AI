import os
import time
import shutil
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

# Modular Imports
from providers.ai_service import policy_db, claims_db, embeddings, llm
from providers.logging import logger
from config import config 

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_experimental.text_splitter import SemanticChunker

class IngestionHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.processed_cache = {}
        self.semantic_splitter = SemanticChunker(
            embeddings, 
            breakpoint_threshold_type="percentile" 
        )
        logger.info("🔄 Polling Monitor Initialized. System will scan every 2 seconds.")

    def on_any_event(self, event):
        # 1. Totally ignore directory events
        if event.is_directory:
            return

        # 2. Extract and Normalize Path
        src_path = os.path.normpath(event.src_path)
        
        # 3. Filter for PDF and ignore 'processed' folders
        if not src_path.lower().endswith(".pdf") or "processed" in src_path or ".ingesting" in src_path:
            return

        self.trigger_processing(src_path)

    def trigger_processing(self, file_path):
        # Debounce: Prevent double-processing within 10 seconds
        now = time.time()
        if file_path in self.processed_cache and (now - self.processed_cache[file_path] < 10):
            return
            
        self.processed_cache[file_path] = now
        logger.info(f"📂 New file detected: {os.path.basename(file_path)}")
        self.process_pdf(file_path)

    def wait_for_file_release(self, file_path):
        """Wait for Windows to finish copying the file."""
        for i in range(config.FILE_RETRIES):
            try:
                # If we can rename it to itself, the copy/move is finished
                os.rename(file_path, file_path)
                return True
            except OSError:
                time.sleep(config.FILE_DELAY)
        return False

    def process_pdf(self, file_path):
        filename = os.path.basename(file_path)
        if not self.wait_for_file_release(file_path):
            logger.error(f"❌ File locked or incomplete: {filename}")
            return

        temp_path = file_path + ".ingesting"
        try:
            os.rename(file_path, temp_path)
            
            # Determine logic (Claim vs Policy)
            parts = os.path.normpath(file_path).split(os.sep)
            is_claim = "claims" in parts
            
            # Smart category extraction
            category = "General"
            if "policies" in parts:
                idx = parts.index("policies")
                category = parts[idx + 1] if len(parts) > idx + 1 else "General"
            
            loader = PyMuPDFLoader(temp_path)
            docs = loader.load()
            
            logger.info(f"🧠 Semantic Chunking: {filename}")
            chunks = self.semantic_splitter.split_documents(docs)
            
            # Classification for claims
            if is_claim:
                category = self.classify_claim_type(docs[0].page_content[:1500] if docs else "")

            for chunk in chunks: 
                chunk.metadata.update({
                    "source": filename,
                    "document_category": category,
                    "source_type": "Claim" if is_claim else "Policy"
                })
            
            db = claims_db if is_claim else policy_db
            db.add_documents(chunks)
            
            # Move to processed
            processed_dir = os.path.join(os.path.dirname(file_path), "processed")
            os.makedirs(processed_dir, exist_ok=True)
            shutil.move(temp_path, os.path.join(processed_dir, filename))
            
            logger.info(f"✅ Indexed: {filename} into {category}")
            
        except Exception as e: 
            logger.error(f"💥 Error: {str(e)}")
            if os.path.exists(temp_path):
                try: os.rename(temp_path, file_path)
                except: pass

    def classify_claim_type(self, text):
        try:
            return llm.invoke(f"Extract insurance category (Travel/Medical/Motor) from: {text[:500]}. Return ONLY the word:").strip()
        except: return "General"

def startup_scan(handler, watch_path):
    """Scans for files that were added while the script was offline."""
    logger.info("🔍 Performing startup scan...")
    for root, dirs, files in os.walk(watch_path):
        if "processed" in root: continue
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                handler.trigger_processing(full_path)

if __name__ == "__main__":
    WATCH_PATH = os.path.normpath(config.STORAGE_PATH)
    os.makedirs(WATCH_PATH, exist_ok=True)
    
    handler = IngestionHandler()
    
    # 1. Start by scanning existing files
    startup_scan(handler, WATCH_PATH)
    
    # 2. Start the Polling Observer (Check every 2 seconds)
    observer = Observer(timeout=2)
    observer.schedule(handler, path=WATCH_PATH, recursive=True)
    logger.info(f"🚀 Monitor Active on {WATCH_PATH}")
    observer.start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()