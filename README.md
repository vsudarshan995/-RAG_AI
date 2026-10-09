# Enterprise Insurance RAG & Policy Audit System

An advanced, locally-hosted Retrieval-Augmented Generation (RAG) and workflow orchestration platform built specifically for enterprise insurance policy management, auditing, and compliance. Powered by **LangGraph**, **ChromaDB**, **Ollama**, and **FastAPI**, with an interactive **Streamlit** frontend.

---

## 🏗️ System Architecture & Directory Structure

```text
RAG_AI/
│
├── core/                  # Workflow orchestration graph definitions
│   └── graph.py           # LangGraph multi-agent workflow state and transitions
├── nodes/                 # Specialized worker nodes for agentic workflows
│   ├── compliance.py      # Regulatory rule-checking and validation nodes
│   ├── investigator.py    # Deep document analysis and clause cross-referencing
│   └── orchestrator.py    # Master router and intent classification coordinator
├── providers/             # Backend service integrations and utilities
│   ├── ai_service.py      # Dual-model local Ollama & ChromaDB client initialization
│   ├── chunker.py         # Semantic text chunking and document preprocessing
│   ├── logging.py         # Unified system event and debugging logs
│   ├── prompts.py         # Centralized prompt engineering templates
│   └── rag_service.py     # Graph execution wrappers and retrieval pipelines
├── views/                 # Streamlit multi-page frontend views
│   ├── chatbot.py         # Interactive RAG chat interface with dynamic loading states
│   ├── clients.py         # Client record and profile management
│   ├── dashboard.py       # Executive metrics and analytics overview
│   ├── evaluation.py      # System performance and output audit logging
│   ├── hitl_queue.py      # Human-in-the-Loop review and approval tasks
│   ├── policies.py        # Policy document ingestion and metadata management
│   └── system_admin.py    # Database reset, collection registry, and server settings
├── notebooks/             # Jupyter Notebooks for testing and data inspection
│   ├── data_inspector.py  # Vector database and metadata health inspection
│   └── policy_audit.ipynb # Automated policy compliance auditing notebooks
├── app.py                 # Streamlit multi-page entry point launcher
├── main.py                # FastAPI backend server application entry point
├── config.py              # Centralized environment configuration and paths
├── langgraph.json         # LangGraph Studio configuration schema
└── requirements.txt       # Python package dependencies


🚀 Key Features
Local Multi-Model LLM Cascade: Optimized for consumer hardware (configured for an Intel i7 CPU / 16GB RAM setup) using Ollama (OLLAMA_MAX_LOADED_MODELS=2) to run smollm2:360m for instant intent routing and llama3.2:1b for deep document reasoning.

LangGraph Orchestration: Stateful multi-agent workflows managing routing, intent extraction, category filtering, and temporal validity date-overlap matching.

Relational Filename Lookup: Seamless mapping between vector chunk metadata (docid) and the master policy_registry collection to ensure accurate file source citations.

Human-in-the-Loop (HITL) Queue: Built-in review workflows allowing compliance officers to inspect, approve, or reject automated outputs.

Modular Streamlit Dashboard: Comprehensive views covering interactive chat, client administration, policy management, audit logs, and system configuration.
