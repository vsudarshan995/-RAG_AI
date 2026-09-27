import os
from pathlib import Path
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from providers.ai_service import embeddings
from langchain_experimental.text_splitter import SemanticChunker

def process_document_with_semantic_chunking(
    file_path_str: str, 
    filename: str, 
    category: str, 
    doc_id: str, 
    effective_date: str, 
    effective_end_date: str,
    uploaded_by: str
) -> list[Document]:
    file_path = Path(file_path_str)
    docs = []
    
    try:
        if file_path.suffix.lower() == ".pdf":
            loader = PyMuPDFLoader(file_path_str)
            docs = loader.load()
        else:
            raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
            docs = [Document(page_content=raw_text, metadata={"source": filename})]
    except Exception as e:
        print(f"⚠️ Warning: Loader failed for {filename}, using fallback text. Error: {e}")
        docs = [Document(page_content=f"Master Policy Document: {filename}", metadata={"source": filename})]

    try:
        semantic_splitter = SemanticChunker(
            embeddings, 
            breakpoint_threshold_type="percentile"
        )
        chunks = semantic_splitter.split_documents(docs) if docs else []
    except Exception as e:
        print(f"⚠️ Semantic chunking failed, falling back to basic split: {e}")
        chunks = docs

    if not chunks:
        chunks = [Document(
            page_content=f"Master Policy Document: {filename} under category {category}", 
            metadata={
                "doc_id": doc_id,
                "source": filename,
                "document_category": category,
                "effective_date": effective_date,
                "effective_end_date": effective_end_date,
                "uploaded_by": uploaded_by
            }
        )]

    for chunk in chunks:
        chunk.metadata.update({
            "doc_id": doc_id,
            "source": filename,
            "document_category": category,
            "effective_date": effective_date,
            "effective_end_date": effective_end_date,
            "uploaded_by": uploaded_by,
            "source_type": "Policy"
        })

    return chunks