import os
import sys

# Prevent TensorFlow/Keras deadlock on macOS Python 3.9
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json


from utils.logger import log
from utils.embedding_utils import load_model, embed_texts
from utils.faiss_utils import load_index, search_index
from utils.scoring_utils import apply_priority_boost, deduplicate_results, enforce_diversity

# ----------------------------------------
# CONFIG
# ----------------------------------------
CONFIG_PATH = "config.json"
INDEX_PATH = "data/dataset/faiss_index.bin"
METADATA_PATH = "data/dataset/chunk_metadata.json"

TOP_K_INITIAL = 15
TOP_K_FINAL = 5
MIN_CHUNKS_REQUIRED = 3
MIN_UNIQUE_DOCS = 2
PRIORITY_WEIGHT = 0.2
MAX_CHUNKS_PER_DOC = 2
DEDUP_THRESHOLD = 0.85

# ----------------------------------------
# GLOBALS — lazy loaded once
# ----------------------------------------
_config = None
_model = None
_index = None
_metadata = None


def _load_resources():
    global _config, _model, _index, _metadata

    if _config is None:
        try:
            with open(CONFIG_PATH, "r") as f:
                _config = json.load(f)
            log("Config loaded.")
        except Exception as e:
            log(f"Config load failed: {e}", level="ERROR")
            raise

    if _model is None:
        model_name = _config.get("embedding_model", "BAAI/bge-large-en-v1.5")
        _model = load_model(model_name)

    if _index is None:
        if not os.path.exists(INDEX_PATH):
            log("FAISS index file missing.", level="CRITICAL")
            raise FileNotFoundError("FAISS index missing at: " + INDEX_PATH)
        _index = load_index(INDEX_PATH)

    if _metadata is None:
        if not os.path.exists(METADATA_PATH):
            log("Chunk metadata file missing.", level="CRITICAL")
            raise FileNotFoundError("Chunk metadata missing at: " + METADATA_PATH)
        with open(METADATA_PATH, "r") as f:
            _metadata = json.load(f)
        if _index.ntotal != len(_metadata):
            log(
                f"Index/metadata size mismatch: {_index.ntotal} vs {len(_metadata)}",
                level="ERROR"
            )
            raise ValueError("Index and metadata are out of sync. Please rebuild.")


