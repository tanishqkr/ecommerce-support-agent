import os
import json
import logging
from typing import Dict, Any, List
from groq import Groq
import time
from dotenv import load_dotenv

# STEP 1 — Load Environment
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename="logs/resolution_agent.log"
)

# STEP 3 — Initialize 
client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"

# STEP 4 — CREATE STRICT SYSTEM PROMPT
SYSTEM_PROMPT = """
You are a STRICT resolution generator for an e-commerce support system.

Your MISSION:
Translate a system-generated decision and policy context into a clear, helpful user explanation.

STRICT CONSTRAINTS:
1. You DO NOT make decisions. You ONLY explain the provided 'decision'.
2. Use ONLY the provided 'retrieved_policies' for grounding.
3. If 'supporting_chunks' are provided in the decision, prioritize those policies.
4. Do NOT use external knowledge, assumptions, or hallucinations.
5. Do NOT change the decision 'status' or 'action'.
6. If the context is insufficient to explain the decision, return a JSON with an error.
7. Tone: Professional, empathetic, Amazon-style customer support.

OUTPUT FORMAT (STRICT JSON ONLY):
{
  "decision_summary": "Short internal summary of the outcome.",
  "user_message": "The final message sent to the customer.",
  "justification": "Internal explanation of why this policy applies.",
  "citations": [
    {
      "policy_text": "Copy EXACT text from retrieved_policies without modification.",
      "source": "Source of the policy (e.g., Doc ID or name).",
      "section": "The section name from the policy."
    }
  ],
  "next_steps": "Clear instructions for the user (e.g., 'Check your email for the label').",
  "confidence_explanation": "Why the system is confident in this result."
}

Return ONLY valid JSON.
Do NOT include markdown, backticks, or any explanation outside JSON.
Your response MUST start with { and end with }.
Do NOT include any text before or after JSON.
Do NOT explain anything outside JSON.
All fields are mandatory and must be non-empty.
Citations must EXACTLY match text from retrieved_policies.
"""

def validate_resolution(input_payload: Dict[str, Any], resolution: Dict[str, Any]) -> bool:
    """
    STEP 8 — VALIDATION LAYER (CRITICAL)
    Ensure decision is not changed and citations are grounded.
    """
    try:
        # 1. Decision NOT changed
        system_status = input_payload["decision"]["status"]
        user_message = resolution.get("user_message", "").lower()
        
        # Hard Lock: Prevent LLM from contradicting system decision
        if system_status == "APPROVED" and ("reject" in user_message or "denied" in user_message):
            logging.error("Validation Failed: System APPROVED but LLM message suggests rejection.")
            return False
            
        if system_status == "REJECTED" and ("approved" in user_message or "accepted" in user_message):
            logging.error("Validation Failed: System REJECTED but LLM message suggests approval.")
            return False
            
        # 2. Citations exist
        if not resolution.get("citations"):
            logging.error("Validation Failed: No citations provided.")
            return False
            
        # 3. Improved Citation Validation (strip + lowercase + full substring match)
        policy_texts = [p["text"] for p in input_payload.get("retrieved_policies", [])]
        for citation in resolution["citations"]:
            cited_text = citation.get("policy_text", "")
            if not any(cited_text.strip().lower() in p.strip().lower() for p in policy_texts if p):
                logging.error(f"Validation Failed: Citation not found in source: {cited_text[:50]}...")
                return False
                
        # 4. No empty fields
        required_fields = ["decision_summary", "user_message", "justification", "citations", "next_steps"]
        for field in required_fields:
            if not resolution.get(field):
                logging.error(f"Validation Failed: Missing field {field}")
                return False
                
        logging.info("Validation Passed.")
        return True
    except Exception as e:
        logging.error(f"Validation Error: {str(e)}")
        return False

