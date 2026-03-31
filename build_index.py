import os
import sys
import json
import numpy as np
import faiss
from utils.logger import log
from utils.embedding_utils import load_model, embed_texts

def main():
    # STEP 2: FREEZE ARTIFACTS
    critical_files = [
        "dataset/embeddings.npy",
        "dataset/faiss_index.bin",
        "dataset/chunk_metadata.json"
    ]
    
    if any(os.path.exists(f) for f in critical_files):
        if "--rebuild" not in sys.argv:
            log("WARNING: Index files already exist. Refusing to accidentally overwrite.", level="WARNING")
            log("To explicitly recreate the index, please pass the --rebuild flag: `python build_index.py --rebuild`")
            sys.exit(1)
        else:
            log("Proceeding with index rebuild flag.")
            
    # Load config file (STEP 1)
    with open("config.json", "r") as f:
        config = json.load(f)
        
    model_name = config.get("embedding_model", "BAAI/bge-large-en-v1.5")
    prefix = config.get("embedding_prefix", "Represent this sentence for retrieval: ")
    
    log("Loading chunks_v3.json...")
    with open("dataset/chunks_v3.json", "r") as f:
        chunks = json.load(f)

    # Extract embedding_ready_text and add prefix from config
    texts = [prefix + c["embedding_ready_text"] for c in chunks]

    # Use embedding_utils
    model = load_model(model_name)
    embeddings = embed_texts(model, texts, batch_size=32, show_progress_bar=True, normalize=True)

    log(f"Embeddings shape: {embeddings.shape}")
    np.save("dataset/embeddings.npy", embeddings)

    log("Building FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    faiss.write_index(index, "dataset/faiss_index.bin")

    log("Saving metadata...")
    metadata_list = []
    for c in chunks:
        metadata_list.append({
            "chunk_id": c.get("chunk_id"),
            "text": c.get("text"),
            "source": c.get("source"),
            "section": c.get("section"),
            "priority": c.get("priority")
        })

    with open("dataset/chunk_metadata.json", "w") as f:
        json.dump(metadata_list, f, indent=2)

    log("System index rebuilt and ready.")

if __name__ == "__main__":
    main()