# ----------------------------------------
# CORE RETRIEVAL
# ----------------------------------------
def retrieve_chunks(query: str, state: dict) -> list:
    """
    Embed query, search FAISS, post-process and return final chunks.
    """
    if not query or not query.strip():
        log("Empty query passed to retrieve_chunks.", level="ERROR")
        return []

    _load_resources()

    prefix = _config.get("embedding_prefix", "")
    top_k_initial = _config.get("top_k_initial", TOP_K_INITIAL)
    top_k_final = _config.get("top_k_final", TOP_K_FINAL)
    priority_weight = _config.get("priority_weight", PRIORITY_WEIGHT)
    max_chunks_per_doc = _config.get("max_chunks_per_doc", MAX_CHUNKS_PER_DOC)
    dedup_threshold = _config.get("dedup_threshold", DEDUP_THRESHOLD)

    # 1. Embed query
    prefixed_query = prefix + query
    query_emb = embed_texts(_model, [prefixed_query], normalize=True)

    # 2. Search FAISS
    scores, indices = search_index(_index, query_emb, top_k_initial)

    # 3. Build candidates with full metadata
    candidates = []
    for i in range(top_k_initial):
        idx = indices[0][i]
        if idx == -1:
            continue

        meta = _metadata[idx]
        sim_score = float(scores[0][i])
        priority = meta.get("priority", 1)

        # Parse doc_id from chunk_id (e.g. "DOC_001_A_1" → "DOC_001")
        chunk_id = meta.get("chunk_id", "")
        parts = chunk_id.split("_")
        doc_id = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else chunk_id

        boosted_score = apply_priority_boost(sim_score, priority, priority_weight)

        candidates.append({
            "text": meta.get("text", ""),
            "source": meta.get("source", "unknown"),
            "section": meta.get("section", ""),
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "score": round(boosted_score, 6),
            "priority": priority
        })

    log(f"Initial candidates: {len(candidates)}")

    # 4. Sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # 5. Semantic deduplication
    after_dedup = deduplicate_results(candidates, dedup_threshold)
    log(f"After dedup: {len(after_dedup)}")

    # 6. Diversity enforcement (max chunks per doc)
    after_diversity = enforce_diversity(after_dedup, max_chunks_per_doc)
    log(f"After diversity: {len(after_diversity)}")

    # ---- HARD FILTER: DELIVERY_ISSUE ----
    intent = state.get("intent", "UNKNOWN")
    if intent == "DELIVERY_ISSUE":
        delivery_keywords = [
            "delivery", "delivered", "not delivered", 
            "shipment", "tracking", "dispatch", 
            "in transit", "out for delivery"
        ]
        filtered = []
        for chunk in after_diversity:
            text = chunk["text"].lower()
            if any(k in text for k in delivery_keywords):
                filtered.append(chunk)
        
        # Fallback if too aggressive
        if len(filtered) >= 3:
            after_diversity = filtered
            log(f"Applied delivery hard filter: {len(after_diversity)} chunks remaining.")

    # 7. Final top-k slice
    final_candidates = after_diversity[:top_k_final]

    # ---- ISSUE 1: INTENT-AWARE FILTERING ----
    issue_type = state.get("issue_type", "UNKNOWN")
    intent = state.get("intent", "UNKNOWN")

    INTENT_KEYWORDS = {
        "SIZE_ISSUE": ["size", "fit", "too small", "too big"],
        "DAMAGED": ["damaged", "broken", "defective", "cracked"],
        "DELIVERY_ISSUE": ["delivery", "not received", "tracking"],
        "CUSTOMER_DISSATISFACTION": ["not satisfied", "unhappy"]
    }

    for c in final_candidates:
        text = c["text"].lower()
        # Boost relevant chunks
        relevant_keywords = INTENT_KEYWORDS.get(issue_type, [])
        if any(k in text for k in relevant_keywords):
            c["score"] += 0.05
        
        # Penalize clearly irrelevant chunks
        if issue_type == "SIZE_ISSUE":
            if any(k in text for k in ["damaged", "defective", "broken"]):
                c["score"] -= 0.2
        elif issue_type == "DAMAGED":
            if any(k in text for k in ["size", "fit", "too small", "too big"]):
                c["score"] -= 0.2

    # Re-sort after adjustment
    final_candidates.sort(key=lambda x: x["score"], reverse=True)

    # ---- ISSUE 4: POLICY TYPE TAGGING ----
    for c in final_candidates:
        section = c["section"].lower()
        if "eligib" in section:
            c["policy_type"] = "ELIGIBILITY"
        elif "refund" in section:
            c["policy_type"] = "REFUND"
        elif "return" in section:
            c["policy_type"] = "RETURN_CONDITION"
        elif "evidence" in section:
            c["policy_type"] = "EVIDENCE"
        elif "exception" in section:
            c["policy_type"] = "EXCEPTION"
        else:
            c["policy_type"] = "GENERAL"

    # ---- MINOR IMPROVEMENTS: NORMALIZATION & TOP TAGGING ----
    if final_candidates:
        max_score = max(c["score"] for c in final_candidates)
        if max_score > 0:
            for c in final_candidates:
                c["score"] = round(c["score"] / max_score, 4)

    for i, c in enumerate(final_candidates):
        c["is_top_policy"] = (i < 2)

    final_chunks = final_candidates

    # ---- VALIDATION ----
    if len(final_chunks) < MIN_CHUNKS_REQUIRED:
        log(
            f"Validation failed: only {len(final_chunks)} chunks (need >= {MIN_CHUNKS_REQUIRED})",
            level="ERROR"
        )

    unique_docs = len(set(c["doc_id"] for c in final_chunks))
    if unique_docs < MIN_UNIQUE_DOCS:
        log(
            f"Validation warning: only {unique_docs} unique doc(s) (need >= {MIN_UNIQUE_DOCS})",
            level="ERROR"
        )

    # Strip internal-only fields before returning
    return [
        {
            "text": c["text"],
            "source": c["source"],
            "section": c["section"],
            "doc_id": c["doc_id"],
            "chunk_id": c["chunk_id"],
            "score": c["score"],
            "policy_type": c.get("policy_type", "GENERAL"),
            "is_top_policy": c.get("is_top_policy", False)
        }
        for c in final_chunks
    ]


