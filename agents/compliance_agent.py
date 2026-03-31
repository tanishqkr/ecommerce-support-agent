import logging
import json

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename="logs/compliance_agent.log"
)

# ─────────────────────────────────────────────
# REQUIRED FIELDS IN A VALID RESOLUTION OUTPUT
# ─────────────────────────────────────────────
REQUIRED_FIELDS = [
    "decision_summary",
    "user_message",
    "justification",
    "citations",
    "next_steps",
    "confidence_explanation",
]

# Words that signal a possible approval or rejection in the user_message
APPROVAL_SIGNALS = ["approved", "accepted"]
REJECTION_SIGNALS = ["reject", "denied"]


def run_compliance_check(input_payload: dict, resolution_output: dict) -> dict:
    """
    Phase 8 — Compliance Agent
    Fully deterministic, rule-based compliance verification.
    No LLM, no API calls.

    Returns:
        {
            "status": "PASS" | "FAIL",
            "issues": [...],
            "confidence_score": float (0.0 – 1.0)
        }
    """
    issues = []

    # ─────────────────────────────────────────
    # CHECK 1 — DECISION CONSISTENCY
    # ─────────────────────────────────────────
    try:
        decision_status = input_payload["decision"]["status"]
        user_message = resolution_output.get("user_message", "").lower()

        if decision_status == "APPROVED":
            if any(word in user_message for word in REJECTION_SIGNALS):
                issue = "Decision mismatch between system and response (APPROVED but message suggests rejection)"
                issues.append(issue)
                logging.error(f"CHECK 1 FAIL: {issue}")

        elif decision_status == "REJECTED":
            if any(word in user_message for word in APPROVAL_SIGNALS):
                issue = "Decision mismatch between system and response (REJECTED but message suggests approval)"
                issues.append(issue)
                logging.error(f"CHECK 1 FAIL: {issue}")

        logging.info(f"CHECK 1 — Decision Consistency: {'PASS' if not any('Decision mismatch' in i for i in issues) else 'FAIL'}")

    except KeyError as e:
        issue = f"CHECK 1 ERROR — Missing key in input_payload: {e}"
        issues.append(issue)
        logging.error(issue)

    # ─────────────────────────────────────────
    # CHECK 2 — CITATION EXISTENCE
    # ─────────────────────────────────────────
    citations = resolution_output.get("citations", [])
    if not citations:
        issue = "Missing citations"
        issues.append(issue)
        logging.error(f"CHECK 2 FAIL: {issue}")
    else:
        logging.info("CHECK 2 — Citation Existence: PASS")

    # ─────────────────────────────────────────
    # CHECK 3 — CITATION GROUNDING
    # ─────────────────────────────────────────
    policy_texts = [p["text"] for p in input_payload.get("retrieved_policies", []) if p.get("text")]

    for citation in citations:
        cited_text = citation.get("policy_text", "").strip().lower()
        if not cited_text:
            issue = "Citation has empty policy_text"
            issues.append(issue)
            logging.error(f"CHECK 3 FAIL: {issue}")
            continue

        grounded = any(cited_text in p.strip().lower() for p in policy_texts)
        if not grounded:
            issue = f"Citation not grounded in retrieved policies: \"{citation.get('policy_text', '')[:60]}...\""
            issues.append(issue)
            logging.error(f"CHECK 3 FAIL: {issue}")

    if not any("Citation not grounded" in i or "Citation has empty" in i for i in issues):
        logging.info("CHECK 3 — Citation Grounding: PASS")

    # ─────────────────────────────────────────
    # CHECK 4 — REQUIRED FIELDS
    # ─────────────────────────────────────────
    for field in REQUIRED_FIELDS:
        value = resolution_output.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            issue = f"Missing required field: {field}"
            issues.append(issue)
            logging.error(f"CHECK 4 FAIL: {issue}")

    if not any("Missing required field" in i for i in issues):
        logging.info("CHECK 4 — Required Fields: PASS")

    # ─────────────────────────────────────────
    # CHECK 5 — LIGHTWEIGHT HALLUCINATION CHECK
    # Flags if justification is much longer than policy context
    # or contains no keywords from any policy text.
    # ─────────────────────────────────────────
    justification = resolution_output.get("justification", "").lower()
    policy_combined = " ".join(policy_texts).lower()

    hallucination_flagged = False

    if justification and policy_combined:
        # Heuristic 1: Justification is more than 3x longer than total policy text
        if len(justification) > 3 * len(policy_combined):
            hallucination_flagged = True

        # Heuristic 2: Less than 2 meaningful words in justification appear in policies
        meaningful_words = [
            w for w in justification.split()
            if len(w) > 4 and w.isalpha()
        ]
        overlap_count = sum(1 for w in meaningful_words if w in policy_combined)
        if meaningful_words and overlap_count < 2:
            hallucination_flagged = True

    if hallucination_flagged:
        issue = "Possible hallucination in justification"
        issues.append(issue)
        logging.warning(f"CHECK 5 WARNING: {issue}")
    else:
        logging.info("CHECK 5 — Hallucination Check: PASS")

    # ─────────────────────────────────────────
    # CHECK 6 — BUILD FINAL STATUS + CONFIDENCE
    # ─────────────────────────────────────────
    status = "PASS" if not issues else "FAIL"
    confidence_score = max(0.0, round(1.0 - 0.2 * len(issues), 2))

    result = {
        "status": status,
        "issues": issues,
        "confidence_score": confidence_score,
    }

    logging.info(f"COMPLIANCE RESULT — Status: {status} | Score: {confidence_score} | Issues: {len(issues)}")

    # Console summary
    print(f"\n[Compliance] Status: {status}")
    print(f"[Compliance] Confidence Score: {confidence_score}")
    if issues:
        print("[Compliance] Issues Found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("[Compliance] No issues found.")

    return result


# ─────────────────────────────────────────────────────────────
# DEMO TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    if not os.path.exists("logs"):
        os.makedirs("logs")

    print("Running compliance test...\n")

    # --- SAMPLE PASSING CASE ---
    sample_payload = {
        "order_id": "LIVE-001",
        "decision": {
            "status": "APPROVED",
            "action": "REFUND",
            "reason": "Damaged item eligible",
            "supporting_chunks": ["CH-001"]
        },
        "retrieved_policies": [
            {
                "text": "Damaged items are eligible for a full refund if reported within 48 hours.",
                "source": "PolicyV1",
                "section": "Damaged Goods"
            }
        ]
    }

    sample_resolution = {
        "decision_summary": "Refund approved for damaged Camera.",
        "user_message": "We're sorry to hear your Camera arrived damaged. Your refund has been approved and will be processed shortly.",
        "justification": "The policy states that damaged items are eligible for a full refund if reported within 48 hours.",
        "citations": [
            {
                "policy_text": "Damaged items are eligible for a full refund if reported within 48 hours.",
                "source": "PolicyV1",
                "section": "Damaged Goods"
            }
        ],
        "next_steps": "Please allow 3-5 business days for the refund to be credited to your original payment method.",
        "confidence_explanation": "The system is confident because the damage was reported and the policy directly applies."
    }

    result = run_compliance_check(sample_payload, sample_resolution)

    print("\n=== COMPLIANCE CHECK RESULT ===\n")
    print(json.dumps(result, indent=2))

    # --- SAMPLE FAILING CASE ---
    print("\n" + "=" * 50)
    print("Running FAILING case (missing citations + decision mismatch)...\n")

    bad_resolution = {
        "decision_summary": "Request reviewed.",
        "user_message": "Your request has been denied.",   # APPROVED but says denied
        "justification": "We reviewed your case.",
        "citations": [],                                    # Empty citations
        "next_steps": "Contact support.",
        "confidence_explanation": ""                        # Empty field
    }

    bad_result = run_compliance_check(sample_payload, bad_resolution)

    print("\n=== COMPLIANCE CHECK RESULT (FAILING CASE) ===\n")
    print(json.dumps(bad_result, indent=2))
