import os
import json
from datetime import datetime
from typing import TypedDict, List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, END

# 1. Updated Imports for Multi-Model Cascade
from providers.ai_service import policy_db, fast_llm, reasoning_llm, policy_registry_db

# --- Helper: Relational Filename Lookup ---
def get_filename_from_registry(chunk_metadata: dict) -> str:
    """
    Looks up the real filename from the policy_registry using the docid.
    Falls back to chunk metadata if the registry lookup fails.
    """
    docid = chunk_metadata.get("docid") or chunk_metadata.get("document_id")
    
    if docid:
        try:
            registry_data = policy_registry_db.get(ids=[str(docid)])
            if registry_data and registry_data.get("metadatas") and len(registry_data["metadatas"]) > 0:
                return registry_data["metadatas"][0].get("filename", "Unknown")
        except Exception as e:
            print(f"⚠️ Registry lookup failed for docid {docid}: {e}")

    # Fallback if docid is missing
    raw_source = chunk_metadata.get("filename") or chunk_metadata.get("source") or "Unknown"
    return os.path.basename(raw_source) if raw_source != "Unknown" else "Unknown"

# 1. Define State for the Chatbot Graph
class ChatState(TypedDict):
    question: str
    category_filter: str
    intent: dict
    answer: str
    sources: List[str]

# 2. Router Node (Uses fast_llm & Restored spelling fixes)
def router_node(state: ChatState) -> dict:
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    router_prompt = ChatPromptTemplate.from_template("""You are a strict JSON intent router for an enterprise insurance system.
Analyze the user's question and return ONLY valid JSON. Do not include markdown code blocks or explanations.

Examples:
User: "Hi there"
{"is_greeting": true, "is_summary": false, "start_date": null, "end_date": null, "category": null, "search_query": "Hi there"}

User: "consolidate the documents"
{"is_greeting": false, "is_summary": true, "start_date": null, "end_date": null, "category": null, "search_query": "policy overview summary"}

User: "summarize the content of each"
{"is_greeting": false, "is_summary": true, "start_date": null, "end_date": null, "category": null, "search_query": "policy overview summary"}

User: "What is my health deductible?"
{"is_greeting": false, "is_summary": false, "start_date": null, "end_date": null, "category": "Health", "search_query": "health deductible"}

Today's Date: {today}
User Question: {question}
""")

    try:
        chain = router_prompt | reasoning_llm | StrOutputParser()
        response = chain.invoke({"question": state["question"], "today": today_str})
        
        cleaned = response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
            
        intent = json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ Router Intent Extraction Fallback: {e}")
        q_lower = state["question"].lower()
        is_g = any(w in q_lower for w in ["hi", "hello", "hey", "thanks", "how are you", "greetings"])
        # Expanded fallback list to catch all variants
        summary_terms = ["consolidate", "summary", "summarize", "summarise", "overview", "all documents", "recap", "content of each"]
        is_s = any(w in q_lower for w in summary_terms)
        intent = {
            "is_greeting": is_g,
            "is_summary": is_s,
            "start_date": None,
            "end_date": None,
            "category": None,
            "search_query": state["question"]
        }
        
    return {"intent": intent}

# 3. Conditional Routing Logic
def decide_route(state: ChatState) -> str:
    intent = state.get("intent", {})
    if intent.get("is_greeting"):
        return "greeting_worker"
    elif intent.get("is_summary"):
        return "summary_worker"
    else:
        return "rag_worker"

# 4. Worker Nodes
# --- Greeting Worker (Uses fast_llm) ---
def greeting_worker(state: ChatState) -> dict:
    try:
        template = """You are a polite and professional enterprise insurance policy assistant. 
The user just said: "{question}"
Respond conversationally and warmly in 1-2 sentences. 
Always end your response by asking how you can help them audit, search, or review their policy documents today."""

        prompt = ChatPromptTemplate.from_template(template)
        # Assigned to SmolLM2 for instant replies
        chain = prompt | fast_llm | StrOutputParser()
        answer = chain.invoke({"question": state["question"]})
        
        return {"answer": answer, "sources": []}
    except Exception as e:
        return {"answer": "Hello! I am ready to help you search or review your insurance documents. What would you like to check?", "sources": []}

