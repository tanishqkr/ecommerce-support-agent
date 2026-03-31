import faiss
from utils.logger import log

def load_index(index_path):
    log(f"Loading FAISS index from {index_path}")
    try:
        index = faiss.read_index(index_path)
        log("FAISS index loaded successfully.")
        return index
    except Exception as e:
        log(f"Failed to load FAISS index: {e}", level="ERROR")
        raise

def search_index(index, query_embedding, top_k):
    # Returns raw scores and indices
    scores, indices = index.search(query_embedding, top_k)
    return scores, indices
