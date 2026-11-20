import json


def parse_detect_secrets():
    path = "docs/security/scan-output/detect-secrets-report.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", {})
        print(f"detect-secrets found results in {len(results)} files:")
        for f, items in results.items():
            types = [it.get("type") for it in items]
            lines = [it.get("line_number") for it in items]
            print(f"  {f}: lines {lines} -> {types}")
    except Exception as e:
        print(f"Error reading {path}: {e}")


if __name__ == "__main__":
    parse_detect_secrets()
