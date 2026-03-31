import json
import os
import sys

from utils.logger import log
from utils.embedding_utils import load_model, embed_texts
from utils.faiss_utils import load_index, search_index
from utils.scoring_utils import apply_priority_boost, deduplicate_results, enforce_diversity

# Globals for lazy loading
_config = None
_model = None
_index = None
_metadata = None

def _load_resources():
    global _config, _model, _index, _metadata
    
    if _config is None:
        try:
            with open("config.json", "r") as f:
                _config = json.load(f)
        except Exception as e:
            log(f"Config file not found or corrupted: {e}", level="ERROR")
            raise

    if _model is None:
        _model = load_model(_config.get("embedding_model", "BAAI/bge-large-en-v1.5"))

    if _index is None:
        index_path = "dataset/faiss_index.bin"
        if not os.path.exists(index_path):
            log("Index file is missing. Please run build_index.py --rebuild to generate it.", level="CRITICAL")
            raise FileNotFoundError("FAISS index missing")
        _index = load_index(index_path)

    if _metadata is None:
        meta_path = "dataset/chunk_metadata.json"
        if not os.path.exists(meta_path):
            log("Metadata file is missing.", level="CRITICAL")
            raise FileNotFoundError("Chunk metadata missing")
        with open(meta_path, "r") as f:
            _metadata = json.load(f)
            
        # Metadata mismatch check: index size should match metadata size
        if _index.ntotal != len(_metadata):
            msg = f"Metadata mismatch: FAISS index size ({_index.ntotal}) != metadata length ({len(_metadata)}). Please rebuild."
            log(msg, level="ERROR")
            raise ValueError("Index and Metadata are significantly out of sync")

def retrieve(query, top_k=None):
    # STEP 5: Add Error Handling
    if not query or not query.strip():
        log("Received an empty query.", level="ERROR")
        return {"error": "Query cannot be empty", "results": []}

    _load_resources()
    
    prefix = _config.get("embedding_prefix", "")
    top_k_initial = _config.get("top_k_initial", 15)
    top_k_final = _config.get("top_k_final", 5)
    priority_weight = _config.get("priority_weight", 0.2)
    max_chunks_per_doc = _config.get("max_chunks_per_doc", 2)
    dedup_threshold = _config.get("dedup_threshold", 0.85)

    # 1. Embed query
    prefixed_query = prefix + query
    query_emb = embed_texts(_model, [prefixed_query], normalize=True)

    # 2. Search FAISS index
    scores, indices = search_index(_index, query_emb, top_k_initial)

    # 3. Form initial candidates & score (apply priority boost)
    candidates = []
    for i in range(top_k_initial):
        idx = indices[0][i]
        if idx == -1:
            continue
            
        meta = _metadata[idx]
        sim_score = float(scores[0][i])
        priority = meta.get("priority", 1)
        
        # Determine doc_id
        chunk_id = meta.get("chunk_id", "")
        parts = chunk_id.split("_")
        doc_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else chunk_id

        # Calculate final boosted score
        final_score = apply_priority_boost(sim_score, priority, priority_weight)
        
        candidates.append({
            "text": meta["text"],
            "source": meta["source"],
            "section": meta["section"],
            "score": final_score,
            "priority": priority,
            "doc_id": doc_id
        })
        
    log(f"Initial candidates fetched: {len(candidates)}")

    # Sort descending based on our new final_scores before filters apply
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 4. Semantic Deduplication
    after_dedup = deduplicate_results(candidates, dedup_threshold)
    log(f"Candidates after deduplication: {len(after_dedup)}")

    # 5. Diversity Enforcement
    after_diversity = enforce_diversity(after_dedup, max_chunks_per_doc)
    log(f"Candidates after diversity enforcement: {len(after_diversity)}")

    # 6. Final Slice & Attach Reason Blocks
    final_results = after_diversity[:top_k_final]
    log(f"Final results ready to return: {len(final_results)}")

    formatted_results = []
    for c in final_results:
        reason = "high semantic match"
        if c.get("priority", 1) == 2:
            reason += " + atomic rule boost"
        else:
            reason += " + contextual chunk"
            
        c["reason"] = reason
        formatted_results.append(c)

    return {
        "query": query,
        "results": formatted_results
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query_text = sys.argv[1]
        print(json.dumps(retrieve(query_text), indent=2))
