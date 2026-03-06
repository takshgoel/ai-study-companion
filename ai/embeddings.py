import faiss
import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer


@st.cache_resource(show_spinner=False)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def split_text(text: str, chunk_size: int = 400) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size) if words[i : i + chunk_size]]


@st.cache_resource(show_spinner=False)
def build_vector_store_cached(doc_payload: tuple[tuple[str, str], ...]) -> dict:
    model = get_embedding_model()
    chunks = []
    metadata = []

    for name, content in doc_payload:
        for chunk in split_text(content):
            if chunk.strip():
                chunks.append(chunk)
                metadata.append(name)

    if not chunks:
        return {"index": None, "chunks": [], "metadata": []}

    embeddings = model.encode(chunks)
    dim = embeddings.shape[1]

    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))

    return {"index": index, "chunks": chunks, "metadata": metadata}


def get_vector_store(docs: list[dict]) -> dict:
    payload = tuple((doc["name"], doc["content"]) for doc in docs)
    return build_vector_store_cached(payload)


def retrieve_chunks(question: str, vector_store: dict, k: int = 5) -> list[dict]:
    index = vector_store.get("index")
    chunks = vector_store.get("chunks", [])
    metadata = vector_store.get("metadata", [])

    if index is None or not chunks:
        return []

    model = get_embedding_model()
    q_embedding = model.encode([question])

    top_k = min(k, len(chunks))
    _, indices = index.search(np.array(q_embedding), top_k)

    return [{"text": chunks[idx], "source": metadata[idx]} for idx in indices[0]]
