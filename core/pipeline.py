from phases.phase3_engine import process as run_state_engine
from phases.phase4_triage import process_triage as run_triage
from phases.phase5_retriever import run_phase5 as run_retrieval
from phases.phase6_rule_engine import evaluate_decision as run_rule_engine
from agents.resolution_agent import generate_resolution
from agents.compliance_agent import run_compliance_check

def run_full_pipeline(user_query: str):
    # 1. Normalize input
    normalized_query = user_query.lower()

    # 2. PHASE 3 — STATE ENGINE
    input_json = {
        "query": user_query,
        "order": {"product_name": "Unknown", "order_id": "PIPELINE-001"}
    }
    state_data = run_state_engine(input_json)
    state = state_data["state"]

    # 3. PHASE 4 — TRIAGE
    triage = run_triage(state_data)
    state_data["triage"] = triage

    # 4. PHASE 5 — RETRIEVAL
    retrieval_data = run_retrieval(state_data)
    retrieved_policies = retrieval_data.get("retrieval", [])

    # 5. PHASE 6 — RULE ENGINE
    decision = run_rule_engine(retrieval_data)

    # 6. BUILD INPUT PAYLOAD FOR RESOLUTION
    input_payload = {
        "order_id": "PIPELINE-001",
        "user_query": user_query,
        "normalized_query": normalized_query,
        "order": {
            "order_date": "2026-03-20",
            "delivery_date": "2026-03-25",
            "item_category": "apparel" if any(w in normalized_query for w in ("shirt", "cloth", "apparel", "dress", "jeans")) else "electronics",
            "fulfillment_type": "marketplace",
            "shipping_region": "India",
            "order_status": "delivered",
            "product_name": "Unknown"
        },
        "state": state,
        "decision": decision,
        "retrieved_policies": retrieved_policies
    }

    # 7. CLARIFYING QUESTIONS
    clarifying_questions = []
    if not input_payload.get("retrieved_policies"):
        clarifying_questions.append("Can you provide more details about the issue?")
    if input_payload["order"].get("order_status") is None:
        clarifying_questions.append("What is the current order status?")

    # 8. PHASE 7 — RESOLUTION
    resolution = generate_resolution(input_payload)

    # 9. PHASE 8 — COMPLIANCE
    compliance = run_compliance_check(input_payload, resolution)

    # 10. RETURN FINAL OUTPUT
    return {
        "resolution": resolution,
        "compliance": compliance,
        "decision": decision,
        "state": state,
        "clarifying_questions": clarifying_questions
    }
