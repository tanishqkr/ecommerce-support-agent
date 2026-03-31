from difflib import SequenceMatcher

def apply_priority_boost(similarity_score, priority, priority_weight=0.2):
    return similarity_score * (1 + priority_weight * priority)

def deduplicate_results(candidates, dedup_threshold=0.85):
    """
    Remove candidates that have high string similarity to already seen candidates.
    Assumes candidates are already sorted DESC by score.
    """
    after_dedup = []
    
    for c in candidates:
        is_duplicate = False
        for seen in after_dedup:
            if SequenceMatcher(None, c["text"], seen["text"]).ratio() > dedup_threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            after_dedup.append(c)
            
    return after_dedup

def enforce_diversity(candidates, max_chunks_per_doc=2):
    """
    Limit max chunks returning from the same document ID.
    Assumes candidates are processed in ranking order.
    """
    after_diversity = []
    doc_counts = {}
    
    for c in candidates:
        doc_id = c["doc_id"]
        count = doc_counts.get(doc_id, 0)
        
        if count < max_chunks_per_doc:
            after_diversity.append(c)
            doc_counts[doc_id] = count + 1
            
    return after_diversity
