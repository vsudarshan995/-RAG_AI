from datetime import datetime
from langchain_core.output_parsers import StrOutputParser

from providers.ai_service import policy_vr_db, policy_registry_db, reasoning_llm
from providers.prompts import rag_refinement_prompt

def parse_iso_date(date_str: str) -> datetime.date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return datetime.min.date()

def get_filename_from_registry(docid: str) -> str:
    try:
        registry_data = policy_registry_db.get(ids=[str(docid)])
        if registry_data and registry_data.get("metadatas"):
            return registry_data["metadatas"][0].get("filename", "Unknown Policy")
    except Exception:
        pass
    return "Unknown Policy"

def process_rag_query(query: str, category_filter: str = "All") -> dict:
    search_kwargs = {"k": 6}
    if category_filter and category_filter != "All":
        search_kwargs["filter"] = {"document_category": category_filter}

    docs = policy_vr_db.similarity_search(query, **search_kwargs)

    if not docs:
        return {
            "answer": "No relevant policy documents or clauses were found matching your criteria.",
            "sources": []
        }

    valid_docs = []
    current_date = datetime.now().date()

    for doc in docs:
        effective_start = parse_iso_date(doc.metadata.get("effective_date", "1900-01-01"))
        effective_end = parse_iso_date(doc.metadata.get("effective_end_date", "2100-01-01"))

        if effective_start <= current_date <= effective_end:
            valid_docs.append(doc)

    selected_docs = valid_docs if valid_docs else docs

    context_str = "\n\n---\n\n".join([
        f"Source: {d.metadata.get('filename', 'Doc')} (Clause ID: {d.metadata.get('docid', 'N/A')})\n{d.page_content}"
        for d in selected_docs
    ])

    chain = rag_refinement_prompt | reasoning_llm | StrOutputParser()
    answer = chain.invoke({"context": context_str, "question": query})

    sources = [
        {
            "filename": d.metadata.get("filename", get_filename_from_registry(d.metadata.get("docid"))),
            "category": d.metadata.get("document_category", "General"),
            "effective_date": d.metadata.get("effective_date", "N/A"),
            "effective_end_date": d.metadata.get("effective_end_date", "N/A")
        }
        for d in selected_docs
    ]

    return {"answer": answer, "sources": sources}