# --- Summary Worker (Uses reasoning_llm) ---
def summary_worker(state: ChatState) -> dict:
    try:
        retriever = policy_db.as_retriever(search_kwargs={"k": 3})
        docs = retriever.invoke("policy overview summary coverage terms")
        
        if not docs:
            return {"answer": "No policy documents found in the knowledgebase to consolidate or summarize.", "sources": []}
            
        sources = set()
        blocks = []
        for doc in docs:
            fn = get_filename_from_registry(doc.metadata)
            sources.add(fn)
            blocks.append(f"--- Document: {fn} ---\n{doc.page_content}")
            
        context = "\n\n".join(blocks)
        prompt = ChatPromptTemplate.from_template("""You are an expert enterprise insurance compliance assistant. Provide a clear, structured executive summary and consolidation of the following uploaded policy documents:

{context}

Executive Consolidation Summary:""")
        
        # Assigned to Llama 3.2 1B for deep reading
        chain = prompt | reasoning_llm | StrOutputParser()
        answer = chain.invoke({"context": context})
        
        return {"answer": answer, "sources": list(sources)}
    except Exception as e:
        return {"answer": f"Error generating document consolidation: {str(e)}", "sources": []}

# --- RAG Worker (Uses reasoning_llm & Restored NoneType fixes) ---
def rag_worker(state: ChatState) -> dict:
    try:
        intent = state.get("intent", {})
        question = state["question"]
        category_filter = state.get("category_filter", "All")
        
        q_start = intent.get("start_date")
        q_end = intent.get("end_date")
        extracted_cat = intent.get("category")
        
        # Restored NoneType protection
        opt_query = intent.get("search_query") or question
        
        if not q_start or not q_end:
            today = datetime.now().strftime("%Y-%m-%d")
            q_start, q_end = today, today
            
        active_cat = category_filter if (category_filter and category_filter != "All") else extracted_cat
        
        search_kwargs = {"k": 6}
        if active_cat and active_cat in ["Health", "Life", "Travel", "Commercial", "General"]:
            search_kwargs["filter"] = {"document_category": active_cat}
            
        retriever = policy_db.as_retriever(search_kwargs=search_kwargs)
        docs = retriever.invoke(opt_query)
        
        if not docs and opt_query != question:
            docs = retriever.invoke(question)
            
        if not docs:
            return {"answer": "No relevant policy documents found matching your criteria. Try broadening your question or checking your category filters.", "sources": []}
            
        # Restored NoneType protection for dates
        overlapping = []
        for doc in docs:
            p_start = doc.metadata.get("effective_date") or "2000-01-01"
            p_end = doc.metadata.get("effective_end_date") or "2099-12-31"
            if p_start <= q_end and q_start <= p_end:
                overlapping.append(doc)
                
        target_docs = overlapping if overlapping else docs[:4]
        
        sources = set()
        blocks = []
        for doc in target_docs:
            fn = get_filename_from_registry(doc.metadata)
            cat = doc.metadata.get("document_category", "General")
            eff = doc.metadata.get("effective_date", "N/A")
            end = doc.metadata.get("effective_end_date", "N/A")
            sources.add(fn)
            blocks.append(f"--- Document: {fn} [Category: {cat} | Valid: {eff} to {end}] ---\n{doc.page_content}")
            
        context = "\n\n".join(blocks)
        
        template = """You are an expert enterprise insurance compliance and policy auditing assistant. 
Answer the user's question accurately using ONLY the provided policy context below. 
Pay close attention to document categories and effective validity dates. 
If the answer cannot be found in the context, state clearly that the matching policy documents do not contain this information.

Policy Context:
{context}

Question: {question}

Answer:"""

        prompt = ChatPromptTemplate.from_template(template)
        # Assigned to Llama 3.2 1B for deep reading
        chain = prompt | reasoning_llm | StrOutputParser()
        answer = chain.invoke({"context": context, "question": question})
        
        return {"answer": answer, "sources": list(sources)}
    except Exception as e:
        return {"answer": f"Error executing RAG query: {str(e)}", "sources": []}

# 5. Assemble and Compile the LangGraph Workflow
workflow = StateGraph(ChatState)
workflow.add_node("router", router_node)
workflow.add_node("greeting_worker", greeting_worker)
workflow.add_node("summary_worker", summary_worker)
workflow.add_node("rag_worker", rag_worker)

workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router", 
    decide_route, 
    {
        "greeting_worker": "greeting_worker",
        "summary_worker": "summary_worker",
        "rag_worker": "rag_worker"
    }
)
workflow.add_edge("greeting_worker", END)
workflow.add_edge("summary_worker", END)
workflow.add_edge("rag_worker", END)

chatbot_graph = workflow.compile()

# 6. Public Interface Function for FastAPI / main.py
def process_rag_query(question: str, category_filter: str = "All") -> dict:
    try:
        initial_state = {
            "question": question,
            "category_filter": category_filter,
            "intent": {},
            "answer": "",
            "sources": []
        }
        
        final_state = chatbot_graph.invoke(initial_state)
        
        return {
            "answer": final_state.get("answer", "No response generated."),
            "sources": final_state.get("sources", [])
        }
    except Exception as e:
        print(f"❌ Chatbot Graph Execution Error: {e}")
        return {
            "answer": f"An error occurred while processing your query: {str(e)}",
            "sources": []
        }