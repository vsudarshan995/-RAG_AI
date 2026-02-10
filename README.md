InsuranceRAG: Multi-Agent Audit Monitor
InsuranceRAG is a production-grade, multi-agent AI system designed to automate insurance claim investigations and compliance auditing. By leveraging stateful LangGraph orchestration, the system coordinates specialized agents to analyze policy coverage, investigate claim history, and evaluate regulatory compliance.

🛡️ Key Features
Multi-Agent Orchestration: Utilizes a stateful graph to manage complex workflows across specialized nodes including Initialization, Policy Selection, History Investigation, Compliance Evaluation, and Verdict Orchestration.

Asynchronous Processing: Features a FastAPI backend that triggers long-running investigations as background tasks, ensuring the API remains responsive while providing tracking via unique instance IDs.

Intelligent RAG (Retrieval-Augmented Generation):

Dual-Collection Architecture: Separates Master Policies and Client Claims within ChromaDB for precise context retrieval.

Semantic Chunking: Documents are split based on semantic meaning rather than arbitrary character counts to improve the quality of retrieved context.

Real-time Monitoring Dashboard: A built-in Streamlit dashboard allows auditors to monitor agent "thought processes," view detailed step-by-step logs, and track the status of investigation instances.

Automated Ingestion: Employs a file-system observer to automatically detect, process, and index new PDF policies or claims added to monitored storage folders.

🏗️ Architecture
The solution is built with a modular structure for high maintainability:

core/graph.py: Defines the agentic workflow and state management using LangGraph.

nodes/: Contains individual specialized logic for compliance checks, history investigation, and final orchestration.

providers/: Infrastructure layers for AI services (LLM/Embeddings), centralized logging, and a prompt registry.

processor.py: Handles the automated background document ingestion and semantic splitting pipeline.

config.py: Centralized configuration for paths, model settings, and database collection names.

🚀 Getting Started
Prerequisites
Python 3.10+

Ollama (configured with llama3:8b-instruct-q2_K)

Local directory for database storage (configured in config.py)

Installation
Install dependencies:

Bash
pip install -r requirements.txt
Configuration: Update your base paths and model settings in config.py. The default production path is set to D:\pY\InsuranceRAG.

Running the System
Start the API:

Bash
uvicorn main:app --reload
Start the Document Processor:

Bash
python processor.py
Launch the Dashboard:

Bash
streamlit run dashboard.py
🛠️ API Endpoints
POST /ask/investigate/async: Trigger a new multi-agent claim investigation.

POST /upload/policy: Upload a new insurance policy to a specific category.

POST /upload/claim/{client_id}/{submission_type}: Submit a new claim for investigation.

DELETE /clear-all: Wipe all database collections and physical storage for a clean state.

📊 Monitoring
The system captures an Audit Trail at every node execution via a custom decorator, providing full transparency into how the final APPROVED or DENIED verdict was reached by the agents. Statuses and logs are stored in the evaluation_audit_log and instance_log collections for review in the dashboard
