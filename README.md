# logos-go-faithfulness

Tools for turning LoGos Go rollout explanations into a structured, SGF-like tree that can be inspected and later verified.

The current pipeline normalizes each rollout sample into:

```text
position
  -> variation tree
      -> move
      -> term
      -> comment
```

The parser is mechanical and no-lexicon: it does not maintain a list of Go terms. It extracts move anchors, surface text spans, parentheses, and branch structure from the rollout text.

## Contents

- `scripts/download_rollout.py`: download `YichuanMa/LoGos-Rollout-1K` from Hugging Face.
- `scripts/parse_rollout_tree.py`: parse raw rollout JSON into tree JSONL.
- `scripts/build_viewer_data.py`: convert parsed JSONL into compact JSON for the viewer.
- `public/rollout.html`: local viewer for parsed rollout trees.
- `src/gogame.js`: Go board replay, legality checks, and coordinate conversion.
- `data/raw/`: raw rollout data. Only the tiny first-3 sample is tracked.
- `data/processed/`: parsed JSONL outputs, ignored by git.
- `public/data/`: viewer JSON outputs, ignored by git.

## Setup

```bash
npm install
python3 -m pip install -r requirements.txt
```

The Python dependency is only needed for downloading the Hugging Face dataset. Parsing existing local JSON does not require `datasets`.

## Prepare Data

If the raw rollout file is already present:

```bash
npm run prepare:rollout
```

For the tiny tracked sample:

```bash
npm run prepare:rollout:first3
```

To download the full dataset first:

```bash
npm run download:rollout
npm run prepare:rollout
```

## Run Viewer

```bash
npm start
```

Open:

```text
http://127.0.0.1:4173/rollout.html
```

If the port is already in use:

```bash
PORT=4174 npm start
```

Then open:

```text
http://127.0.0.1:4174/rollout.html
```

## Parsed Format

Each JSONL row has this shape:

```json
{
  "sample_id": "0",
  "source": "YichuanMa/LoGos-Rollout-1K",
  "position": {
    "move_count": 21,
    "next_color": "O",
    "moves": [
      {"ply": 1, "color": "X", "coord": "Q16", "raw": "1.X-Q16"}
    ],
    "board_matrix": [[0]]
  },
  "input": {"raw": "..."},
  "answer": {
    "color": "O",
    "coord": "C12",
    "winrate_text": "49.5%"
  },
  "tree": {
    "node_id": "0-root",
    "type": "root",
    "position_ply": 21,
    "children": []
  },
  "reasoning": {"raw": "..."},
  "parse_metadata": {
    "parser_version": "0.2-no-lexicon-surface-span",
    "parse_status": "ok",
    "variation_move_count": 14,
    "root_branch_count": 3,
    "low_confidence_move_count": 0,
    "warnings": []
  }
}
```

Each move node stores the extracted move, term span, and comment span:

```json
{
  "node_id": "0-b1-n2",
  "type": "move",
  "move": {
    "ply": 23,
    "color": "X",
    "coord": "C17",
    "raw": "23.X-C17点（黑棋开始骚扰右上）",
    "line_shape": "line_start"
  },
  "term": {
    "raw": "点",
    "source": "surface_cjk_run",
    "confidence": "high"
  },
  "comment": {
    "local": "黑棋开始骚扰右上",
    "parenthetical": "黑棋开始骚扰右上",
    "inline": null
  },
  "children": []
}
```

Parser rules:

- A move anchor (`23.X-C17`) is required for every tree node.
- A term is only taken from the surface CJK span immediately after the coordinate.
- Parenthesized text is stored as comment, not term.
- Dash text after a move is stored as inline comment.
- Inline narrative mentions are skipped from the tree and recorded in `warnings`.

## Check

```bash
npm test
```
