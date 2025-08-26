from app.adapters.openai_client import make_chat
from app.prompts.fusion_prompt import FUSE_SYSTEM

def fuse(question: str, cy_result: str, cy_ctx: str, facts: str) -> str:
    llm = make_chat()
    user = (
        f"Question: {question}\n\n"
        f"CYRESULT:\n{cy_result or '(none)'}\n\n"
        f"CYCONTEXT:\n{cy_ctx or '(none)'}\n\n"
        f"{facts}"
    )
    return llm.invoke([{"role":"system","content":FUSE_SYSTEM},
                       {"role":"user","content":user}]).content
