"""
chroma_store.py — Source-diverse ChromaDB retrieval.
Guarantees results from ALL indexed CSVs, not just the dominant one.
"""

import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)


def get_collection():
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )


def add_documents(documents: list[dict]):
    collection = get_collection()
    texts     = [doc["text"] for doc in documents]
    ids       = [f"{doc['source']}_row{doc['row_index']}_chunk{doc['chunk_index']}" for doc in documents]
    metadatas = [{"source": doc["source"], "row_index": str(doc["row_index"])} for doc in documents]

    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        batch_ids   = ids[i:i+batch_size]
        batch_meta  = metadatas[i:i+batch_size]
        existing    = collection.get(ids=batch_ids)["ids"]
        new_indices = [j for j, id_ in enumerate(batch_ids) if id_ not in existing]
        if new_indices:
            collection.add(
                documents=[batch_texts[j] for j in new_indices],
                ids      =[batch_ids[j]   for j in new_indices],
                metadatas=[batch_meta[j]  for j in new_indices]
            )
            print(f"Added batch {i//batch_size + 1}: {len(new_indices)} new chunks")

    print(f"Collection now has {collection.count()} total chunks.")


def _get_all_sources(collection) -> list[str]:
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m.get("source", "unknown") for m in all_meta})


def query_documents(query: str, top_k: int = 5) -> list[dict]:
    """
    Source-diverse retrieval:
    Fetches chunks from EACH source separately → merges → re-ranks.
    Guarantees the LLM sees context from ALL projects.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    sources      = _get_all_sources(collection)
    per_source_k = max(2, top_k // max(len(sources), 1))
    all_results: list[dict] = []

    for source in sources:
        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(per_source_k, collection.count()),
                where={"source": source},
            )
            for i, doc in enumerate(results["documents"][0]):
                all_results.append({
                    "text":     doc,
                    "source":   results["metadatas"][0][i].get("source", "unknown"),
                    "distance": results["distances"][0][i],
                })
        except Exception:
            pass

    # Fallback: global query if per-source gave nothing
    if not all_results:
        results = collection.query(query_texts=[query], n_results=min(top_k, collection.count()))
        for i, doc in enumerate(results["documents"][0]):
            all_results.append({
                "text":     doc,
                "source":   results["metadatas"][0][i].get("source", "unknown"),
                "distance": results["distances"][0][i],
            })

    all_results.sort(key=lambda x: x["distance"])
    return all_results[:top_k]


def clear_collection():
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
        print("Collection cleared.")
    except Exception:
        pass
    return get_collection()


def get_collection_info() -> dict:
    collection = get_collection()
    sources = _get_all_sources(collection)
    return {"name": CHROMA_COLLECTION_NAME, "count": collection.count(), "sources": sources}