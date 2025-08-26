from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.core.settings import settings

def make_chat():
    return ChatOpenAI(
        model=settings.chat_model,
        temperature=0,
        api_key=settings.openai_key,
    )

def make_embeddings():
    return OpenAIEmbeddings(
        model=settings.emb_model,
        api_key=settings.openai_key,
    )