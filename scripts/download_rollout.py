#!/usr/bin/env python3
"""Download LoGos-Rollout data from Hugging Face."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DATASET = "YichuanMa/LoGos-Rollout-1K"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download LoGos rollout data.")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="Hugging Face dataset id")
    parser.add_argument("--split", default="train", help="Dataset split to load")
    parser.add_argument("--output", default="data/raw/logos_rollout_1k_all.json")
    parser.add_argument("--sample-output", default="data/raw/logos_rollout_1k_first3.json")
    parser.add_argument("--sample-size", type=int, default=3)
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Missing Python dependency: datasets. Install with "
            "`python3 -m pip install -r requirements.txt`."
        ) from exc

    dataset = load_dataset(args.dataset, split=args.split)
    rows = [normalize_record(record, index) for index, record in enumerate(dataset)]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.sample_output:
        sample_path = Path(args.sample_output)
        sample_path.parent.mkdir(parents=True, exist_ok=True)
        sample_path.write_text(
            json.dumps(rows[: args.sample_size], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"Downloaded {len(rows)} rows from {args.dataset}/{args.split}")
    print(output_path.resolve())
    if args.sample_output:
        print(Path(args.sample_output).resolve())


def normalize_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    row = dict(record)
    row.setdefault("id", str(index))
    if "messages" in row and "message" not in row:
        row["message"] = row.pop("messages")
    return row


if __name__ == "__main__":
    main()
