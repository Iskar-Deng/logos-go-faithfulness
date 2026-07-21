#!/usr/bin/env python3
"""Normalize LoGos rollout responses into an SGF-like tree without term lexicons."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COORD_RE = r"[A-HJ-T](?:1[0-9]|[1-9])"
MOVE_RE = re.compile(rf"(?P<ply>\d{{1,3}})\.(?P<color>[XO])-?(?P<coord>{COORD_RE})(?!\d)")
USER_MOVE_RE = re.compile(rf"(?P<ply>\d+)\.(?P<color>[XO])-(?P<coord>{COORD_RE})(?!\d)")
TAG_RE = re.compile(r"<(?P<tag>reasoning|answer)>(?P<body>[\s\S]*?)</(?P=tag)>")
CJK_RUN_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+")
HEADING_PREFIX_RE = re.compile(r"^\s*(?:\d+\s*[\.、]\s*)?")

COLOR_TEXT_TO_CODE = {"黑": "X", "白": "O"}
OPEN_PARENS = {"(": ")", "（": "）"}
SEPARATORS = "-—–"


@dataclass
class Mention:
    ply: int
    color: str
    coord: str
    raw: str
    annotation: str
    annotation_source: str
    confidence: str
    parenthetical: str
    dash_comment: str
    start: int
    end: int
    line: str
    line_shape: str
    branch_intro: str


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert LoGos-Rollout JSON into no-lexicon SGF-like tree JSONL."
    )
    parser.add_argument("input_json", help="LoGos rollout dataset JSON")
    parser.add_argument("output_jsonl", help="Output JSONL tree file")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    input_path = Path(args.input_json).resolve()
    output_path = Path(args.output_jsonl).resolve()

    rows = load_rows(input_path)
    if args.limit is not None:
        rows = rows[: args.limit]

    normalized = [normalize_row(row, index) for index, row in enumerate(rows)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in normalized) + "\n",
        encoding="utf-8",
    )

    samples_with_moves = sum(1 for row in normalized if row["parse_metadata"]["variation_move_count"])
    branch_count = sum(len(row["tree"]["children"]) for row in normalized)
    move_count = sum(row["parse_metadata"]["variation_move_count"] for row in normalized)
    warning_count = sum(len(row["parse_metadata"]["warnings"]) for row in normalized)
    low_confidence = sum(row["parse_metadata"]["low_confidence_move_count"] for row in normalized)
    print(
        f"Prepared {len(normalized)} rows; "
        f"{samples_with_moves} with variations; "
        f"{branch_count} root branches; "
        f"{move_count} move nodes; "
        f"{low_confidence} low-confidence moves; "
        f"{warning_count} warnings"
    )
    print(output_path)


def load_rows(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("rows", raw) if isinstance(raw, dict) else raw
    return [row.get("row", row) if isinstance(row, dict) else row for row in rows]


def normalize_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    sample_id = str(row.get("id", index))
    user = get_content(row, "user")
    assistant = get_content(row, "assistant")
    tags = extract_tags(assistant)
    reasoning = tags.get("reasoning", "")
    answer_text = tags.get("answer", "")
    position_moves = parse_user_moves(user)
    board_matrix = parse_board_matrix(user)
    answer = parse_answer(answer_text)
    mentions, warnings = parse_variation_mentions(
        sample_id=sample_id,
        reasoning=reasoning,
        first_ply=len(position_moves) + 1,
    )
    tree = build_tree(sample_id, len(position_moves), mentions, warnings)

    expected_color = "X" if len(position_moves) % 2 == 0 else "O"
    if answer.get("color") and answer.get("color") != expected_color:
        warnings.append(
            {
                "type": "answer_turn_mismatch",
                "message": f"answer color {answer.get('color')} but position expects {expected_color}",
            }
        )

    low_confidence_count = sum(1 for mention in mentions if mention.confidence == "low")
    return {
        "sample_id": sample_id,
        "source": "YichuanMa/LoGos-Rollout-1K",
        "position": {
            "move_count": len(position_moves),
            "next_color": expected_color,
            "moves": position_moves,
            "board_matrix": board_matrix,
        },
        "input": {"raw": user},
        "answer": answer,
        "tree": tree,
        "reasoning": {"raw": reasoning},
        "parse_metadata": {
            "parser_version": "0.2-no-lexicon-surface-span",
            "parse_status": "ok" if not warnings else "ok_with_warnings",
            "variation_move_count": count_tree_moves(tree),
            "root_branch_count": len(tree["children"]),
            "low_confidence_move_count": low_confidence_count,
            "warnings": warnings,
        },
    }


def get_content(row: dict[str, Any], role: str) -> str:
    for message in row.get("message", []):
        if message.get("role") == role:
            return str(message.get("content", ""))
    return ""


def extract_tags(text: str) -> dict[str, str]:
    return {match.group("tag"): match.group("body").strip() for match in TAG_RE.finditer(text)}


def parse_user_moves(user_text: str) -> list[dict[str, Any]]:
    return [
        {
            "ply": int(match.group("ply")),
            "color": match.group("color"),
            "coord": match.group("coord"),
            "raw": match.group(0),
        }
        for match in USER_MOVE_RE.finditer(user_text)
    ]


def parse_board_matrix(user_text: str) -> list[list[int]] | None:
    marker = "当前盘面情况为:"
    start = user_text.find(marker)
    if start < 0:
        return None
    after_marker = user_text[start + len(marker) :]
    end = after_marker.find("\n其中1表示黑棋")
    if end < 0:
        return None
    try:
        board = json.loads(after_marker[:end].strip())
    except json.JSONDecodeError:
        return None
    if (
        isinstance(board, list)
        and len(board) == 19
        and all(isinstance(row, list) and len(row) == 19 for row in board)
    ):
        return board
    return None


def parse_answer(answer_text: str) -> dict[str, Any]:
    color_text = extract_boxed_value(answer_text, "下一步颜色")
    coord = extract_boxed_value(answer_text, "下一步位置")
    winrate = extract_boxed_value(answer_text, "下一步胜率")
    color = ""
    for text, code in COLOR_TEXT_TO_CODE.items():
        if text in color_text:
            color = code
            break
    return {
        "color_text": color_text,
        "color": color,
        "coord": coord if re.fullmatch(COORD_RE, coord or "") else "",
        "winrate_text": winrate,
        "raw": answer_text,
        "label": f"{color}-{coord}" if color and coord else "",
    }


def extract_boxed_value(text: str, label: str) -> str:
    match = re.search(rf"\\boxed\{{{re.escape(label)}\s*:\s*([^}}]+)\}}", text)
    return match.group(1).strip() if match else ""


def parse_variation_mentions(
    sample_id: str,
    reasoning: str,
    first_ply: int,
) -> tuple[list[Mention], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    mentions: list[Mention] = []
    skipped_mentions: list[dict[str, Any]] = []

    for line_start, line_end, line in iter_lines(reasoning):
        matches = [match for match in MOVE_RE.finditer(line) if int(match.group("ply")) >= first_ply]
        if not matches:
            continue
        line_shape = classify_line(matches, line)
        if line_shape == "mixed_inline" and len(matches) == 1:
            match = matches[0]
            skipped_mentions.append(
                {
                    "reason": "inline_narrative",
                    "raw": match.group(0),
                    "line": line.strip(),
                    "text_span": {
                        "start": line_start + match.start(),
                        "end": line_start + match.end(),
                    },
                }
            )
            continue

        for index, match in enumerate(matches):
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            segment = line[match.end() : next_start]
            parsed = parse_segment(segment)
            shape = "multi_move_line" if line_shape == "mixed_inline" and len(matches) > 1 else line_shape
            confidence = estimate_confidence(shape, parsed)
            raw_end_in_line = match.end() + parsed["consumed"]
            branch_intro = find_branch_intro(reasoning, line_start + match.start(), match.group("coord"), first_ply, int(match.group("ply")))
            mentions.append(
                Mention(
                    ply=int(match.group("ply")),
                    color=match.group("color"),
                    coord=match.group("coord"),
                    raw=line[match.start() : raw_end_in_line],
                    annotation=parsed["term"],
                    annotation_source=parsed["term_source"],
                    confidence=confidence,
                    parenthetical=parsed["parenthetical"],
                    dash_comment=parsed["dash_comment"],
                    start=line_start + match.start(),
                    end=line_start + raw_end_in_line,
                    line=line.strip(),
                    line_shape=shape,
                    branch_intro=branch_intro,
                )
            )

    if not mentions:
        warnings.append(
            {
                "type": "no_variation_moves",
                "message": f"sample {sample_id} has no parsed variation moves in reasoning",
            }
        )
    if skipped_mentions:
        warnings.append(
            {
                "type": "skipped_inline_narrative_moves",
                "count": len(skipped_mentions),
                "mentions": skipped_mentions,
            }
        )
    return mentions, warnings


def iter_lines(text: str):
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        yield offset, offset + len(stripped), stripped
        offset += len(line)


def classify_line(matches: list[re.Match[str]], line: str) -> str:
    prefix = line[: matches[0].start()]
    stripped = prefix.strip()
    if not stripped:
        return "line_start"
    if stripped in SEPARATORS or re.fullmatch(r"[-—–]\s*", prefix):
        return "bullet"
    return "mixed_inline"


def parse_segment(segment: str) -> dict[str, Any]:
    consumed = len(segment) - len(segment.lstrip())
    segment = segment.lstrip()
    term = ""
    term_source = ""
    parenthetical = ""
    dash_comment = ""

    if not segment:
        return parsed_segment(term, term_source, parenthetical, dash_comment, consumed)

    if segment[0] in OPEN_PARENS:
        content, paren_end = consume_parenthetical(segment, 0)
        if content:
            parenthetical = content
            consumed += paren_end
            trailing = segment[paren_end:].strip()
            dash_comment = consume_dash_comment(trailing)
            if dash_comment:
                consumed += len(segment[paren_end:])
        return parsed_segment(term, term_source, parenthetical, dash_comment, consumed)

    match = CJK_RUN_RE.match(segment)
    if match:
        term = match.group(0)
        term_source = "surface_cjk_run"
        consumed += match.end()
        trailing = segment[match.end() :].lstrip()
        consumed += len(segment[match.end() :]) - len(trailing)
        if trailing and trailing[0] in OPEN_PARENS:
            content, paren_end = consume_parenthetical(trailing, 0)
            if content:
                parenthetical = content
                consumed += paren_end
        else:
            dash_comment = consume_dash_comment(trailing)
            if dash_comment:
                consumed += len(trailing)

    return parsed_segment(term, term_source, parenthetical, dash_comment, consumed)


def parsed_segment(
    term: str,
    term_source: str,
    parenthetical: str,
    dash_comment: str,
    consumed: int,
) -> dict[str, Any]:
    return {
        "term": term,
        "term_source": term_source,
        "parenthetical": parenthetical,
        "dash_comment": dash_comment,
        "consumed": consumed,
    }


def consume_parenthetical(text: str, start: int) -> tuple[str, int]:
    opener = text[start]
    closer = OPEN_PARENS[opener]
    end = text.find(closer, start + 1)
    if end < 0:
        return "", start
    return text[start + 1 : end].strip(), end + 1


def consume_dash_comment(text: str) -> str:
    stripped = text.strip()
    if stripped and stripped[0] in SEPARATORS:
        return stripped[1:].strip()
    return ""


def estimate_confidence(shape: str, parsed: dict[str, Any]) -> str:
    term = parsed["term"]
    if parsed["term_source"] == "surface_cjk_run" and term and len(term) <= 6:
        return "high"
    if parsed["parenthetical"]:
        return "medium"
    return "low"


def find_branch_intro(
    text: str,
    move_start: int,
    coord: str,
    first_ply: int,
    ply: int,
) -> str:
    if ply != first_ply:
        return ""
    window_start = max(0, move_start - 900)
    before = text[window_start:move_start]
    lines = [line.strip() for line in before.splitlines() if line.strip()]
    for line in reversed(lines[-14:]):
        if len(line) > 160:
            continue
        if MOVE_RE.search(line):
            continue
        if coord not in line:
            continue
        return HEADING_PREFIX_RE.sub("", line).strip()
    return ""


def build_tree(
    sample_id: str,
    position_ply: int,
    mentions: list[Mention],
    warnings: list[dict[str, Any]],
) -> dict[str, Any]:
    root = {
        "node_id": f"{sample_id}-root",
        "type": "root",
        "position_ply": position_ply,
        "children": [],
    }
    current_path: list[dict[str, Any]] = []
    first_ply = position_ply + 1
    branch_index = 0

    for mention in mentions:
        if not current_path or mention.ply == first_ply or mention.ply <= current_path[-1]["move"]["ply"]:
            branch_index += 1
            node = make_node(sample_id, branch_index, 1, mention)
            root["children"].append(node)
            current_path = [node]
            continue

        previous_ply = current_path[-1]["move"]["ply"]
        if mention.ply != previous_ply + 1:
            warnings.append(
                {
                    "type": "ply_gap",
                    "message": f"branch {branch_index} jumps from {previous_ply} to {mention.ply}",
                    "text_span": {"start": mention.start, "end": mention.end},
                }
            )
        node = make_node(sample_id, branch_index, len(current_path) + 1, mention)
        current_path[-1]["children"].append(node)
        current_path.append(node)

    return root


def make_node(sample_id: str, branch_index: int, depth: int, mention: Mention) -> dict[str, Any]:
    comments = {
        "branch": mention.branch_intro or None,
        "local": mention.parenthetical or mention.dash_comment or None,
        "parenthetical": mention.parenthetical or None,
        "inline": mention.dash_comment or None,
    }
    return {
        "node_id": f"{sample_id}-b{branch_index}-n{depth}",
        "type": "move",
        "move": {
            "ply": mention.ply,
            "color": mention.color,
            "coord": mention.coord,
            "raw": mention.raw,
            "text_span": {"start": mention.start, "end": mention.end},
            "line": mention.line,
            "line_shape": mention.line_shape,
        },
        "term": {
            "raw": mention.annotation or None,
            "source": mention.annotation_source or None,
            "confidence": mention.confidence,
        },
        "comment": comments,
        "children": [],
    }


def count_tree_moves(node: dict[str, Any]) -> int:
    return sum(count_tree_moves(child) for child in node.get("children", [])) + (
        1 if node.get("type") == "move" else 0
    )


if __name__ == "__main__":
    main()
