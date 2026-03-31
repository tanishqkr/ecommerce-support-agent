from retriever import retrieve
import json

def test():
    queries = [
        "refund for damaged product",
        "non returnable items",
        "used item return policy",
        "perishable refund time"
    ]

    for q in queries:
        print(f"--- Query: '{q}' ---")
        try:
            res = retrieve(q, top_k=5)
            print(json.dumps(res, indent=2))
        except Exception as e:
            print(f"Error testing query '{q}': {e}")
        print("\n")

if __name__ == "__main__":
    test()
