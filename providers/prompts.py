from langchain_core.prompts import ChatPromptTemplate

class PromptRegistry:
    TEMPLATES = {
        "history_investigator": [
            ("system", "You are a Fraud Analyst. Review history for Client {client_id}."),
            ("human", "Analyze these claims for suspicious patterns:\n{history}")
        ],
        "compliance_evaluator": [
            ("system", "You are a Compliance Officer. Apply these rules:\n{rules}"),
            ("human", "Claim Content: {content}")
        ],
        "orchestrator": [
            ("system", "You are a Senior Adjuster. Provide a final verdict."),
            ("human", "Risk Score: {risk_score}\nReport: {report}\n\nVerdict (APPROVED/DENIED):")
        ]
    }

    @classmethod
    def get_chain(cls, key: str, llm):
        prompt = ChatPromptTemplate.from_messages(cls.TEMPLATES[key])
        return prompt | llm