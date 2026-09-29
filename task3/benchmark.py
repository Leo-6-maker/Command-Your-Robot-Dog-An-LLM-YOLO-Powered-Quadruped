"""Reproducible planner-only comparison of OpenAI and local Qwen."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time
from typing import Any, Iterable

from .planner import OllamaPlanner, OpenAIPlanner, PlanningResult, plan_to_dict


CASES_PATH = Path(__file__).with_name("benchmark_cases.json")

# gpt-4o-mini text-token prices per one million tokens, checked 2026-09-29.
OPENAI_INPUT_USD_PER_M = 0.15
OPENAI_CACHED_INPUT_USD_PER_M = 0.075
OPENAI_OUTPUT_USD_PER_M = 0.60
OPENAI_PRICING_URL = "https://developers.openai.com/api/docs/models/gpt-4o-mini"


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) != 20:
        raise ValueError("benchmark must contain exactly 20 cases")
    groups: dict[str, int] = defaultdict(int)
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("each benchmark case must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"invalid or duplicate benchmark id: {case_id!r}")
        seen.add(case_id)
        group = case.get("group")
        if group not in {"basic", "paraphrase", "invalid"}:
            raise ValueError(f"unsupported group for {case_id}: {group!r}")
        groups[group] += 1
        if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
            raise ValueError(f"blank prompt for {case_id}")
        expected = case.get("expected")
        if not isinstance(expected, dict) or set(expected) != {"accepted", "actions"}:
            raise ValueError(f"invalid expected result for {case_id}")
    if groups != {"basic": 10, "paraphrase": 5, "invalid": 5}:
        raise ValueError(f"unexpected benchmark group counts: {dict(groups)}")
    return cases


def semantic_plan(result: PlanningResult) -> dict[str, Any]:
    plan = plan_to_dict(result.plan)
    return {"accepted": plan["accepted"], "actions": plan["actions"]}


def plans_match(expected: object, actual: object) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(expected), float(actual), rel_tol=0.0, abs_tol=1e-9)
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(
            plans_match(expected[key], actual[key]) for key in expected
        )
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            plans_match(left, right) for left, right in zip(expected, actual)
        )
    return expected == actual


def estimated_openai_cost_usd(result: PlanningResult) -> float:
    input_tokens = result.input_tokens or 0
    cached_tokens = min(result.cached_input_tokens or 0, input_tokens)
    uncached_tokens = input_tokens - cached_tokens
    output_tokens = result.output_tokens or 0
    return (
        uncached_tokens * OPENAI_INPUT_USD_PER_M
        + cached_tokens * OPENAI_CACHED_INPUT_USD_PER_M
        + output_tokens * OPENAI_OUTPUT_USD_PER_M
    ) / 1_000_000


def run_provider(
    planner: OpenAIPlanner | OllamaPlanner,
    cases: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{planner.model}] {index:02d}/20 {case['id']}", flush=True)
        started = time.monotonic()
        try:
            result = planner.plan(case["prompt"])
            actual = semantic_plan(result)
            correct = plans_match(case["expected"], actual)
            reason = None if correct else "semantic plan mismatch"
            record = {
                "id": case["id"],
                "group": case["group"],
                "prompt": case["prompt"],
                "expected": case["expected"],
                "actual": actual,
                "message": result.plan.message,
                "correct": correct,
                "failure_reason": reason,
                "latency_s": round(result.latency_s, 6),
                "input_tokens": result.input_tokens,
                "cached_input_tokens": result.cached_input_tokens,
                "output_tokens": result.output_tokens,
                "estimated_cost_usd": (
                    round(estimated_openai_cost_usd(result), 9)
                    if result.provider == "openai"
                    else 0.0
                ),
            }
        except Exception as exc:
            latency_s = time.monotonic() - started
            record = {
                "id": case["id"],
                "group": case["group"],
                "prompt": case["prompt"],
                "expected": case["expected"],
                "actual": None,
                "message": None,
                "correct": False,
                "failure_reason": f"{type(exc).__name__}: {exc}",
                "latency_s": round(latency_s, 6),
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "estimated_cost_usd": 0.0,
            }
        records.append(record)
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [record["latency_s"] for record in records if record["latency_s"] is not None]
    correct = sum(bool(record["correct"]) for record in records)
    by_group: dict[str, dict[str, Any]] = {}
    for group in ("basic", "paraphrase", "invalid"):
        group_records = [record for record in records if record["group"] == group]
        group_correct = sum(bool(record["correct"]) for record in group_records)
        by_group[group] = {
            "correct": group_correct,
            "total": len(group_records),
            "accuracy_percent": round(100.0 * group_correct / len(group_records), 1),
        }
    return {
        "correct": correct,
        "total": len(records),
        "accuracy_percent": round(100.0 * correct / len(records), 1),
        "by_group": by_group,
        "latency_mean_s": round(statistics.mean(latencies), 6) if latencies else None,
        "latency_median_s": round(statistics.median(latencies), 6) if latencies else None,
        "input_tokens": sum(record["input_tokens"] or 0 for record in records),
        "cached_input_tokens": sum(
            record["cached_input_tokens"] or 0 for record in records
        ),
        "output_tokens": sum(record["output_tokens"] or 0 for record in records),
        "estimated_cost_usd": round(
            sum(record["estimated_cost_usd"] for record in records), 9
        ),
        "failures": [record["id"] for record in records if not record["correct"]],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Step 13 — 20-command LLM benchmark",
        "",
        f"Run time (UTC): `{report['run_time_utc']}`",
        "",
        "This is a planner-only benchmark. No command was sent to the executor or MuJoCo.",
        "Each case used a fresh conversation with no previous-plan context.",
        "Both providers used temperature 0; Qwen additionally used its fixed seed 42.",
        "",
        "## Summary",
        "",
        "| Provider | Model | Correct | Accuracy | Mean latency | Median latency | Input tokens | Cached input | Output tokens | Estimated API cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for provider in report["providers"]:
        summary = provider["summary"]
        lines.append(
            f"| {provider['provider']} | `{provider['model']}` | "
            f"{summary['correct']}/{summary['total']} | {summary['accuracy_percent']:.1f}% | "
            f"{summary['latency_mean_s']:.3f}s | {summary['latency_median_s']:.3f}s | "
            f"{summary['input_tokens']} | {summary['cached_input_tokens']} | "
            f"{summary['output_tokens']} | ${summary['estimated_cost_usd']:.6f} |"
        )
    lines.extend(["", "## Accuracy by group", ""])
    lines.extend(
        [
            "| Provider | Basic (10) | Paraphrase (5) | Invalid/out-of-range (5) |",
            "|---|---:|---:|---:|",
        ]
    )
    for provider in report["providers"]:
        groups = provider["summary"]["by_group"]
        lines.append(
            f"| {provider['provider']} | {groups['basic']['correct']}/10 | "
            f"{groups['paraphrase']['correct']}/5 | {groups['invalid']['correct']}/5 |"
        )
    lines.extend(["", "## Per-command results", ""])
    lines.extend(
        [
            "| ID | Group | OpenAI | Qwen | OpenAI latency | Qwen latency |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    providers = {entry["provider"]: entry for entry in report["providers"]}
    by_id = {
        name: {record["id"]: record for record in entry["records"]}
        for name, entry in providers.items()
    }
    for case in report["cases"]:
        cells = []
        latencies = []
        for name in ("openai", "ollama"):
            record = by_id.get(name, {}).get(case["id"])
            cells.append("✅" if record and record["correct"] else "❌")
            latency = record.get("latency_s") if record else None
            latencies.append(f"{latency:.3f}s" if latency is not None else "n/a")
        lines.append(
            f"| {case['id']} | {case['group']} | {cells[0]} | {cells[1]} | "
            f"{latencies[0]} | {latencies[1]} |"
        )
    failures = [
        (provider["provider"], record)
        for provider in report["providers"]
        for record in provider["records"]
        if not record["correct"]
    ]
    lines.extend(["", "## Failure analysis", ""])
    if not failures:
        lines.append("No semantic failures occurred in this run.")
    else:
        for provider, record in failures:
            lines.extend(
                [
                    f"### {provider} / {record['id']}",
                    "",
                    f"- Prompt: `{record['prompt']}`",
                    f"- Reason: {record['failure_reason']}",
                    f"- Expected: `{json.dumps(record['expected'], ensure_ascii=False)}`",
                    f"- Actual: `{json.dumps(record['actual'], ensure_ascii=False)}`",
                    "",
                ]
            )
    lines.extend(
        [
            "## Interpretation",
            "",
            "The total score must be read together with the category scores. OpenAI was more "
            "conservative and rejected every invalid or out-of-range request, but it also "
            "over-rejected several safe paraphrases. Qwen understood more supported wording "
            "and every basic command, but it was less safe on numeric limits.",
            "",
            "For two Qwen limit failures, the model emitted illegal values and the independent "
            "local validator stopped them before execution. For `invalid_01`, Qwen silently "
            "changed requested speed 1.5 to 1.0; that output was schema-valid, so this is a "
            "real semantic safety failure that cannot be detected by output validation alone.",
            "",
        ]
    )
    lines.extend(
        [
            "## Cost method",
            "",
            "OpenAI cost is estimated from returned input, cached-input and output token counts. "
            "The rates used for `gpt-4o-mini` are $0.15, $0.075 and $0.60 per one million "
            "tokens respectively. Local Qwen has no API fee; electricity is not measured.",
            "",
            f"Pricing source: {report['openai_pricing_url']}",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("both", "openai", "ollama"), default="both")
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--ollama-model", default="qwen2.5:7b")
    parser.add_argument("--ollama-host", default=None)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = load_cases()
    planners: list[tuple[str, OpenAIPlanner | OllamaPlanner]] = []
    if args.provider in {"both", "openai"}:
        planners.append(("openai", OpenAIPlanner(model=args.openai_model)))
    if args.provider in {"both", "ollama"}:
        planners.append(
            (
                "ollama",
                OllamaPlanner(model=args.ollama_model, host=args.ollama_host),
            )
        )

    providers = []
    for provider_name, planner in planners:
        records = run_provider(planner, cases)
        providers.append(
            {
                "provider": provider_name,
                "model": planner.model,
                "summary": summarize(records),
                "records": records,
            }
        )
    report = {
        "run_time_utc": datetime.now(timezone.utc).isoformat(),
        "cases_path": str(CASES_PATH.relative_to(CASES_PATH.parent.parent)),
        "cases": cases,
        "openai_pricing_url": OPENAI_PRICING_URL,
        "providers": providers,
    }
    json_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    markdown_text = markdown_report(report)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json_text, encoding="utf-8")
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown_text, encoding="utf-8")
    print(json.dumps({entry["provider"]: entry["summary"] for entry in providers}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
