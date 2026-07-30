#!/usr/bin/env python3
"""
Compare the key structure of two JSON files (e.g. locale files) and report
which keys exist in one file but not the other.

Usage:
    python compare_json_keys.py file_a.json file_b.json
"""

import json
import sys


def flatten_keys(data, prefix=""):
    """Recursively collect all dotted key paths from a nested dict."""
    keys = set()

    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                keys |= flatten_keys(value, path)
            else:
                keys.add(path)
    else:
        # Non-dict at top level, just add the prefix itself
        keys.add(prefix)

    return keys


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <file_a.json> <file_b.json>")
        sys.exit(1)

    file_a, file_b = sys.argv[1], sys.argv[2]

    data_a = load_json(file_a)
    data_b = load_json(file_b)

    keys_a = flatten_keys(data_a)
    keys_b = flatten_keys(data_b)

    only_in_a = sorted(keys_a - keys_b)
    only_in_b = sorted(keys_b - keys_a)

    print(f"Comparing:\n  A = {file_a}\n  B = {file_b}\n")

    if not only_in_a and not only_in_b:
        print("✅ Both files have identical key structures.")
        return

    if only_in_a:
        print(f"❌ Keys missing in {file_b} (present in {file_a}): {len(only_in_a)}")
        for key in only_in_a:
            print(f"  - {key}")
        print()

    if only_in_b:
        print(f"❌ Keys missing in {file_a} (present in {file_b}): {len(only_in_b)}")
        for key in only_in_b:
            print(f"  - {key}")
        print()

    total_a = len(keys_a)
    total_b = len(keys_b)
    print(f"Total keys: {file_a} = {total_a}, {file_b} = {total_b}")


if __name__ == "__main__":
    main()