# ----------------------------------------
# PHASE 5 PIPELINE
# ----------------------------------------
def run_phase5(phase4_data: dict) -> dict:
    """
    Accepts a single Phase 4 output record, adds 'retrieval' key.
    Does NOT mutate any existing keys.
    """
    try:
        query = phase4_data.get("normalized", {}).get("query", "")
        order_id = phase4_data.get("order_id", "UNKNOWN")
        state = phase4_data.get("state", {})
        validation = phase4_data.get("validation", {})

        # ---- ISSUE 3: BLOCKED CASE HANDLING ----
        if validation.get("safe_to_process") == False:
            result = dict(phase4_data)
            result["retrieval"] = []
            result["retrieval_meta"] = {
                "status": "SKIPPED",
                "reason": "Blocked case",
                "chunk_count": 0
            }
            return result

        # ---- ISSUE 2: QUERY EXPANSION ----
        expanded_query = query
        intent = state.get("intent", "")
        issue_type = state.get("issue_type", "")

        if intent == "DELIVERY_ISSUE":
            expanded_query = "delivery tracking shipment status not received " + query
        if issue_type == "SIZE_ISSUE":
            expanded_query = "size mismatch fit return policy " + query
        if issue_type == "DAMAGED":
            expanded_query = "damaged defective broken return refund policy " + query

        if not query.strip():
            log(f"[{order_id}] Empty query, skipping retrieval.", level="ERROR")
            result = dict(phase4_data)
            result["retrieval"] = []
            result["retrieval_meta"] = {
                "status": "SKIPPED",
                "reason": "Empty query",
                "chunk_count": 0
            }
            return result

        chunks = retrieve_chunks(expanded_query, state)

        result = dict(phase4_data)
        result["retrieval"] = chunks
        
        chunk_count = len(chunks)
        unique_docs = len(set(c["doc_id"] for c in chunks))

        # ---- MINOR IMPROVEMENT 3: RETRIEVAL QUALITY CHECK ----
        quality_flag = "GOOD"
        if chunk_count < MIN_CHUNKS_REQUIRED:
            quality_flag = "LOW"
        elif unique_docs < MIN_UNIQUE_DOCS:
            quality_flag = "LOW_DIVERSITY"

        result["retrieval_meta"] = {
            "status": "OK" if chunk_count >= MIN_CHUNKS_REQUIRED else "PARTIAL",
            "chunk_count": chunk_count,
            "unique_docs": unique_docs,
            "quality_flag": quality_flag
        }
        log(f"[{order_id}] Retrieved {len(chunks)} chunks.")
        return result

    except Exception as e:
        log(f"Phase 5 failed for order {phase4_data.get('order_id', '?')}: {e}", level="ERROR")
        result = dict(phase4_data)
        result["retrieval"] = []
        result["retrieval_meta"] = {"status": "ERROR", "reason": str(e), "chunk_count": 0}
        return result


# ----------------------------------------
# ENTRY POINT
# ----------------------------------------
if __name__ == "__main__":
    INPUT_FILE = "output_triage.json"
    OUTPUT_FILE = "output_retrieval.json"

    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    # ---- TEST ON 5 FIRST ----
    print("=== PHASE 5 — TESTING 5 INPUTS ===")
    for item in data[:5]:
        result = run_phase5(item)
        print(f"\nOrder ID : {result.get('order_id')}")
        print(f"Query    : {result.get('normalized', {}).get('query', '')[:80]}")
        print(f"Status   : {result.get('retrieval_meta', {}).get('status')}")
        print(f"Chunks   : {result.get('retrieval_meta', {}).get('chunk_count')}")
        print(f"Unique docs: {result.get('retrieval_meta', {}).get('unique_docs')}")
        for i, chunk in enumerate(result.get("retrieval", []), 1):
            print(f"  [{i}] score={chunk['score']:.4f} | doc={chunk['doc_id']} | chunk={chunk['chunk_id']}")
            print(f"       {chunk['text'][:90]}...")
        print("-" * 60)

    # ---- FULL DATASET ----
    print("\n=== PHASE 5 — FULL DATASET ===")
    full_results = []
    for item in data:
        full_results.append(run_phase5(item))

    with open(OUTPUT_FILE, "w") as f:
        json.dump(full_results, f, indent=2)

    # ---- SUMMARY ----
    total = len(full_results)
    ok = sum(1 for r in full_results if r.get("retrieval_meta", {}).get("status") == "OK")
    partial = sum(1 for r in full_results if r.get("retrieval_meta", {}).get("status") == "PARTIAL")
    skipped = sum(1 for r in full_results if r.get("retrieval_meta", {}).get("status") == "SKIPPED")
    errors = sum(1 for r in full_results if r.get("retrieval_meta", {}).get("status") == "ERROR")

    print(f"\n=== PHASE 5 RETRIEVAL SUMMARY ===")
    print(f"Total processed : {total}")
    print(f"OK (>=3 chunks) : {ok}")
    print(f"Partial (<3)    : {partial}")
    print(f"Skipped (empty) : {skipped}")
    print(f"Errors          : {errors}")
    print(f"\nOutput saved to: {OUTPUT_FILE}")
