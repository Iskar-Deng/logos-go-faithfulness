#!/usr/bin/env python3
"""Build compressed JSON data for the rollout tree viewer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert rollout tree JSONL into viewer JSON.")
    parser.add_argument("input_jsonl", help="Parsed rollout tree JSONL")
    parser.add_argument("output_json", help="Viewer JSON array")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of rows to write")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output JSON")
    args = parser.parse_args()

    rows = read_jsonl(Path(args.input_jsonl))
    if args.limit is not None:
        rows = rows[: args.limit]

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.pretty:
        payload = json.dumps(rows, ensure_ascii=False, indent=2)
    else:
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    output_path.write_text(payload, encoding="utf-8")

    branch_count = sum(len(row.get("tree", {}).get("children", [])) for row in rows)
    move_count = sum(row.get("parse_metadata", {}).get("variation_move_count", 0) for row in rows)
    print(f"Built viewer data: {len(rows)} rows; {branch_count} root branches; {move_count} moves")
    print(output_path.resolve())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


if __name__ == "__main__":
    main()
