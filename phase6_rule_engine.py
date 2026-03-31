import json
import os
import sys
from utils.logger import log

def evaluate_decision(item: dict) -> dict:
    validation = item.get("validation", {})
    triage = item.get("triage", {})
    state = item.get("state", {})
    retrieval = item.get("retrieval", [])
    order = item.get("normalized", {}).get("order", {})
    derived_flags = item.get("derived_flags", {})

    # Default values needed for rules
    safe_to_process = validation.get("safe_to_process", False)
    issue_type = triage.get("final_issue_type") or state.get("issue_type", "UNKNOWN")
    intent = triage.get("final_intent") or state.get("intent", "UNKNOWN")
    is_final_sale = order.get("is_final_sale", False)
    
    # Check if a conflict resolved it
    resolved_conflicts = item.get("resolved_conflicts", [])
    if isinstance(resolved_conflicts, list) and "is_final_sale" in resolved_conflicts:
         pass
    
    # STEP 1 — FILTER VALID POLICIES
    valid_policies = []
    chunk_ids = []
    
    for chunk in retrieval:
        if chunk.get("is_top_policy", False) or chunk.get("score", 0) > 0.9:
            valid_policies.append(chunk)
            chunk_ids.append(chunk.get("chunk_id"))

    decision = {
        "status": "REVIEW",
        "action": "NONE",
        "reason": "Default fallback",
        "supporting_chunks": chunk_ids
    }

    # STEP 2 — APPLY RULES
    
    # RULE 1 — BLOCKED CASE
    if not safe_to_process:
        decision["status"] = "BLOCKED"
        decision["action"] = "NONE"
        decision["reason"] = "Validation blocked request"
        decision["supporting_chunks"] = []
        return decision

    # RULE 2 — FINAL SALE
    if is_final_sale:
        if issue_type == "DAMAGED":
            decision["status"] = "APPROVED"
            decision["action"] = "REFUND"
            decision["reason"] = "Damaged exceptions override final sale"
        else:
            decision["status"] = "REJECTED"
            decision["action"] = "NONE"
            decision["reason"] = "Item is final sale"
        return decision

    # FIX 2 — PERISHABLE OVERRIDE
    is_perishable = order.get("is_perishable", False)
    within_return_window = derived_flags.get("within_return_window", False)
    if is_perishable and not within_return_window:
        decision["status"] = "REJECTED"
        decision["action"] = "NONE"
        decision["reason"] = "Perishable item outside of return window"
        return decision

    # RULE 3 — DAMAGED ITEM
    if issue_type == "DAMAGED":
        # FIX 1 & 5 — REFINED DETECTION
        has_refund_policy = any(
            p.get("policy_type") == "REFUND" or "refund" in p.get("text", "").lower()
            for p in valid_policies
        )
        if has_refund_policy:
            decision["status"] = "APPROVED"
            decision["action"] = "REFUND"
            decision["reason"] = "Damaged item eligible for refund"
        else:
            decision["status"] = "APPROVED"
            decision["action"] = "RETURN"
            decision["reason"] = "Damaged item eligible for return"
        return decision

    # RULE 4 — SIZE ISSUE
    if issue_type == "SIZE_ISSUE":
        decision["status"] = "APPROVED"
        decision["action"] = "RETURN"
        decision["reason"] = "Size issue qualifies for return"
        return decision

    # RULE 5 — DELIVERY ISSUE (FIX 4)
    if intent == "DELIVERY_ISSUE":
        decision["status"] = "ESCALATE"
        decision["action"] = "TRACK"
        decision["reason"] = "Order requires tracking based on delivery status"
        return decision

    # RULE 6 — CUSTOMER DISSATISFACTION (FIX 3)
    if issue_type == "CUSTOMER_DISSATISFACTION":
        if derived_flags.get("within_return_window"):
            decision["status"] = "APPROVED"
            decision["action"] = "RETURN"
            decision["reason"] = "Customer dissatisfaction within return window"
        else:
            decision["status"] = "REVIEW"
            decision["action"] = "NONE"
            decision["reason"] = "Customer dissatisfaction outside return window"
        return decision

    # RULE 7 — DEFAULT
    decision["status"] = "REVIEW"
    decision["action"] = "NONE"
    decision["reason"] = "No matching automated rule; requires review"
    
    return decision



def run_phase6(input_path: str, output_path: str):
    log("Starting Phase 6: Rule Engine")
    
    if not os.path.exists(input_path):
        log(f"Input file not found: {input_path}", level="CRITICAL")
        sys.exit(1)
        
    with open(input_path, "r") as f:
        data = json.load(f)

    # Process all records
    for item in data:
        item["decision"] = evaluate_decision(item)

    # Dump output
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    log(f"Phase 6 completed. Processed {len(data)} items. Saved to {output_path}")

    # Print summary
    stats = {}
    for item in data:
        status = item["decision"]["status"]
        stats[status] = stats.get(status, 0) + 1
        
    print("\n=== PHASE 6 RULE ENGINE SUMMARY ===")
    print(f"Total processed : {len(data)}")
    for status, count in stats.items():
        print(f"  {status:<15}: {count}")

    # TEST on 5 inputs
    print("\n=== FIRST 5 RECORDS DECISIONS ===")
    for item in data[:5]:
        order_id = item.get("order_id", "UNKNOWN")
        dec = item["decision"]
        print(f"Order ID : {order_id}")
        print(f"Status   : {dec['status']}")
        print(f"Action   : {dec['action']}")
        print(f"Reason   : {dec['reason']}")
        print(f"Chunks   : {dec['supporting_chunks']}")
        print("-" * 60)

if __name__ == "__main__":
    run_phase6("output_retrieval.json", "output_decision.json")
