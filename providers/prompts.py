from langchain_core.prompts import ChatPromptTemplate

# ==============================================================================
# 1. TOP-LEVEL PROMPT TEMPLATES (Imported by rag_service, nodes, etc.)
# ==============================================================================

rag_refinement_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a specialized Insurance Policy Assistant. 
Analyze the user's question using strictly the retrieved policy clauses provided in the context.

Rules:
1. Answer clearly, citing specific clauses, sections, or coverage terms when available.
2. If the context does not contain sufficient details to answer, state clearly that the requested information is not covered under the provided policy excerpts.
3. Do not assume or fabricate terms, exclusions, or financial limits outside the provided context."""
    ),
    (
        "human",
        """Context:
{context}

Question:
{question}

Provide an accurate and concise answer:"""
    )
])

compliance_evaluator_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Senior Insurance Compliance Auditor.
Audit the submitted claim against the retrieved policy clauses.

Rules:
1. Verify mandatory documentation (e.g., official police reports for motor collisions, original receipts).
2. Check for exclusions (commercial use, unlisted drivers, territorial limits).
3. If no conditions are violated, set is_compliant=true, detected_violations=[], and assigned_risk_score=0.
4. If violations exist, specify each breach with a realistic severity penalty (10-50 pts).
5. Ground all reasoning strictly in the provided policy and claim details."""
    ),
    (
        "human",
        """Retrieved Policy Context:
{policy_context}

Claim Narrative:
{claim_narrative}

Perform the structured compliance audit:"""
    )
])

history_investigator_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an Insurance Fraud and Claim History Investigator.
Evaluate the current claim submission against the client's past history and similarity benchmarks.

Rules:
1. Identify rapid repeat filing patterns, velocity spikes, or inconsistent incident dates.
2. Flag potential staged accidents, multiple simultaneous claims, or anomalous amounts.
3. Provide an anomaly score and itemized suspicion flags."""
    ),
    (
        "human",
        """Client Profile & Past Claims History:
{history_context}

Current Claim Incident:
{current_claim}

Provide the investigative anomaly breakdown:"""
    )
])

orchestrator_summary_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are the Chief Claims Adjudication Officer.
Synthesize the outputs from the Investigator and Compliance Evaluator into a finalized claims decision statement.
Clearly outline coverage determination, total risk score, and required next actions."""
    ),
    (
        "human",
        """Compliance Findings:
{compliance_report}

Historical Risk Assessment:
{history_report}

Generate the final formal audit verdict:"""
    )
])


# ==============================================================================
# 2. PROMPT REGISTRY CLASS (Backward Compatibility with your existing pattern)
# ==============================================================================

class PromptRegistry:
    TEMPLATES = {
        "rag_refinement": rag_refinement_prompt,
        "compliance_evaluator": compliance_evaluator_prompt,
        "history_investigator": history_investigator_prompt,
        "orchestrator": orchestrator_summary_prompt
    }

    @classmethod
    def get_prompt(cls, key: str) -> ChatPromptTemplate:
        prompt = cls.TEMPLATES.get(key)
        if not prompt:
            raise KeyError(f"Prompt template '{key}' not found in PromptRegistry.")
        return prompt

    @classmethod
    def get_chain(cls, key: str, llm):
        prompt = cls.get_prompt(key)
        return prompt | llm