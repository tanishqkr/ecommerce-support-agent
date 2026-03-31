import json

def process_triage(phase3_data):
    normalized = phase3_data.get("normalized", {})
    validation = phase3_data.get("validation", {})
    derived_flags = phase3_data.get("derived_flags", {})
    state = phase3_data.get("state", {})

    query = normalized.get("query", "")
    order = normalized.get("order", {})

    intent = state.get("intent", "UNKNOWN")
    issue_type = state.get("issue_type", "UNKNOWN")
    base_confidence = state.get("confidence", 0.5)

    soft_errors = validation.get("soft_errors", [])
    conflicts = validation.get("conflicts", [])
    multi_intent = derived_flags.get("multi_intent", False)
    query_empty = derived_flags.get("query_empty", False)

    final_intent = intent
    final_issue_type = issue_type
    needs_clarification = False
    clarification_question = None
    missing_fields = []

    # CLARIFICATION CONDITIONS
    is_vague = "AMBIGUOUS_QUERY" in soft_errors or query_empty
    is_unknown_no_intent = (issue_type == "UNKNOWN" and intent == "GENERAL_QUERY")

    if is_vague:
        needs_clarification = True
        clarification_question = "Can you please provide more details about your request?"
    elif multi_intent:
        needs_clarification = True
        clarification_question = "Can you confirm if you want a refund, return, or replacement?"
    elif len(conflicts) > 0:
        needs_clarification = True
        if "FINAL_SALE_CONFLICT" in conflicts:
            clarification_question = (
                "This item is marked as Final Sale and may not be eligible "
                "for return. Could you clarify the reason for your return request?"
            )
        elif "NO_DELIVERY_DATA" in conflicts:
            clarification_question = (
                "We could not confirm your delivery status. "
                "Has your order been delivered? Please provide delivery details."
            )
        else:
            clarification_question = "We found conflicting information. Could you please clarify?"
    elif is_unknown_no_intent:
        needs_clarification = True
        clarification_question = "Can you describe what issue you're facing with the product?"

    # MISSING FIELDS
    # delivery_date missing -> needed for returns
    if order.get("delivery_date") is None and intent in ["RETURN_REQUEST", "REFUND_REQUEST", "REPLACEMENT_REQUEST"]:
        missing_fields.append("delivery_date")
    
    if order.get("category") is None:
        missing_fields.append("category")

    KNOWN_DISSATISFACTION_SIGNALS = [
        "not satisfied", "dissatisfied", "unhappy", 
        "disappointed", "not happy", "poor quality"
    ]
    is_dissatisfaction = any(
        sig in query for sig in KNOWN_DISSATISFACTION_SIGNALS
    )
    if intent == "GENERAL_QUERY" and issue_type == "UNKNOWN" and not is_dissatisfaction:
        missing_fields.append("intent")

    # CONFIDENCE ADJUSTMENT
    confidence = base_confidence
    
    is_ambiguous = needs_clarification or is_vague
    is_clear_strong = not is_ambiguous and len(soft_errors) == 0 and len(conflicts) == 0 and len(missing_fields) == 0
    
    if is_clear_strong:
        confidence += 0.05
    
    if is_ambiguous:
        confidence -= 0.1

    if confidence < 0.3:
        confidence = 0.3
    if confidence > 0.95:
        confidence = 0.95

    # format structure strict
    output = {
        "final_intent": final_intent,
        "final_issue_type": final_issue_type,
        "confidence": round(confidence, 2),
        "needs_clarification": needs_clarification,
        "clarification_question": clarification_question,
        "missing_fields": missing_fields
    }
    
    from datetime import datetime
    output["triage_version"] = "1.0"
    output["processed_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    return output

if __name__ == "__main__":
    with open("output_state.json", "r") as f:
        data = json.load(f)

    print("=== TESTING 5 INPUTS ===")
    for item in data[:5]:
        res = process_triage(item)
        print(f"Order ID: {item.get('order_id')}")
        print(f"Query: {item.get('normalized', {}).get('query')}")
        print(json.dumps(res, indent=2))
        print("-" * 50)

    for item in data:
        item["triage"] = process_triage(item)

    with open("output_triage.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nProcessed {len(data)} items successfully. Output saved to output_triage.json")

    blocked = sum(1 for i in data if not i["validation"]["safe_to_process"])
    needs_clarif = sum(1 for i in data if i["triage"]["needs_clarification"])
    high_conf = sum(1 for i in data if i["triage"]["confidence"] >= 0.85)
    low_conf = sum(1 for i in data if i["triage"]["confidence"] < 0.6)
    
    print("\n=== TRIAGE SUMMARY ===")
    print(f"Total processed     : {len(data)}")
    print(f"Blocked (hard error): {blocked}")
    print(f"Needs clarification : {needs_clarif}")
    print(f"High confidence (>=0.85): {high_conf}")
    print(f"Low confidence (<0.60) : {low_conf}")
