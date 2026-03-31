# 🧠 E-Commerce Support Resolution Agent

A production-grade, multi-stage AI system designed to resolve e-commerce customer support tickets using **Retrieval-Augmented Generation (RAG)**, **deterministic decision-making**, and **automated compliance validation**.

---

## 🚀 Project Goal

This system solves the "hallucination problem" in AI customer support by separating **Decision Logic** from **Response Generation**.

> [!IMPORTANT]
> **Key Design Principle:**  
> Decisions are 100% deterministic (Rule Engine). The LLM is used effectively for explanation and empathy, but never for policy adjudication.

---

## 🏗️ System Architecture

The pipeline follows a strict linear flow to ensure auditability:

1.  **State Engine:** Normalization, spell-correction, and initial intent detection.
2.  **Triage:** Detects ambiguity, missing info, or conflicting data in the query.
3.  **Retriever:** Fetches relevant policy chunks using **FAISS** and **BGE-Large** embeddings.
4.  **Rule Engine:** Applies hard business logic (Final Sale, Perishables, etc.) to reach a status.
5.  **Resolution Agent:** Uses **LLaMA 3.1** to draft a response grounded in retrieved context.
6.  **Compliance Agent:** deterministic auditor that scans for hallucinations or decision mismatches.

---

## ⚙️ Tech Stack

*   **Models:** LLaMA 3.1 8B (via Groq), BAAI/bge-large-en-v1.5 (Embeddings)
*   **Database:** FAISS (Vector Store)
*   **Frontend:** Streamlit
*   **Orchestration:** Custom Python Pipeline (Safety-first design)
*   **Key Libraries:** `sentence-transformers`, `faiss-cpu`, `groq`, `python-dotenv`

---

## 📂 Project Structure

| Directory/File | Purpose |
| :--- | :--- |
| `agents/` | LLM-based agents (`resolution`, `compliance`) that handle text generation and auditing. |
| `phases/` | Deterministic pipeline stages (State Engine, Triage, Retriever, Rule Engine). |
| `core/` | Contains `pipeline.py`—the central orchestrator connecting all phases. |
| `data/` | Knowledge base (policies), FAISS index, and embedding artifacts. |
| `input.json` | High-fidelity test suite with 25+ real-world support scenarios. |
| `app.py` | The main Streamlit application entry point. |

---

## 🚀 Quick Start

### 1. Installation
Ensure you have Python 3.9+ installed.
```bash
# Clone the repository and install dependencies
pip install -r requirements.txt
```

### 2. Set up Environment
Create a `.env` file in the root directory and add your Groq API key:
```text
GROQ_API_KEY=your_key_here
```

### 3. Build the Index
Prepare the vector database from the policy documents:
```bash
python build_index.py
```

### 4. Run the Agent
Launch the interactive Streamlit dashboard:
```bash
streamlit run app.py
```

---

## 📥 IO Contracts

### Input Schema
```json
{
  "query": "My camera arrived with a cracked lens. I'd like a refund.",
  "order": {
    "order_id": "ORD-101",
    "product_name": "Pro Tablet",
    "is_final_sale": false,
    "return_window_days": 15
  }
}
```

### Output Schema
```json
{
  "decision": { "status": "APPROVED", "action": "REFUND" },
  "resolution": {
    "user_message": "...",
    "citations": [...],
    "justification": "..."
  },
  "compliance": { "status": "PASS", "confidence_score": 0.95 }
}
```

---

## 🧪 Engineering Highlights

*   **Zero Hallucination:** The Compliance Agent cross-checks every LLM-generated citation against the original source text.
*   **Conflict Resolution:** The State Engine resolves contradictions (e.g., if a system says an item is returnable but it's marked as Final Sale).
*   **Intent-Aware Retrieval:** The retriever filters and boosts chunks based on the detected intent (e.g., boosting 'Refund' policies if the user asks for money back).

---

## ⚠️ Limitations & Future Scope
*   **Current:** Stateless execution (no multi-turn memory).
*   **Planned:** Database integration for real-time order lookups.
*   **Planned:** Multi-language support for global e-commerce environments.

---

👨‍💻 **Author:** Tanish