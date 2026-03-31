import json
from datetime import datetime

TODAY = datetime(2026, 3, 31)


# -----------------------------
# STEP 1 — NORMALIZATION
# -----------------------------
def normalize(input_json):
    query = input_json.get("query")
    order = input_json.get("order", {})

    if query is None:
        query = ""
    else:
        query = str(query).lower().strip()
        query = query.replace("refnd", "refund")
        query = query.replace("ordr", "order")
        query = query.replace("brok", "broken")

    return {
        "query": query,
        "order": order
    }


# -----------------------------
# STEP 2 — VALIDATION (NO MUTATION)
# -----------------------------
def validate(normalized):
    query = normalized["query"]
    order = normalized["order"]

    hard_errors = []
    soft_errors = []
    conflicts = []
    policy_flags = []
    notes = []

    price = order.get("price", 0)

    purchase_date = parse_date(order.get("purchase_date"))
    delivery_date = parse_date(order.get("delivery_date"))

    # HARD ERRORS
    if query == "":
        hard_errors.append("EMPTY_QUERY")

    if price < 0:
        hard_errors.append("NEGATIVE_PRICE")

    if purchase_date and purchase_date > TODAY:
        hard_errors.append("FUTURE_PURCHASE_DATE")

    if purchase_date and delivery_date:
        if delivery_date < purchase_date:
            hard_errors.append("INVALID_DATE_ORDER")

    # SOFT ERRORS
    if order.get("category") is None:
        soft_errors.append("MISSING_CATEGORY")

    if len(query.strip()) < 10:
        soft_errors.append("AMBIGUOUS_QUERY")

    # CONFLICTS
    if order.get("is_final_sale") and order.get("is_returnable"):
        conflicts.append("FINAL_SALE_CONFLICT")

    if order.get("delivery_date") is None:
        conflicts.append("NO_DELIVERY_DATA")

    # POLICY FLAGS
    if order.get("is_perishable"):
        policy_flags.append("PERISHABLE_ITEM")

    if order.get("is_hygiene_sensitive"):
        policy_flags.append("HYGIENE_ITEM")

    if order.get("return_window_days") == 0:
        policy_flags.append("ZERO_RETURN_WINDOW")

    if price > 10000:
        notes.append("HIGH_VALUE_ORDER")

    return {
        "hard_errors": hard_errors,
        "soft_errors": soft_errors,
        "conflicts": conflicts,
        "policy_flags": policy_flags,
        "system_notes": notes
    }


# -----------------------------
# STEP 3 — CONFLICT RESOLUTION
# -----------------------------
def resolve_conflicts(normalized, validation):
    order = normalized["order"]

    resolved = []

    if "FINAL_SALE_CONFLICT" in validation["conflicts"]:
        order["is_returnable"] = False
        resolved.append("FINAL_SALE_OVERRIDE")

    return resolved


# -----------------------------
# STEP 4 — DERIVED FLAGS
# -----------------------------
def derive_flags(normalized):
    query = normalized["query"]
    order = normalized["order"]

    delivery_date = parse_date(order.get("delivery_date"))

    flags = {}

    flags["query_empty"] = (query == "")
    flags["has_delivery"] = delivery_date is not None

    if delivery_date:
        days = (TODAY - delivery_date).days
        flags["days_since_delivery"] = days
        flags["within_return_window"] = days <= order.get("return_window_days", 0)
    else:
        flags["days_since_delivery"] = None
        flags["within_return_window"] = False

    flags["can_initiate_return"] = flags["has_delivery"]

    multi_keywords = ["refund", "replace", "cancel", "return"]
    count = sum(1 for word in multi_keywords if word in query)
    flags["multi_intent"] = count > 1

    flags["is_return_flow"] = any(word in query for word in ["return", "refund", "replace"])

    flags["has_issue_signal"] = any(word in query for word in [
        "broken", "damaged", "defective",
        "not working", "cracked",
        "shattered", "faulty", "rotten", "wrong", "incorrect", "missing", "late", "not received"
    ])

    return flags


# -----------------------------
# UTILS
# -----------------------------
def parse_date(date_str):
    try:
        if date_str is None:
            return None
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return None


