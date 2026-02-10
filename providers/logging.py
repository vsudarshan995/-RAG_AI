import functools
import logging
import sys
from datetime import datetime
import config # Import the central config

def setup_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Pulling path from config.py
        file_h = logging.FileHandler(config.config.LOG_FILE, encoding='utf-8')
        file_h.setFormatter(formatter)
        
        stream_h = logging.StreamHandler(sys.stdout)
        stream_h.setFormatter(formatter)
        
        logger.addHandler(file_h)
        logger.addHandler(stream_h)
    return logger

logger = setup_logger("InsuranceRAG")

def audit_step(node_name: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(state, *args, **kwargs):
            # Local import to prevent circular dependency
            from providers.ai_service import evaluations_db, instance_log
            
            # Single-Record Instance Update (Upsert)
            if node_name.lower() == "initialization":
                instance_log.add_texts(
                    texts=[f"Evaluation started for Client: {state['client_id']}"],
                    metadatas=[{"instance_id": state["instance_id"], "status": "STARTED"}],
                    ids=[state["instance_id"]]
                )

            # Audit Trail
            evaluations_db.add_texts(
                texts=[f"Started {node_name}"],
                metadatas=[{"instance_id": state["instance_id"], "status": f"{node_name}_running"}]
            )
            
            result = func(state, *args, **kwargs)
            
            evaluations_db.add_texts(
                texts=[f"Finished {node_name}"],
                metadatas=[{"instance_id": state["instance_id"], "status": f"{node_name}_done"}]
            )
            return result
        return wrapper
    return decorator