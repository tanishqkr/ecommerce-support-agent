from sentence_transformers import SentenceTransformer
import numpy as np
from utils.logger import log

def load_model(model_name):
    log(f"Loading embedding model: {model_name}")
    try:
        model = SentenceTransformer(model_name)
        log("Model loaded successfully.")
        return model
    except Exception as e:
        log(f"Failed to load model {model_name}: {e}", level="ERROR")
        raise

def embed_texts(model, texts, batch_size=32, show_progress_bar=False, normalize=True):
    log(f"Generating embeddings for {len(texts)} texts...")
    embeddings = model.encode(
        texts, 
        batch_size=batch_size, 
        show_progress_bar=show_progress_bar, 
        normalize_embeddings=normalize
    )
    return np.array(embeddings).astype('float32')

def normalize_vectors(vectors):
    # Normalize if not already done by the model
    # (Though SentenceTransformer normalize_embeddings=True usually covers this)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.where(norms > 0, vectors / norms, vectors)
