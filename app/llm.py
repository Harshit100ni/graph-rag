from openai import OpenAI
from .config import settings
from .prompts import SYSTEM_PROMPT

_client = OpenAI(api_key=settings.openai_key)

def answer_from_facts(question: str, facts: str) -> str:
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {question}\n\n{facts}"},
    ]
    resp = _client.chat.completions.create(model=settings.chat_model, temperature=0.2, messages=msgs)
    return resp.choices[0].message.content.strip()
