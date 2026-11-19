
import json
import os
import re
import sys
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher


ROOT = Path(__file__).resolve().parent
REFERENCE = "en.json"
SIMILARITY_THRESHOLD = 0.80
PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
IS_CI = os.getenv("GITHUB_ACTIONS") == "true"


def report(level, message, filename=None):
    icon = {
        "error": "❌",
        "warning": "⚠️",
        "notice": "ℹ️"
    }.get(level, "")

    print(f"{icon} {message}")

    if IS_CI:
        escaped = (
            message.replace("%", "%25")
            .replace("\r", "%0D")
            .replace("\n", "%0A")
        )

        location = ""

        if filename:
            safe_file = (
                filename.replace("%", "%25")
                .replace("\r", "%0D")
                .replace("\n", "%0A")
                .replace(":", "%3A")
                .replace(",", "%2C")
            )
            location = f" file={safe_file}"

        print(f"::{level}{location}::{escaped}")


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")

        result[key] = value

    return result


def load_translations(path):
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(
            file,
            object_pairs_hook=reject_duplicate_keys
        )

    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")

    translations = {}

    def collect(obj, prefix=""):
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                collect(value, full_key)
                continue

            if full_key in translations:
                raise ValueError(
                    f"Duplicate flattened key: {full_key}"
                )

            if not isinstance(value, str):
                raise ValueError(
                    f"Translation must be a string: {full_key}"
                )

            translations[full_key] = value

    collect(data)
    return translations


def find_similar(key, candidates):
    best_match = None
    best_score = SIMILARITY_THRESHOLD

    for candidate in sorted(candidates):
        score = SequenceMatcher(
            None, key, candidate
        ).ratio()

        if score >= SIMILARITY_THRESHOLD and (
            best_match is None or score > best_score
        ):
            best_match = candidate
            best_score = score

    return best_match, best_score


def get_placeholders(value):
    return Counter(PLACEHOLDER_PATTERN.findall(value))


def format_placeholders(placeholders):
    return ", ".join(
        f"{{{{{key}}}}} x{count}"
        for key, count in sorted(placeholders.items())
    )


def main():
    files = sorted(ROOT.glob("*.json"))
    translations = {}
    errors = 0

    print("=" * 60)
    print("Translation Validation")
    print(f"Reference: {REFERENCE}")
    print("=" * 60)

    if not (ROOT / REFERENCE).is_file():
        report("error", f"Reference file {REFERENCE} not found")
        return 1

    for path in files:
        try:
            translations[path.name] = load_translations(path)
        except (OSError, ValueError) as error:
            report("error", str(error), path.name)
            errors += 1

    if REFERENCE not in translations:
        return 1

    if len(translations) < 2:
        report("error", "No valid additional translation files found")
        return 1

    reference_keys = set(translations[REFERENCE])

    all_keys = set().union(
        *(set(values) for values in translations.values())
    )

    language_names = sorted(
        translations,
        key=lambda name: (name != REFERENCE, name)
    )

    print("\nLoaded translation files:")

    for filename in language_names:
        print(f"  - {filename}: {len(translations[filename])} keys")

    print(f"\nUnique keys across all languages: {len(all_keys)}")

    # --------------------------------------------------
    # Reference validation
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("1. Reference Validation")
    print("=" * 60)

    for filename in language_names:
        if filename == REFERENCE:
            continue

        keys = set(translations[filename])
        missing = reference_keys - keys
        extra = keys - reference_keys

        print(f"\n--- {filename} ---")

        if not missing and not extra:
            print("✅ All reference keys match")

        for key in sorted(missing):
            report("error", f"Missing key: {key}", filename)
            errors += 1

            match, score = find_similar(key, extra)

            if match:
                print(
                    f"  💡 Possible typo: {match} "
                    f"({score:.0%} similarity)"
                )

        for key in sorted(extra):
            report(
                "error",
                f"Key not present in {REFERENCE}: {key}",
                filename
            )
            errors += 1

            match, score = find_similar(key, missing)

            if match:
                print(
                    f"  💡 Did you mean: {match} "
                    f"({score:.0%} similarity)?"
                )

    # --------------------------------------------------
    # Global cross-reference validation
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("2. Global Cross-Reference Validation")
    print("=" * 60)

    inconsistent_keys = 0

    for key in sorted(all_keys):
        present = [
            name for name in language_names
            if key in translations[name]
        ]

        missing = [
            name for name in language_names
            if key not in translations[name]
        ]

        if not missing:
            continue

        inconsistent_keys += 1

        print(f"\n❌ Inconsistent key: {key}")
        print(f"  Present in: {', '.join(present)}")
        print(f"  Missing in: {', '.join(missing)}")
        print(f"  Coverage: {len(present)}/{len(language_names)}")

        if REFERENCE not in present:
            report(
                "error",
                f"Key exists in other languages but not in "
                f"{REFERENCE}: {key}",
                REFERENCE
            )
            errors += 1

    if inconsistent_keys == 0:
        print("✅ All languages contain identical keys")

    # --------------------------------------------------
    # Placeholder validation
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("3. Placeholder Validation")
    print("=" * 60)

    placeholder_errors = 0

    for key in sorted(all_keys):
        available = [
            name for name in language_names
            if key in translations[name]
        ]

        baseline = available[0]
        expected = get_placeholders(
            translations[baseline][key]
        )

        for filename in available[1:]:
            actual = get_placeholders(
                translations[filename][key]
            )

            missing = expected - actual
            extra = actual - expected

            if not missing and not extra:
                continue

            report(
                "error",
                f"Placeholder mismatch: {key} "
                f"(compared to {baseline})",
                filename
            )

            if missing:
                print(
                    "  Missing: "
                    + format_placeholders(missing)
                )

            if extra:
                print(
                    "  Unexpected: "
                    + format_placeholders(extra)
                )

            placeholder_errors += 1
            errors += 1

    if placeholder_errors == 0:
        print("✅ All placeholders match")

    # --------------------------------------------------
    # Summary
    # --------------------------------------------------

    print("\n" + "=" * 60)
    print("4. Summary")
    print("=" * 60)

    print(f"Translation files: {len(translations)}")
    print(f"Reference keys: {len(reference_keys)}")
    print(f"Unique keys: {len(all_keys)}")
    print(f"Inconsistent keys: {inconsistent_keys}")
    print(f"Placeholder errors: {placeholder_errors}")
    print(f"Total error reports: {errors}")

    if errors:
        print("\n❌ Translation validation failed")
        return 1

    print("\n✅ All translation files are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