# -----------------------------
# STEP 5 - STATE ENGINE
# -----------------------------
def build_state(normalized, validation, derived_flags):
    query = normalized["query"]
    
    if not query.strip():
        return {
            "intent": "GENERAL_QUERY",
            "issue_type": "UNKNOWN",
            "request_type": "UNKNOWN",
            "flow_type": "GENERAL_SUPPORT",
            "priority": "NORMAL",
            "confidence": 0.3
        }

    # 1. INTENT CLASSIFICATION
    intent = "GENERAL_QUERY"
    if any(w in query for w in ["refund", "money back", "reimbursement", "cash back"]):
        intent = "REFUND_REQUEST"
    elif "return" in query:
        intent = "RETURN_REQUEST"
    elif any(w in query for w in ["replace", "replacement", "swap"]):
        intent = "REPLACEMENT_REQUEST"
    elif "cancel" in query:
        intent = "CANCELLATION_REQUEST"
    elif any(w in query for w in ["where is", "not received", "delivery", "late"]):
        intent = "DELIVERY_ISSUE"
    elif derived_flags.get("has_issue_signal"):
        intent = "PRODUCT_ISSUE"

    if derived_flags.get("has_issue_signal") and normalized["order"].get("is_perishable"):
        intent = "PRODUCT_ISSUE"

    # 2. ISSUE TYPE
    issue_type = "UNKNOWN"
    if derived_flags.get("has_issue_signal"):
        issue_type = "DAMAGED"
    elif any(w in query for w in ["not received", "where is"]):
        issue_type = "NOT_DELIVERED"
    elif any(w in query for w in ["size", "fit", "small"]):
        issue_type = "SIZE_ISSUE"
    elif "not satisfied" in query:
        issue_type = "CUSTOMER_DISSATISFACTION"

    # 3. REQUEST TYPE
    request_type = "UNKNOWN"
    if any(w in query for w in ["refund", "money back", "reimbursement", "cash back"]):
        request_type = "REFUND"
    elif "return" in query:
        request_type = "RETURN"
    elif any(w in query for w in ["replace", "replacement", "swap"]):
        request_type = "REPLACEMENT"
    elif "cancel" in query:
        request_type = "CANCEL"
    elif any(w in query for w in ["where is", "not received", "delivery", "late"]):
        request_type = "TRACK"

    # 4. FLOW TYPE
    flow_type = "GENERAL_SUPPORT"
    if derived_flags.get("has_delivery") is False:
        flow_type = "PRE_DELIVERY"
    elif intent in ["RETURN_REQUEST", "REFUND_REQUEST", "REPLACEMENT_REQUEST"]:
        flow_type = "POST_DELIVERY"
    elif intent == "DELIVERY_ISSUE":
        flow_type = "DELIVERY_TRACKING"

    # 5. PRIORITY ENGINE
    priority = "NORMAL"
    if len(validation.get("hard_errors", [])) > 0:
        priority = "BLOCKED"
    elif "HIGH_VALUE_ORDER" in validation.get("system_notes", []):
        priority = "HIGH"
    elif derived_flags.get("multi_intent") is True:
        priority = "HIGH"
    elif issue_type == "DAMAGED":
        priority = "HIGH"

    # 6. CONFIDENCE SCORE
    confidence = 0.85
    if derived_flags.get("multi_intent") is True:
        confidence -= 0.2
    if issue_type == "UNKNOWN":
        confidence -= 0.2
    if derived_flags.get("has_issue_signal") is True:
        confidence += 0.05
    if len(validation.get("soft_errors", [])) > 0:
        confidence -= 0.1
        
    if confidence < 0.3:
        confidence = 0.3
    if confidence > 0.95:
        confidence = 0.95

    return {
        "intent": intent,
        "issue_type": issue_type,
        "request_type": request_type,
        "flow_type": flow_type,
        "priority": priority,
        "confidence": round(confidence, 2)
    }


# -----------------------------
# MAIN PIPELINE
# -----------------------------
def process(input_json):
    normalized = normalize(input_json)

    validation = validate(normalized)

    resolved = resolve_conflicts(normalized, validation)

    flags = derive_flags(normalized)

    state = build_state(normalized, validation, flags)

    safe = len(validation["hard_errors"]) == 0

    return {
        "order_id": normalized["order"].get("order_id", "UNKNOWN"),
        "normalized": normalized,
        "validation": {
            "safe_to_process": safe,
            "hard_errors": validation["hard_errors"],
            "soft_errors": validation["soft_errors"],
            "conflicts": validation["conflicts"],
            "policy_flags": validation["policy_flags"]
        },
        "resolved_conflicts": resolved,
        "derived_flags": flags,
        "system_notes": validation["system_notes"],
        "state": state
    }


# -----------------------------
# TEST RUN (SAFE)
# -----------------------------
if __name__ == "__main__":
    with open("input.json", "r") as f:
        data = json.load(f)

    results = []
    for item in data:
        results.append(process(item))
    
    with open("output_state.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Processed {len(results)} items successfully. output_state.json generated.")