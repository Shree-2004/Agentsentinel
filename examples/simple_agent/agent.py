"""A deliberately trivial stand-in for "someone else's agent" — the point
of this example is that AgentSentinel never needed to know this function
existed until the config file below pointed at it. No AgentSentinel import,
no special decoration, just a plain function.
"""

_FAQS = {
    "return policy": "You can return any item within 30 days for a full refund.",
    "shipping time": "Standard shipping takes 3-5 business days.",
}


def answer(question: str) -> str:
    q = question.lower()
    for key, text in _FAQS.items():
        if key in q:
            return text
    return "I don't know the answer to that."