def generate_resolution(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for generating a resolution message.
    """
    logging.info(f"Input Payload: {json.dumps(input_payload, indent=2)}")

    # STEP 2 — HARD INPUT VALIDATION
    if "decision" not in input_payload:
        logging.error("Input Validation Failed: MISSING_DECISION")
        return {"error": "MISSING_DECISION"}
        
    retrieved_policies = input_payload.get("retrieved_policies", [])
    if not retrieved_policies:
        logging.error("Input Validation Failed: NO_RETRIEVAL_CONTEXT")
        return {"error": "NO_RETRIEVAL_CONTEXT"}

    # STEP 5 — BUILD FINAL PROMPT
    prompt = f"""
SYSTEM:
{SYSTEM_PROMPT}

INPUT:
{json.dumps(input_payload, indent=2)}

RETURN ONLY JSON.
"""

    logging.info(f"Generating resolution for Order: {input_payload.get('order_id')}")

    # STEP 6 — CALL  (with retry)
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Rate safety (avoid burst)
            time.sleep(1)

            response = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(input_payload)}
                ]
            )

            raw_text = response.choices[0].message.content.strip()
            logging.info(f"Raw LLM Output (Attempt {attempt + 1}): {raw_text}")
            print(f"RAW LLM OUTPUT (Attempt {attempt + 1}):\n{raw_text}\n")

            # Remove markdown formatting if present
            if raw_text.startswith("```"):
                lines = raw_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            # Extract first valid JSON block (strip anything before { and after })
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start != -1 and end > start:
                raw_text = raw_text[start:end]
            
            resolution = json.loads(raw_text)
            
            # STEP 8 — VALIDATION
            if validate_resolution(input_payload, resolution):
                logging.info(f"Resolution generated and validated for {input_payload.get('order_id')}")
                return resolution
            else:
                logging.warning(f"Validation failed on attempt {attempt + 1}")
                
        except json.JSONDecodeError as je:
            logging.error(f"JSON Parse Error (Attempt {attempt + 1}): {str(je)}")
        except Exception as e:
            logging.error(f"Groq Call Error (Attempt {attempt + 1}): {str(e)}")
            
    # FAILURE FORMAT
    return {
        "error": "INSUFFICIENT_CONTEXT",
        "message": "Unable to generate safe response after retries."
    }

def run_tests():
    """
    STEP 11 — TEST REQUIREMENTS
    """
    print("\n=== RUNNING RESOLUTION AGENT TESTS ===\n")
    
    # Mock data for testing
    test_cases = [
        {
            "name": "Damaged item -> refund",
            "payload": {
                "order_id": "TEST-001",
                "user_query": "The product arrived broken.",
                "normalized_query": "the product arrived broken.",
                "order": {"product_name": "Camera"},
                "state": {"intent": "PRODUCT_ISSUE", "issue_type": "DAMAGED"},
                "decision": {
                    "status": "APPROVED",
                    "action": "REFUND",
                    "reason": "Damaged item eligible for refund",
                    "supporting_chunks": ["CH-001"]
                },
                "retrieved_policies": [
                    {"text": "Damaged items are eligible for a full refund if reported within 48 hours.", "source": "PolicyV1", "section": "Damaged Goods", "chunk_id": "CH-001"}
                ]
            }
        },
        {
            "name": "Final sale -> rejected",
            "payload": {
                "order_id": "TEST-002",
                "user_query": "I want to return this dress.",
                "normalized_query": "i want to return this dress.",
                "order": {"product_name": "Dress", "is_final_sale": True},
                "state": {"intent": "RETURN_REQUEST", "issue_type": "UNKNOWN"},
                "decision": {
                    "status": "REJECTED",
                    "action": "NONE",
                    "reason": "Item is final sale",
                    "supporting_chunks": ["CH-002"]
                },
                "retrieved_policies": [
                    {"text": "Final sale items cannot be returned or refunded.", "source": "PolicyV1", "section": "Final Sale", "chunk_id": "CH-002"}
                ]
            }
        },
        {
            "name": "Perishable expired -> rejected",
            "payload": {
                "order_id": "TEST-003",
                "user_query": "The milk was bad but I forgot to tell you.",
                "normalized_query": "the milk was bad but i forgot to tell you.",
                "order": {"product_name": "Milk", "is_perishable": True},
                "state": {"intent": "PRODUCT_ISSUE", "issue_type": "DAMAGED"},
                "decision": {
                    "status": "REJECTED",
                    "action": "NONE",
                    "reason": "Perishable item outside of return window",
                    "supporting_chunks": ["CH-003"]
                },
                "retrieved_policies": [
                    {"text": "Perishable items outside the delivery window are not eligible for return.", "source": "PolicyV1", "section": "Perishables", "chunk_id": "CH-003"}
                ]
            }
        },
        {
            "name": "Delivery issue -> tracking",
            "payload": {
                "order_id": "TEST-004",
                "user_query": "Where is my package?",
                "normalized_query": "where is my package?",
                "order": {"product_name": "Headphones"},
                "state": {"intent": "DELIVERY_ISSUE", "issue_type": "NOT_DELIVERED"},
                "decision": {
                    "status": "ESCALATE",
                    "action": "TRACK",
                    "reason": "Order requires tracking based on delivery status",
                    "supporting_chunks": ["CH-004"]
                },
                "retrieved_policies": [
                    {"text": "If an item is not delivered, escalate to tracking for shipment status.", "source": "PolicyV1", "section": "Delivery", "chunk_id": "CH-004"}
                ]
            }
        },
        {
            "name": "Size issue -> return",
            "payload": {
                "order_id": "TEST-005",
                "user_query": "The shoes are too small.",
                "normalized_query": "the shoes are too small.",
                "order": {"product_name": "Shoes"},
                "state": {"intent": "RETURN_REQUEST", "issue_type": "SIZE_ISSUE"},
                "decision": {
                    "status": "APPROVED",
                    "action": "RETURN",
                    "reason": "Size issue qualifies for return",
                    "supporting_chunks": ["CH-005"]
                },
                "retrieved_policies": [
                    {"text": "Shoes with size issues can be returned for a full refund.", "source": "PolicyV1", "section": "Returns", "chunk_id": "CH-005"}
                ]
            }
        },
        {
            "name": "Missing policy -> failure",
            "payload": {
                "order_id": "TEST-006",
                "user_query": "I am not happy.",
                "decision": {
                    "status": "REVIEW",
                    "action": "NONE",
                    "reason": "Missing policy context",
                    "supporting_chunks": []
                },
                "retrieved_policies": []
            }
        }
    ]

    for case in test_cases:
        print(f"Testing Case: {case['name']}")
        result = generate_resolution(case['payload'])
        if "error" in result:
            print(f"Outcome: Expected Failure/Error - {result['error']}")
        else:
            print(f"Outcome: SUCCESS")
            print(f"User Message: {result['user_message'][:100]}...")
            print(f"Source Cited: {result['citations'][0]['source']}")
        print("-" * 40)

def run_integration_test():
    """
    NEW: Integration Test simulating realistic pipeline output.
    """
    print("\n=== RUNNING INTEGRATION TEST ===\n")
    
    payload = {
        "order_id": "INT-999",
        "user_query": "I received my camera but the lens is cracked. I want a refund.",
        "order": {"product_name": "Pro Camera", "price": 1200},
        "decision": {
            "status": "APPROVED",
            "action": "REFUND",
            "reason": "Damaged high-value item qualifies for refund",
            "supporting_chunks": ["POL-CAM-001"]
        },
        "retrieved_policies": [
            {
                "text": "Customers who receive a damaged item are eligible for a full refund if reported within 48 hours of delivery.",
                "source": "Returns_Policy_v2",
                "section": "Damaged Goods",
                "chunk_id": "POL-CAM-001"
            }
        ]
    }

    result = generate_resolution(payload)
    
    if "error" in result:
        print(f"Integration Test FAILED: {result['error']}")
    else:
        print("Integration Test SUCCESS")
        print(f"Decision Summary: {result.get('decision_summary')}")
        print(f"User Message: {result.get('user_message')}")
        print(f"Citations: {json.dumps(result.get('citations'), indent=2)}")

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")

    print("Resolution Agent Ready — Running Demo Query...\n")

    user_payload = {
        "order_id": "LIVE-001",
        "user_query": "My product arrived damaged, I want a refund",
        "normalized_query": "product arrived damaged want refund",
        "order": {"product_name": "Camera"},
        "state": {"intent": "PRODUCT_ISSUE", "issue_type": "DAMAGED"},
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

    result = generate_resolution(user_payload)

    print("=== FINAL OUTPUT ===\n")
    print(json.dumps(result, indent=2))