import os
import time
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

# Modular Imports
from providers.ai_service import policy_db, claims_db, embeddings, llm
from providers.logging import logger
from config import config #

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_experimental.text_splitter import SemanticChunker

class IngestionHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(
            patterns=["*.pdf"],
            ignore_patterns=["*\\processed\\*", "*/processed/*", "*.ingesting"],
            ignore_directories=True
        )
        self.processed_cache = {}
        self.semantic_splitter = SemanticChunker(
            embeddings, 
            breakpoint_threshold_type="percentile" 
        )
        logger.info("Handler initialized with Semantic Chunking.")

    def on_created(self, event): self.handle_event(event)
    def on_modified(self, event): self.handle_event(event)

    def handle_event(self, event):
        # Debounce using settings from config.py
        now = time.time()
        if event.src_path in self.processed_cache and \
           now - self.processed_cache[event.src_path] < config.DEBOUNCE_SECONDS: 
            return 
            
        self.processed_cache[event.src_path] = now
        
        # Guard against Windows "ghost" events
        if not os.path.exists(event.src_path):
            return

        logger.info(f"File detected: {os.path.basename(event.src_path)}")
        self.process_pdf(event.src_path)

    def classify_claim_type(self, sample_text):
        try:
            policy_info = policy_db.similarity_search("Claim categories", k=3)
            context = "\n".join([d.page_content for d in policy_info])
            prompt = f"Context: {context}\n\nClaim: {sample_text}\n\nOutput ONLY the category name:"
            return llm.invoke(prompt).strip()
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return "General"

    def wait_for_file_release(self, file_path):
        """Uses config retries. Checks lock by attempting a write-access open."""
        for i in range(config.FILE_RETRIES):
            try:
                # Better than rename for checking Windows locks
                with open(file_path, 'ab'):
                    pass
                return True
            except (OSError, IOError):
                time.sleep(config.FILE_DELAY)
        return False

    def process_pdf(self, file_path):
        filename = os.path.basename(file_path)
        if not self.wait_for_file_release(file_path):
            logger.error(f"Could not access {filename}. File is locked.")
            return

        temp_path = file_path + ".ingesting"
        try:
            os.rename(file_path, temp_path)
            
            parts = os.path.normpath(file_path).split(os.sep)
            is_claim = "claims" in parts
            
            loader = PyMuPDFLoader(temp_path)
            docs = loader.load()
            
            logger.info(f"Splitting semantically: {filename}")
            chunks = self.semantic_splitter.split_documents(docs)
            
            if is_claim:
                category = self.classify_claim_type(docs[0].page_content[:1500] if docs else "")
            else:
                category = parts[-3] if len(parts) > 3 else "General"
            
            meta_data = {
                "source_type": "Claim" if is_claim else "Policy",
                "document_category": category,
                "client_id": parts[-3] if is_claim else "Company",
                "submission_date": parts[-2] if is_claim else "N/A",
                "chunk_method": "semantic"
            }

            for chunk in chunks: 
                chunk.metadata.update(meta_data)
            
            db = claims_db if is_claim else policy_db
            db.add_documents(chunks)
            
            # Use hardcoded storage path from config
            processed_dir = os.path.join(os.path.dirname(file_path), "processed")
            os.makedirs(processed_dir, exist_ok=True)
            
            dest_path = os.path.join(processed_dir, filename)
            if os.path.exists(dest_path):
                os.remove(dest_path) # Prevent shutil errors on overwrite
                
            shutil.move(temp_path, dest_path)
            logger.info(f"Successfully indexed chunks for: {filename}")
            
        except Exception as e: 
            logger.error(f"Error processing {filename}: {str(e)}")
            if os.path.exists(temp_path): 
                try: os.rename(temp_path, file_path)
                except: pass

if __name__ == "__main__":
    # Ensure watch path is pulled from config.py hardcoded setting
    WATCH_PATH = config.STORAGE_PATH
    os.makedirs(WATCH_PATH, exist_ok=True)
    
    observer = Observer()
    observer.schedule(IngestionHandler(), path=WATCH_PATH, recursive=True)
    logger.info(f"Processor monitoring: {WATCH_PATH}")
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: 
        observer.stop()
    observer.join()