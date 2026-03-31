import os

base_path = "/Users/tanishporwal/Desktop/ecommerce_agent/dataset/cleaned/"
mapping = {
    "ajio_fees_payments_policy.txt": "synthetic_faq.txt",
    "ajio_returns_refunds_policy.txt": "synthetic_returns.txt",
    "ajio_terms_and_conditions.txt": "synthetic_terms.txt",
    "amazon_faq_rag_refined.txt": "amazon_faq.txt",
    "amazon_refund_policy_rag_refined.txt": "amazon_refund.txt",
    "amazon_returns_policy_rag_refined.txt": "amazon_returns.txt",
    "consumer_protection_act_2019.txt": "legal_consumer_law.txt",
    "damaged_defective_goods_policy.txt": "synthetic_damaged_goods.txt",
    "ecommerce_rules_2020.txt": "legal_ecommerce_rules.txt",
    "final_sale_policy.txt": "synthetic_final_sale.txt",
    "flipkart_returns_policy_rag.txt": "flipkart_returns.txt",
    "flipkart_shipping_policy_rag.txt": "flipkart_shipping.txt",
    "hygiene_sensitive_products_policy.txt": "synthetic_hygiene.txt",
    "myntra_faq_rag.txt": "myntra_faq.txt",
    "myntra_terms_rag.txt": "myntra_terms.txt",
    "perishable_goods_policy.txt": "synthetic_perishable.txt"
}

for old_name, new_name in mapping.items():
    old_path = os.path.join(base_path, old_name)
    new_path = os.path.join(base_path, new_name)
    if os.path.exists(old_path):
        print(f"Renaming {old_name} to {new_name}")
        os.rename(old_path, new_path)
    else:
        print(f"File {old_name} not found or already renamed.")
