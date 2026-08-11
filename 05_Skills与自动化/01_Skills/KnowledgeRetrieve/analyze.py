"""Quick analysis helper for test results."""
import json, sys

def analyze(query, results_json):
    with open(results_json, "r", encoding="utf-8") as f:
        lines = f.readlines()
    # Skip [INFO] lines, find JSON start
    json_lines = []
    for line in lines:
        if line.startswith("[INFO]") or line.startswith("[WARN]"):
            continue
        json_lines.append(line)
    data = json.loads("".join(json_lines))

    print(f"\n{'='*70}")
    print(f"Query: {data['query']}")
    print(f"Understanding: {data['query_understanding']}")
    print(f"Status: {data['status']}")
    print(f"Candidates: {data['candidate_count']}, Hits: {data['hit_count']}")
    print(f"{'='*70}")

    books_seen = {}
    for h in data["hits"]:
        book = h["book"]
        books_seen[book] = books_seen.get(book, 0) + 1
        print(f"\n#{h['rank']} [{book}] [{h['knowledge_level']}] dim={h['dimension']}")
        stmt = h['statement'][:120]
        print(f"  {stmt}...")
        if h['evidence'] and h['evidence'][0] != 'absent':
            print(f"  Evidence: {h['evidence']}")
        if h['boundary'] and h['boundary'] != 'absent':
            print(f"  Boundary: {h['boundary']}")
        if h['counterevidence'] and h['counterevidence'] != 'absent':
            print(f"  Counterevidence: {h['counterevidence']}")
        print(f"  Score: {h['raw_score']:.3f}")

    print(f"\n--- Book distribution ---")
    for book, cnt in sorted(books_seen.items(), key=lambda x: -x[1]):
        print(f"  {book}: {cnt}")

    if data["gaps"]:
        print(f"\n--- Gaps ---")
        for g in data["gaps"]:
            print(f"  {g}")


if __name__ == "__main__":
    analyze(sys.argv[1], sys.argv[2])
