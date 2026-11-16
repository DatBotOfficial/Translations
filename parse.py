
import json
import sys
from pathlib import Path
from difflib import SequenceMatcher


def load_keys(path: str) -> set[str]:
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)

    keys = set()

    def collect(obj, prefix=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                collect(value, full_key)
        else:
            keys.add(prefix)

    collect(data)
    return keys


def find_similar_keys(
    missing: set[str],
    candidates: set[str],
    threshold: float = 0.75
) -> dict[str, tuple[str, float]]:
    matches = {}

    for key in missing:
        best_match = None
        best_score = threshold

        for candidate in candidates:
            score = SequenceMatcher(
                None, key, candidate
            ).ratio()

            if score > best_score:
                best_match = candidate
                best_score = score

        if best_match:
            matches[key] = (best_match, best_score)

    return matches


def print_missing(
    filename: str,
    source: str,
    missing: set[str],
    suggestions: dict[str, tuple[str, float]]
):
    if not missing:
        print(f"✅ No keys missing in {filename}")
        return

    print(
        f"\n❌ Keys missing in {filename} "
        f"(present in {source}): {len(missing)}"
    )

    for key in sorted(missing):
        print(f"  - {key}")

        if key in suggestions:
            match, score = suggestions[key]
            print(
                f"    💡 Did you mean: {match} "
                f"({score:.0%} similarity)?"
            )


def main():
    if len(sys.argv) != 3:
        print("Usage: python parse.py <file_a.json> <file_b.json>")
        sys.exit(1)

    file_a, file_b = sys.argv[1:3]

    try:
        keys_a = load_keys(file_a)
        keys_b = load_keys(file_b)
    except (OSError, json.JSONDecodeError) as error:
        print(f"❌ Error reading JSON: {error}")
        sys.exit(1)

    name_a = Path(file_a).name
    name_b = Path(file_b).name

    print(f"Comparing:\n  A = {name_a}\n  B = {name_b}")

    missing_in_b = keys_a - keys_b
    missing_in_a = keys_b - keys_a

    suggestions_b = find_similar_keys(
        missing_in_b, missing_in_a
    )
    suggestions_a = find_similar_keys(
        missing_in_a, missing_in_b
    )

    print_missing(
        name_b, name_a, missing_in_b, suggestions_b
    )
    print_missing(
        name_a, name_b, missing_in_a, suggestions_a
    )

    print(
        f"\nTotal keys: {name_a} = {len(keys_a)}, "
        f"{name_b} = {len(keys_b)}"
    )

    if missing_in_a or missing_in_b:
        sys.exit(1)

    print("\n✅ All translation keys match!")


if __name__ == "__main__":
    main()
