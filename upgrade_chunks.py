import json

def main():
    with open("dataset/chunks_v2.json", "r") as f:
        chunks = json.load(f)

    for chunk in chunks:
        source = chunk.get("source", "").title()
        section = chunk.get("section", "")
        text = chunk.get("text", "")
        if source.lower() == "amazon":
            source = "Amazon"
        elif source.lower() == "flipkart":
            source = "Flipkart"
        elif source.lower() == "myntra":
            source = "Myntra"
        # Just use title() as safe default if it isn't one of the known ones
        
        new_text = f"[Source: {source} | Section: {section}] {text}"
        chunk["embedding_ready_text"] = new_text

    with open("dataset/chunks_v3.json", "w") as f:
        json.dump(chunks, f, indent=2)

    print(f"Successfully upgraded {len(chunks)} chunks to chunks_v3.json")

if __name__ == "__main__":
    main()
