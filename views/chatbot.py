import streamlit as st
import requests

st.title("🤖 Policy Knowledgebase Chatbot")
st.caption("Interactive Retrieval-Augmented Generation (RAG) assistant for quality testing policy embeddings and answers.")
st.divider()

# Initialize chat history in session state if not present
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input query
if prompt := st.chat_input("Ask a question about your uploaded policies..."):
    # Append and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 1. Quick UI-side intent check for dynamic loading states
    q_lower = prompt.lower().strip()
    greetings = ["hi", "hello", "hey", "thanks", "how are you", "greetings", "good morning"]
    is_greeting = any(q_lower == g or q_lower.startswith(f"{g} ") for g in greetings)
    
    is_summary = any(w in q_lower for w in ["consolidate", "summary", "summarize", "overview"])

    # 2. Dynamically set the loading text
    if is_greeting:
        loading_text = "Saying hello..."
    elif is_summary:
        loading_text = "Consolidating policy documents..."
    else:
        loading_text = "Searching policy vector embeddings and generating answer..."

    # 3. Query backend RAG endpoint with smart spinner
    with st.chat_message("assistant"):
        with st.spinner(loading_text):
            try:
                payload = {"question": prompt}
                res = requests.post("http://localhost:8000/chatbot/query", json=payload)
                
                if res.status_code == 200:
                    data = res.json()
                    answer = data.get("answer", "No response generated.")
                    sources = data.get("sources", [])
                    
                    # Append source citations if available
                    if sources:
                        source_str = ", ".join([f"`{src}`" for src in sources])
                        response_text = f"{answer}\n\n**Sources:** {source_str}"
                    else:
                        response_text = answer
                else:
                    response_text = "⚠️ Failed to retrieve a response from the backend RAG service."
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
            except Exception as ex:
                error_msg = f"Connection error: {ex}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})