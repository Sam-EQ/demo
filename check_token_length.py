"""
Estimate token length of each record in output.json (for embedding without chunking).
Uses ~4 chars per token (OpenAI-style approximation). Reports records over 7k tokens.
"""
import json

# ~4 characters per token for English/JSON (OpenAI embedding models)
CHARS_PER_TOKEN = 4
MAX_TOKENS = 7000

def main():
    with open("output.json", "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = [data]

    over_7k = []
    for rec in data:
        rec_id = rec.get("id") or rec.get("_id") or "?"
        text = json.dumps(rec, ensure_ascii=False)
        est_tokens = len(text) // CHARS_PER_TOKEN
        rec["_est_tokens"] = est_tokens
        if est_tokens > MAX_TOKENS:
            over_7k.append((rec_id, est_tokens))

    print(f"Total records: {len(data)}")
    print(f"Token limit checked: {MAX_TOKENS}")
    print(f"Records over {MAX_TOKENS} tokens: {len(over_7k)}")
    if over_7k:
        print("\nIDs over 7k tokens (id, estimated_tokens):")
        for rid, tok in sorted(over_7k, key=lambda x: -x[1]):
            print(f"  {rid}  ->  {tok}")
    else:
        print("\nNo records exceed 7k tokens.")

if __name__ == "__main__":
    main()
