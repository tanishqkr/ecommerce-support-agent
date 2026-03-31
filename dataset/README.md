# E-commerce Policy RAG Dataset

## 1. Dataset Overview
This dataset contains cleaned text documents representing various e-commerce policies, legal regulations, and synthetic decision rules. It is optimized for RAG (Retrieval-Augmented Generation) applications in the e-commerce domain.

## 2. Total Documents
Total Documents: 16

## 3. Sources Covered
* Amazon
* Flipkart
* Myntra
* Legal (Consumer Protection Act, E-commerce Rules)
* Synthetic (Generic/AI-generated policy rules)

## 4. Document Types
* FAQ
* Returns Policy
* Refund Policy
* Shipping Policy
* Terms and Conditions
* Consumer Law
* E-commerce Rules
* Perishable Goods Policy
* Hygiene/Sensitive Products Policy
* Final Sale Policy
* Damaged/Defective Goods Policy

## 5. Processing Steps
* **Conversion**: Raw PDFs and policy documents were converted into clean text format.
* **Refinement**: Documents were processed via RAG optimization to improve chunking and retrieval performance.
* **Atomization**: Policies were converted into atomic decision rules for precise rule-based answering.
* **Organization**: Files were renamed to a consistent `<source>_<type>.txt` convention with accompanying metadata.

## 6. Notes
* All sensitive data from original sources has been generalized or removed.
* This dataset is intended for research and development of e-commerce support agents.
* Metadata mapping is available in `metadata.json`.

---
Dataset Version: v1
Total Documents: 16
